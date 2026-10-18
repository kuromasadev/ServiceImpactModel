"""Inspect source schemas and explicitly adapt stop observations into stop pairs."""
import argparse
import csv
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
from zoneinfo import ZoneInfo

from .pipeline import REQUIRED, ROOT, PRIVATE, canonical, config, normalize, number, private_path, sha


def source_reader(path):
    with Path(path).open("rb") as stream:
        sample = stream.read(4096)
    encoding = "utf-16" if sample.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-16-le" if b"\x00" in sample else "utf-8-sig"
    stream = Path(path).open(encoding=encoding, newline="")
    first = stream.readline()
    delimiter = "\t" if first.count("\t") > first.count(",") else ","
    stream.seek(0)
    reader = csv.DictReader(stream, delimiter=delimiter)
    reader.fieldnames = [s.strip() for s in reader.fieldnames or []]
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
        stream.close()
        raise ValueError("Source requires a nonempty, unique header")
    return stream, reader, encoding, delimiter


def inspect(path):
    stream, reader, encoding, delimiter = source_reader(path)
    with stream:
        return {"filename": Path(path).name, "bytes": Path(path).stat().st_size,
                "sha256": sha(path), "encoding": encoding,
                "delimiter": "tab" if delimiter == "\t" else "comma", "columns": reader.fieldnames}


def service_time(service_date, value, rollover):
    match = re.fullmatch(r"(\d{1,2}):(\d{2}):(\d{2}(?:\.\d+)?)", value.strip())
    if not match:
        raise ValueError("Expected HH:MM:SS source time")
    hour, minute, second = map(float, match.groups())
    if hour >= 48 or minute >= 60 or second >= 60:
        raise ValueError("Source time out of range")
    if hour < rollover:
        hour += 24
    local = datetime.strptime(service_date, "%m/%d/%Y") + timedelta(hours=hour, minutes=minute, seconds=second)
    zone = ZoneInfo("America/Chicago")
    if local.replace(tzinfo=zone, fold=0).utcoffset() != local.replace(tzinfo=zone, fold=1).utcoffset():
        raise ValueError("DST ambiguous/nonexistent source time; supply an explicitly offset canonical CSV")
    return local.replace(tzinfo=zone).isoformat()


def adapt(source, output, mapping, cfg):
    """Require stable source sequence and vehicle; never invent either identity."""
    for key in ("vehicle_id", "sequence"):
        if not mapping.get(key):
            raise ValueError(f"Set verified {key} column in the source mapping before conversion")
    if not 0 <= mapping["service_day_rollover_hour"] <= 4:
        raise ValueError("Service-day rollover must be explicitly configured in [0,4]")
    stream, reader, _, _ = source_reader(source)
    mapped = [v for k, v in mapping.items() if k not in {"movement_values", "service_day_rollover_hour", "notes"}]
    if any(v not in reader.fieldnames for v in mapped):
        stream.close()
        raise ValueError("Mapped columns missing from source; inspect schema before adapting")
    output = private_path(output)
    original_sha = sha(source)
    with tempfile.TemporaryDirectory(dir=PRIVATE) as directory:
        db = sqlite3.connect(Path(directory) / "stops.sqlite")
        db.execute("CREATE TABLE stops (trip TEXT, seq INTEGER, raw TEXT, PRIMARY KEY(trip,seq))")
        stop_count = duplicates = 0
        try:
            with stream, db:
                for line, row in enumerate(reader, 2):
                    if None in row or any(value is None for value in row.values()):
                        raise ValueError(f"Line {line}: incorrect source field count")
                    raw = {k: row[v].strip() for k, v in mapping.items() if k not in {"movement_values", "service_day_rollover_hour", "notes"}}
                    route_match = re.match(r"^(?:R)?(162|221|222)(?:\D|$)", raw["route"])
                    if not route_match:
                        raise ValueError(f"Line {line}: unknown route; no out-of-scope rows silently discarded")
                    raw["route"] = "R" + route_match[1]
                    for key in ("vehicle_id", "trip_id", "direction", "sequence"):
                        if not raw[key]:
                            raise ValueError(f"Line {line}: missing stable {key}")
                    trip = canonical([raw[k] for k in ("route", "service_date", "trip_id", "vehicle_id", "direction")])
                    sequence = int(raw["sequence"])
                    if sequence < 0:
                        raise ValueError(f"Line {line}: negative source sequence")
                    old = db.execute("SELECT raw FROM stops WHERE trip=? AND seq=?", (trip, sequence)).fetchone()
                    if old:
                        if old[0] != canonical(raw):
                            raise ValueError(f"Line {line}: conflicting source stop key")
                        duplicates += 1
                    else:
                        db.execute("INSERT INTO stops VALUES (?,?,?)", (trip, sequence, canonical(raw)))
                        stop_count += 1
            count = 0
            previous, previous_trip = None, None
            temporary = output.with_suffix(output.suffix + ".tmp")
            try:
                with temporary.open("w", newline="", encoding="utf-8") as target:
                    writer = csv.DictWriter(target, fieldnames=REQUIRED, lineterminator="\n")
                    writer.writeheader()
                    for trip, _, packed in db.execute("SELECT trip,seq,raw FROM stops ORDER BY trip,seq"):
                        current = json.loads(packed)
                        if previous is not None and trip == previous_trip:
                            a, b = previous, current
                            stop_ids = [re.search(r"\(([^()]+)\)\s*$", item["stop"]) for item in (a, b)]
                            if not all(stop_ids):
                                raise ValueError("Stop IDs must be explicitly present in trailing parentheses")
                            pattern = a["pattern_type"].casefold()
                            if pattern not in mapping["movement_values"]:
                                raise ValueError("Unmapped pattern type; classify its exact source label explicitly")
                            row = {k: a[k] for k in ("route", "direction", "trip_id", "vehicle_id")}
                            row.update(schema_version=cfg["schema_version"],
                                service_date=datetime.strptime(a["service_date"], "%m/%d/%Y").date().isoformat(),
                                from_sequence=a["sequence"], to_sequence=b["sequence"],
                                from_stop_id=stop_ids[0][1], to_stop_id=stop_ids[1][1],
                                movement=mapping["movement_values"][pattern], scheduled_miles="")
                            for result, stop, field in (("scheduled_start", a, "scheduled_departure"),
                                ("scheduled_end", b, "scheduled_arrival"), ("actual_start", a, "actual_departure"),
                                ("actual_end", b, "actual_arrival")):
                                row[result] = service_time(a["service_date"], stop[field], mapping["service_day_rollover_hour"])
                            row["observed_miles"] = float(b["odometer"].replace(",", "")) - float(a["odometer"].replace(",", "")) if a["odometer"] and b["odometer"] else ""
                            for field in ("load", "boardings", "alightings"):
                                vals = [stop[field] for stop in (a, b)]
                                parsed = [number(v.replace(",", "")) for v in vals if v]
                                # A positive endpoint establishes presence; zero requires both endpoints.
                                row[field] = max(parsed) if len(parsed) == 2 or any(v > 0 for v in parsed) else ""
                            row["terminal_event"] = str(any(t["route"] == row["route"] and t["direction"] == row["direction"]
                                and t["stop_id"] == row["to_stop_id"] for t in cfg.get("terminals", []))).lower()
                            normalize({k: str(v) for k, v in row.items()}, cfg)
                            writer.writerow(row)
                            count += 1
                        previous, previous_trip = current, trip
                if not count:
                    raise ValueError("No stop pairs; source trips need at least two stops")
                if sha(source) != original_sha:
                    raise ValueError("Source changed during adaptation; output not replaced")
                temporary.replace(output)
            finally:
                temporary.unlink(missing_ok=True)
        finally:
            db.close()
    report = {"source_sha256": sha(source), "canonical_sha256": sha(output), "source_filename": Path(source).name,
              "source_stops": stop_count, "duplicate_stops": duplicates, "pairs": count,
              "mapping": mapping, "missing_scheduled_mileage": True}
    output.with_suffix(output.suffix + ".source.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    view = sub.add_parser("inspect")
    view.add_argument("sources", type=Path, nargs="+")
    convert = sub.add_parser("adapt")
    convert.add_argument("source", type=Path)
    convert.add_argument("--output", type=Path, required=True)
    convert.add_argument("--mapping", type=Path, required=True)
    convert.add_argument("--config", type=Path, default=ROOT / "config.json")
    args = parser.parse_args()
    try:
        result = ([inspect(path) for path in args.sources] if args.command == "inspect" else
                  adapt(args.source, args.output, json.loads(args.mapping.read_text()), config(args.config)))
        print(json.dumps(result, indent=2))
    except (ValueError, KeyError, OSError, sqlite3.Error) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
