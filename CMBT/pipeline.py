"""Private weekly ingestion and release-reviewed aggregate exports.

Run from the repository root: python -m CMBT.pipeline --help
"""
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import sqlite3
import sys
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
PRIVATE = ROOT / "private"
LIMIT = 95 * 1024 * 1024
PHASES = {"pr_connection", "freeway", "destination_connection"}
MOVEMENTS = {"scheduled_service", "deadhead", "other_non_revenue"}
SLICES = ["Early AM", "AM Peak", "Morning", "Mid-Day", "Afternoon",
          "PM Peak", "After PM", "Evening", "Late"]
REQUIRED = ["schema_version", "route", "direction", "service_date", "trip_id",
            "vehicle_id", "from_sequence", "to_sequence", "from_stop_id",
            "to_stop_id", "scheduled_start", "scheduled_end", "actual_start",
            "actual_end", "scheduled_miles", "observed_miles", "movement",
            "load", "boardings", "alightings", "terminal_event"]
GROUP = ["route", "direction", "service_date", "time_slice", "time_slice_order",
         "period", "phase", "movement", "passenger_presence", "crosses_cutover",
         "trip_crosses_cutover"]
METRICS = ["pairs", "scheduled_seconds", "observed_seconds", "scheduled_miles",
           "observed_miles", "scheduled_miles_samples", "observed_miles_samples",
           "delay_histogram", "terminal_delay_histogram", "source_batch_sha256",
           "qa_flags", "baseline_status"]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def config(path=ROOT / "config.json"):
    cfg = json.loads(Path(path).read_text())
    if set(cfg["routes"]) != {"R162", "R221", "R222"}:
        raise ValueError("Config must retain all three commuter routes")
    if cfg["timezone"] != "America/Chicago" or stamp(cfg["cutover"]) != stamp("2026-10-09T21:00:00-05:00"):
        raise ValueError("Closure cutoff must be October 9, 2026 at 9 PM Central")
    date.fromisoformat(cfg["baseline_start"])
    seen = set()
    for boundary in cfg["phase_boundaries"]:
        key = tuple(boundary[k] for k in ("route", "direction", "from_stop_id", "to_stop_id"))
        if (key in seen or boundary["route"] not in cfg["routes"]
                or boundary["phase"] not in PHASES
                or boundary.get("verified") is not True or not boundary.get("evidence")):
            raise ValueError("Phase boundaries require unique pairs, a physical phase, verification and evidence")
        seen.add(key)
    seen = set()
    for terminal in cfg.get("terminals", []):
        key = (terminal["route"], terminal["direction"])
        if (key in seen or key[0] not in cfg["routes"] or not terminal.get("stop_id")
                or terminal.get("verified") is not True or not terminal.get("evidence")):
            raise ValueError("Terminals require unique route/direction, a stop ID, verification and evidence")
        seen.add(key)
    return cfg


def stamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamps require explicit UTC offsets, including DST disambiguation")
    return parsed.astimezone(timezone.utc)


def otp(seconds, early=-59, late=359):
    if early > late:
        raise ValueError("Early threshold must be at or below late threshold")
    return "Early" if seconds < early else "Late" if seconds > late else "On Time"


def time_slice(hour):
    for index, (start, end) in enumerate([(4, 6), (6, 9), (9, 12), (12, 14),
                                         (14, 16), (16, 18), (18, 20), (20, 22)]):
        if start <= hour < end:
            return SLICES[index], index
    return "Late", 8


def number(value):
    if value == "":
        return None
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError("Miles, loads, boardings and alightings must be finite and nonnegative")
    return result


def normalize(row, cfg):
    if row["schema_version"] != cfg["schema_version"] or row["route"] not in cfg["routes"]:
        raise ValueError("Unsupported schema version or route")
    for field in ("direction", "trip_id", "vehicle_id", "from_stop_id", "to_stop_id"):
        if not row[field].strip():
            raise ValueError(f"Missing {field}")
    service = date.fromisoformat(row["service_date"])
    start_seq, end_seq = int(row["from_sequence"]), int(row["to_sequence"])
    if start_seq < 0 or end_seq <= start_seq:
        raise ValueError("Stop sequences must be nonnegative and increase within a trip")
    times = {key: stamp(row[key]) for key in ("scheduled_start", "scheduled_end", "actual_start", "actual_end")}
    if times["scheduled_end"] < times["scheduled_start"] or times["actual_end"] < times["actual_start"]:
        raise ValueError("Pair end must be at or after start")
    if row["movement"] not in MOVEMENTS or row["terminal_event"] not in {"true", "false"}:
        raise ValueError("Movement or terminal_event is not an accepted value")
    if row["terminal_event"] == "true" and not any(
        t["route"] == row["route"] and t["direction"] == row["direction"]
        and t["stop_id"] == row["to_stop_id"] for t in cfg.get("terminals", [])
    ):
        raise ValueError("Terminal event requires a verified route/direction terminal stop")
    values = {key: number(row[key]) for key in ("load", "boardings", "alightings", "scheduled_miles", "observed_miles")}
    passenger_values = [values[key] for key in ("load", "boardings", "alightings")]
    presence = ("present" if any(v is not None and v > 0 for v in passenger_values)
                else "empty" if all(v == 0 for v in passenger_values) else "unknown")
    cutover = stamp(cfg["cutover"])
    local_end = times["actual_end"].astimezone(ZoneInfo(cfg["timezone"]))
    period = ("impact" if times["actual_end"] >= cutover else
              "baseline" if local_end.date() >= date.fromisoformat(cfg["baseline_start"]) else "outside_baseline")
    # A pair is an indivisible observation: classify by arrival and flag any crossing.
    crossing = times["actual_start"] < cutover <= times["actual_end"]
    phase = "unclassified"
    for boundary in cfg["phase_boundaries"]:
        if all(row[k] == boundary[k] for k in ("route", "direction", "from_stop_id", "to_stop_id")):
            phase = boundary["phase"]
    flags = []
    if phase == "unclassified":
        flags.append("unverified_phase")
    if presence == "unknown":
        flags.append("unknown_passenger_presence")
    if presence == "present" and row["movement"] != "scheduled_service":
        flags.append("passengers_on_non_revenue_movement")
    if crossing:
        flags.append("cutover_crossing_pair_full_runtime_assigned_to_arrival_period")
    if values["scheduled_miles"] is None or values["observed_miles"] is None:
        flags.append("missing_miles")
    if not any(t["route"] == row["route"] and t["direction"] == row["direction"] for t in cfg.get("terminals", [])):
        flags.append("unverified_terminal")
    label, order = time_slice(times["scheduled_start"].astimezone(ZoneInfo(cfg["timezone"])).hour)
    key = [row[k] for k in ("route", "service_date", "trip_id", "vehicle_id")] + [start_seq, end_seq]
    trip = key[:4]
    delay = (times["actual_end"] - times["scheduled_end"]).total_seconds()
    result = {**{k: row[k] for k in ("route", "direction", "service_date", "movement")},
              "time_slice": label, "time_slice_order": order, "period": period, "phase": phase,
              "passenger_presence": presence, "crosses_cutover": crossing,
              "actual_start": times["actual_start"].isoformat(), "actual_end": times["actual_end"].isoformat(),
              "scheduled_seconds": (times["scheduled_end"] - times["scheduled_start"]).total_seconds(),
              "observed_seconds": (times["actual_end"] - times["actual_start"]).total_seconds(),
              "scheduled_miles": values["scheduled_miles"], "observed_miles": values["observed_miles"],
              "delay": delay, "terminal_event": row["terminal_event"] == "true", "qa_flags": flags,
              "trip": trip}
    return canonical(key), result


def private_path(path):
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(PRIVATE.resolve()):
        raise ValueError("Private databases and unapproved exports must stay in CMBT/private/")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def connect(path):
    db = sqlite3.connect(private_path(path))
    db.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS batches (sha TEXT PRIMARY KEY, details TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pairs (key TEXT PRIMARY KEY, raw TEXT NOT NULL, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sources (pair_key TEXT REFERENCES pairs(key), batch_sha TEXT REFERENCES batches(sha),
            PRIMARY KEY(pair_key, batch_sha));
        CREATE TABLE IF NOT EXISTS baseline_revisions (id INTEGER PRIMARY KEY, details TEXT NOT NULL);
    """)
    return db


def baseline_digest(db):
    digest = hashlib.sha256()
    count = 0
    for key, data in db.execute("SELECT key,data FROM pairs ORDER BY key"):
        if json.loads(data)["period"] == "baseline":
            digest.update((key + "\n" + data + "\n").encode())
            count += 1
    return {"sha256": digest.hexdigest(), "pairs": count}


def setting(db, key):
    row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else None


def ingest(db, source, received, cfg, revision_approver=None, revision_reason=None):
    source = Path(source)
    date.fromisoformat(received)
    batch_sha = sha(source)
    if db.execute("SELECT 1 FROM batches WHERE sha=?", (batch_sha,)).fetchone():
        return {"status": "already_ingested", "sha256": batch_sha}
    cfg_hash = hashlib.sha256(canonical(cfg).encode()).hexdigest()
    existing = setting(db, "config_sha256")
    if existing and existing != cfg_hash:
        raise ValueError("Config changed: rebuild a separate private database and review the baseline revision")
    frozen = setting(db, "baseline_freeze")
    if bool(revision_approver) != bool(revision_reason):
        raise ValueError("Baseline revision requires both approver and reason")
    routes, dates, seen, warnings = set(), set(), set(), set()
    inserted = duplicate = baseline_added = 0
    with db:
        db.execute("INSERT INTO batches VALUES (?,?)", (batch_sha, "{}"))
        with source.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != REQUIRED:
                raise ValueError("CSV header must match CMBT/schema.md exactly; adapt the source explicitly")
            for line, raw in enumerate(reader, 2):
                if None in raw or any(value is None for value in raw.values()):
                    raise ValueError(f"CSV line {line}: incorrect field count")
                try:
                    key, data = normalize(raw, cfg)
                except (ValueError, KeyError, TypeError) as error:
                    raise ValueError(f"CSV line {line}: {error}") from error
                routes.add(data["route"])
                dates.add(data["service_date"])
                warnings.update(data["qa_flags"])
                old = db.execute("SELECT raw FROM pairs WHERE key=?", (key,)).fetchone()
                if old and old[0] != canonical(raw):
                    raise ValueError(f"CSV line {line}: conflicting stable key; prior record preserved")
                if old:
                    duplicate += 1
                else:
                    if data["period"] == "baseline":
                        if frozen and not (revision_approver and revision_reason):
                            raise ValueError("Frozen baseline would change; a recorded approval and revision reason are required")
                        baseline_added += 1
                    db.execute("INSERT INTO pairs VALUES (?,?,?)", (key, canonical(raw), canonical(data)))
                    inserted += 1
                db.execute("INSERT OR IGNORE INTO sources VALUES (?,?)", (key, batch_sha))
                seen.add(key)
        if not dates:
            raise ValueError("Empty CSV batch")
        if sha(source) != batch_sha:
            raise ValueError("Source changed during ingestion; batch rolled back")
        missing = sorted(set(cfg["routes"]) - routes)
        if missing:
            warnings.add("missing_routes:" + ",".join(missing))
        details = {"filename": source.name, "received_date": received, "sha256": batch_sha,
                   "coverage_start": min(dates), "coverage_end": max(dates),
                   "schema_version": cfg["schema_version"], "routes": sorted(routes),
                   "unique_pairs": len(seen), "inserted_pairs": inserted, "duplicate_rows": duplicate,
                   "qa_result": "pass_with_warnings" if warnings else "pass", "qa_flags": sorted(warnings)}
        source_report = source.with_suffix(source.suffix + ".source.json")
        if source_report.exists():
            provenance = json.loads(source_report.read_text())
            if provenance.get("canonical_sha256") != batch_sha:
                raise ValueError("Source-adapter provenance does not match canonical batch")
            details["source_adapter"] = provenance
        db.execute("UPDATE batches SET details=? WHERE sha=?", (canonical(details), batch_sha))
        db.execute("INSERT OR REPLACE INTO settings VALUES ('config_sha256',?)", (canonical(cfg_hash),))
        db.execute("INSERT OR REPLACE INTO settings VALUES ('config',?)", (canonical(cfg),))
        if frozen and baseline_added:
            freeze(db, revision_approver, revision_reason)
    return details


def freeze(db, approver, reason):
    if not approver.strip() or not reason.strip():
        raise ValueError("An approval identity and reason are required")
    snapshot = baseline_digest(db)
    if not snapshot["pairs"]:
        raise ValueError("Cannot freeze an empty baseline")
    details = {**snapshot, "approved_by": approver, "reason": reason,
               "recorded_at": datetime.now(timezone.utc).isoformat(),
               "previous": setting(db, "baseline_freeze")}
    db.execute("INSERT INTO baseline_revisions(details) VALUES (?)", (canonical(details),))
    db.execute("INSERT OR REPLACE INTO settings VALUES ('baseline_freeze',?)", (canonical(details),))
    return details


def aggregate(db):
    frozen = setting(db, "baseline_freeze")
    if frozen and baseline_digest(db) != {k: frozen[k] for k in ("sha256", "pairs")}:
        raise ValueError("Frozen baseline integrity check failed")
    records = [(key, json.loads(data)) for key, data in db.execute("SELECT key,data FROM pairs ORDER BY key")]
    if not records:
        raise ValueError("No ingested observations")
    trips = {}
    terminals = set()
    for _, row in records:
        trip = canonical(row["trip"])
        bounds = trips.setdefault(trip, [row["actual_start"], row["actual_end"]])
        bounds[0], bounds[1] = min(bounds[0], row["actual_start"]), max(bounds[1], row["actual_end"])
        if row["terminal_event"]:
            if trip in terminals:
                raise ValueError("More than one terminal event in a stable trip; correct the source adapter")
            terminals.add(trip)
    cfg = setting(db, "config")
    cutoff = stamp(cfg["cutover"])
    sources = {}
    for key, batch in db.execute("SELECT pair_key,batch_sha FROM sources"):
        sources.setdefault(key, set()).add(batch)
    groups = {}
    for key, row in records:
        bounds = trips[canonical(row["trip"])]
        row["trip_crosses_cutover"] = stamp(bounds[0]) < cutoff <= stamp(bounds[1])
        if canonical(row["trip"]) not in terminals:
            row["qa_flags"].append("missing_verified_terminal_for_trip")
        group_key = tuple(row[field] for field in GROUP)
        group = groups.setdefault(group_key, {**dict(zip(GROUP, group_key)), "pairs": 0,
            **{k: 0 for k in ("scheduled_seconds", "observed_seconds", "scheduled_miles", "observed_miles",
                             "scheduled_miles_samples", "observed_miles_samples")},
            "delay_histogram": {}, "terminal_delay_histogram": {}, "source_batch_sha256": set(),
            "qa_flags": set(), "baseline_status": "frozen" if frozen else "provisional"})
        group["pairs"] += 1
        for field in ("scheduled_seconds", "observed_seconds", "scheduled_miles", "observed_miles"):
            if row[field] is not None:
                group[field] += row[field]
                if field.endswith("miles"):
                    group[field + "_samples"] += 1
        delay_key = str(row["delay"])
        group["delay_histogram"][delay_key] = group["delay_histogram"].get(delay_key, 0) + 1
        if row["terminal_event"]:
            group["terminal_delay_histogram"][delay_key] = group["terminal_delay_histogram"].get(delay_key, 0) + 1
        group["source_batch_sha256"].update(sources[key])
        group["qa_flags"].update(row["qa_flags"])
    result = []
    for _, group in sorted(groups.items()):
        for field in ("source_batch_sha256", "qa_flags"):
            group[field] = sorted(group[field])
        result.append(group)
    return result


def export(db, output):
    output = private_path(output)
    rows = aggregate(db)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=GROUP + METRICS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: canonical(v) if isinstance(v, (dict, list)) else
                         str(v).lower() if isinstance(v, bool) else v for k, v in row.items()})
    packed = gzip.compress(stream.getvalue().encode(), mtime=0)
    if len(packed) > LIMIT:
        raise ValueError("Unified file exceeds 95 MiB; stop and review compacting or approved hosting")
    if output.exists() and hashlib.sha256(packed).hexdigest() != sha(output):
        archive = PRIVATE / "archive"
        archive.mkdir(exist_ok=True)
        prior_hash = sha(output)
        archived = archive / (prior_hash + ".csv.gz")
        if not archived.exists():
            shutil.copyfile(output, archived)
        prior_report = output.with_suffix(output.suffix + ".qa.json")
        if prior_report.exists():
            archived_report = archived.with_suffix(archived.suffix + ".qa.json")
            if not archived_report.exists():
                shutil.copyfile(prior_report, archived_report)
    temp = output.with_suffix(output.suffix + ".tmp")
    temp.write_bytes(packed)
    temp.replace(output)
    report = {"sha256": sha(output), "bytes": output.stat().st_size, "aggregate_rows": len(rows),
              "pairs": sum(row["pairs"] for row in rows),
              "routes": sorted({row["route"] for row in rows}),
              "coverage_start": min(row["service_date"] for row in rows),
              "coverage_end": max(row["service_date"] for row in rows),
              "baseline": setting(db, "baseline_freeze"),
              "config": setting(db, "config"), "public_release_approved": False}
    output.with_suffix(output.suffix + ".qa.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=PRIVATE / "commuter.sqlite")
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    sub = parser.add_subparsers(dest="command", required=True)
    load = sub.add_parser("ingest")
    load.add_argument("csv", type=Path)
    load.add_argument("--received", required=True, help="Received date, YYYY-MM-DD")
    load.add_argument("--baseline-revision-approved-by")
    load.add_argument("--baseline-revision-reason")
    out = sub.add_parser("export")
    out.add_argument("--output", type=Path, default=PRIVATE / "commuter.csv.gz")
    lock = sub.add_parser("freeze-baseline")
    lock.add_argument("--approved-by", required=True)
    lock.add_argument("--reason", required=True)
    sub.add_parser("inventory")
    args = parser.parse_args()
    try:
        with connect(args.database) as db:
            if args.command == "ingest":
                result = ingest(db, args.csv, args.received, config(args.config),
                                args.baseline_revision_approved_by, args.baseline_revision_reason)
            elif args.command == "export":
                result = export(db, args.output)
            elif args.command == "freeze-baseline":
                result = freeze(db, args.approved_by, args.reason)
            else:
                result = {"batches": [json.loads(r[0]) for r in db.execute("SELECT details FROM batches ORDER BY sha")],
                          "baseline": setting(db, "baseline_freeze")}
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, sqlite3.Error) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
