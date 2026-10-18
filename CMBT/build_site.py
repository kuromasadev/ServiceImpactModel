"""Generate code and a small manifest pointing to approved GitHub Release data."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import shutil
import sys

from .pipeline import GROUP, METRICS, LIMIT, ROOT, sha
from .release import reference

RELEASE_METRICS = ["arrival_schedule_deviation", "terminal_arrival_schedule_deviation",
                   "scheduled_observed_runtime", "scheduled_observed_miles",
                   "non_revenue_runtime_miles", "passenger_presence_classes",
                   "source_batch_hashes", "coverage_qa", "scenario_rankings"]


def validate_release(data, approval):
    data = Path(data)
    review = json.loads(Path(approval).read_text())
    report = json.loads(data.with_suffix(data.suffix + ".qa.json").read_text())
    digest, size = sha(data), data.stat().st_size
    if size > LIMIT:
        raise ValueError("Unified file exceeds the 95 MiB safe target")
    if (review.get("approved") is not True or not review.get("approved_by")
            or not review.get("approved_at") or not review.get("evidence")
            or review.get("sha256") != digest or report.get("sha256") != digest
            or review.get("bytes") != size or report.get("bytes") != size):
        raise ValueError("Exact dataset bytes/hash, data-owner approval identity, date and evidence are required")
    if set(review.get("metrics", [])) != set(RELEASE_METRICS):
        raise ValueError("Data-owner approval must cover every displayed metric listed in approval.example.json")
    if not report.get("baseline") or not report["baseline"].get("approved_by"):
        raise ValueError("Freeze and approve the baseline before public release")
    rows, pairs, routes = 0, 0, set()
    with gzip.open(data, "rt", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != GROUP + METRICS:
            raise ValueError("Release dataset does not match the aggregate schema")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Malformed release row")
            if row["baseline_status"] != "frozen":
                raise ValueError("Provisional baseline in release dataset")
            flags = json.loads(row["qa_flags"])
            if "unverified_phase" in flags or "unverified_terminal" in flags:
                raise ValueError("Verify physical phase boundaries and terminal stops before public release")
            count = int(row["pairs"])
            hist = json.loads(row["delay_histogram"])
            terminals = json.loads(row["terminal_delay_histogram"])
            if count <= 0 or sum(hist.values()) != count or sum(terminals.values()) > count:
                raise ValueError("Release summary totals do not reconcile")
            routes.add(row["route"])
            pairs += count
            rows += 1
    if routes != {"R162", "R221", "R222"} or pairs != report["pairs"] or rows != report["aggregate_rows"]:
        raise ValueError("Release requires all three routes and reconciled QA totals")
    return {"status": "approved", "sha256": digest,
            "bytes": size, "pairs": pairs, "rows": rows,
            "coverage_start": report["coverage_start"], "coverage_end": report["coverage_end"],
            "baseline_status": "frozen", "baseline_start": report["config"]["baseline_start"],
            "cutover": report["config"]["cutover"], "metrics": RELEASE_METRICS}


def build(output, data=None, approval=None, repository=None, release_date=None, release_metadata=None):
    release_args = (data, approval, repository, release_date, release_metadata)
    if any(release_args) and not all(release_args):
        raise ValueError("Supply --data, --approval, --repository, --release-date and --release-metadata together")
    manifest = (validate_release(data, approval) if data else
                {"status": "pending", "dataset": None,
                 "message": "No dataset has been approved for public display. Analysis is pending source validation and review."})
    if data:
        manifest.update(reference(repository, release_date, manifest,
                                  json.loads(Path(release_metadata).read_text())))
    output = Path(output)
    if (output / "data").exists():
        raise ValueError("Site must contain code and a manifest only; preserve and move legacy data out of the Pages tree")
    if (output / "manifest.json").exists() and not data:
        old = json.loads((output / "manifest.json").read_text())
        if old.get("status") == "approved":
            raise ValueError("Existing approved release preserved; pass its reviewed data and approval to rebuild")
    output.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "styles.css", "app.mjs", "model.mjs", "data.mjs"):
        shutil.copyfile(ROOT / "site" / name, output / name)
    shutil.copyfile(ROOT / "schema.md", output / "data-dictionary.md")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT.parent / "Commuter")
    parser.add_argument("--data", type=Path)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--repository", help="OWNER/REPOSITORY containing the dated release")
    parser.add_argument("--release-date", help="Dated snapshot YYYY-MM-DD")
    parser.add_argument("--release-metadata", type=Path, help="Published GitHub Release API JSON")
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.output, args.data, args.approval, args.repository,
                               args.release_date, args.release_metadata), indent=2))
    except (ValueError, OSError, KeyError) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
