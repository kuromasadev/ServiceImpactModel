import csv
import gzip
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from CMBT import build_site, ivoms, pipeline as p, release


def synthetic_row(**changes):
    row = dict(zip(p.REQUIRED, ["1", "R162", "TEST_OUTBOUND", "2026-10-09", "TEST_TRIP", "TEST_VEHICLE",
        "1", "2", "TEST_A", "TEST_B", "2026-10-09T20:58:00-05:00", "2026-10-09T20:59:00-05:00",
        "2026-10-09T20:58:00-05:00", "2026-10-09T20:59:00-05:00", "1.0", "1.1", "scheduled_service",
        "0", "0", "0", "true"]))
    row.update(changes)
    return row


class PipelineTests(unittest.TestCase):
    def setUp(self):
        p.PRIVATE.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=p.PRIVATE)
        self.root = Path(self.directory.name)
        self.cfg = p.config()
        self.cfg["phase_boundaries"] = [{"route": route, "direction": "TEST_OUTBOUND", "from_stop_id": "TEST_A",
            "to_stop_id": "TEST_B", "phase": "freeway", "verified": True, "evidence": "Synthetic test only"}
            for route in self.cfg["routes"]]
        self.cfg["terminals"] = [{"route": route, "direction": "TEST_OUTBOUND", "stop_id": "TEST_B",
            "verified": True, "evidence": "Synthetic test only"} for route in self.cfg["routes"]]
        self.db = p.connect(self.root / "test.sqlite")

    def tearDown(self):
        self.db.close()
        self.directory.cleanup()

    def batch(self, rows, name="batch.csv"):
        path = self.root / name
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=p.REQUIRED)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def load(self, rows, name="batch.csv", **kwargs):
        return p.ingest(self.db, self.batch(rows, name), "2026-10-18", self.cfg, **kwargs)

    def test_otp_inclusive_boundaries(self):
        self.assertEqual([p.otp(v) for v in (-60, -59, 359, 360)], ["Early", "On Time", "On Time", "Late"])
        self.assertEqual(p.otp(359.001), "Late")

    def test_cutover_utc_and_crossing_pair(self):
        for arrival, period in [("2026-10-09T20:59:59-05:00", "baseline"),
                                ("2026-10-10T02:00:00+00:00", "impact"),
                                ("2026-10-14T07:00:00-05:00", "impact")]:
            row = p.normalize(synthetic_row(actual_end=arrival), self.cfg)[1]
            self.assertEqual(row["period"], period)
        row = p.normalize(synthetic_row(actual_end="2026-10-09T21:01:00-05:00"), self.cfg)[1]
        self.assertTrue(row["crosses_cutover"])
        self.assertEqual(row["observed_seconds"], 180)

    def test_crossing_trip_preserves_pair_periods(self):
        self.load([synthetic_row(terminal_event="false"), synthetic_row(from_sequence="2", to_sequence="3",
            actual_start="2026-10-09T21:00:00-05:00", actual_end="2026-10-09T21:01:00-05:00")])
        rows = p.aggregate(self.db)
        self.assertEqual({r["period"] for r in rows}, {"baseline", "impact"})
        self.assertTrue(all(r["trip_crosses_cutover"] for r in rows))

    def test_missing_timezone_rejected(self):
        with self.assertRaisesRegex(ValueError, "UTC offsets"):
            p.normalize(synthetic_row(actual_end="2026-10-09T20:59:00"), self.cfg)

    def test_all_hours_have_chronological_bands(self):
        expected = ["Late"] * 4 + ["Early AM"] * 2 + ["AM Peak"] * 3 + ["Morning"] * 3 + ["Mid-Day"] * 2 + ["Afternoon"] * 2 + ["PM Peak"] * 2 + ["After PM"] * 2 + ["Evening"] * 2 + ["Late"] * 2
        self.assertEqual([p.time_slice(h)[0] for h in range(24)], expected)
        row = p.normalize(synthetic_row(scheduled_start="2026-10-10T01:58:00+00:00",
                                        scheduled_end="2026-10-10T01:59:00+00:00"), self.cfg)[1]
        self.assertEqual(row["time_slice"], "Evening")

    def test_presence_and_movement_are_separate(self):
        empty = p.normalize(synthetic_row(), self.cfg)[1]
        unknown = p.normalize(synthetic_row(load=""), self.cfg)[1]
        present = p.normalize(synthetic_row(load="", boardings="1", movement="deadhead"), self.cfg)[1]
        self.assertEqual((empty["passenger_presence"], empty["movement"]), ("empty", "scheduled_service"))
        self.assertEqual(unknown["passenger_presence"], "unknown")
        self.assertIn("passengers_on_non_revenue_movement", present["qa_flags"])

    def test_unverified_boundaries_and_reverse_physical_phase(self):
        missing = p.normalize(synthetic_row(terminal_event="false"), p.config())[1]
        self.assertEqual(missing["phase"], "unclassified")
        self.cfg["phase_boundaries"].append({"route": "R162", "direction": "TEST_REVERSE", "from_stop_id": "TEST_A",
            "to_stop_id": "TEST_B", "phase": "destination_connection", "verified": True, "evidence": "Synthetic"})
        reverse = p.normalize(synthetic_row(direction="TEST_REVERSE", terminal_event="false"), self.cfg)[1]
        self.assertEqual(reverse["phase"], "destination_connection")
        with self.assertRaisesRegex(ValueError, "verified route/direction terminal"):
            p.normalize(synthetic_row(), p.config())

    def test_dedup_batch_and_overlap_provenance(self):
        first = self.load([synthetic_row(), synthetic_row()])
        self.assertEqual((first["inserted_pairs"], first["duplicate_rows"]), (1, 1))
        second = self.load([synthetic_row(), synthetic_row(route="R221")], "week2.csv")
        self.assertEqual((second["inserted_pairs"], second["duplicate_rows"]), (1, 1))
        self.assertEqual(self.load([synthetic_row(), synthetic_row()])["status"], "already_ingested")
        rows = p.aggregate(self.db)
        self.assertEqual(sum(r["pairs"] for r in rows), 2)
        self.assertEqual(len(next(r for r in rows if r["route"] == "R162")["source_batch_sha256"]), 2)

    def test_conflicts_and_invalid_rows_rollback_entire_batch(self):
        self.load([synthetic_row()])
        for bad in [synthetic_row(observed_miles="2"), synthetic_row(route="R999"), synthetic_row(load="NaN")]:
            with self.assertRaises(ValueError):
                self.load([synthetic_row(route="R221"), bad], "bad.csv")
            self.assertEqual(self.db.execute("SELECT count(*) FROM pairs").fetchone()[0], 1)
            self.assertEqual(self.db.execute("SELECT count(*) FROM batches").fetchone()[0], 1)

    def test_frozen_baseline_preserved_with_approved_revision_history(self):
        self.load([synthetic_row()])
        with self.db:
            first = p.freeze(self.db, "SYNTHETIC_TEST_APPROVER", "Synthetic approval")
        with self.assertRaisesRegex(ValueError, "Frozen baseline"):
            self.load([synthetic_row(route="R221")], "new.csv")
        self.assertEqual(p.baseline_digest(self.db)["sha256"], first["sha256"])
        self.load([synthetic_row(route="R221")], "new.csv", revision_approver="SYNTHETIC_TEST_APPROVER", revision_reason="Synthetic addition")
        latest = p.setting(self.db, "baseline_freeze")
        self.assertEqual(latest["previous"], first)
        self.assertEqual(latest["pairs"], 2)
        self.load([synthetic_row(actual_start="2026-10-10T20:58:00-05:00", actual_end="2026-10-10T20:59:00-05:00", service_date="2026-10-10")], "impact.csv")
        self.assertEqual(p.setting(self.db, "baseline_freeze"), latest)

    def test_changed_config_requires_rebuild(self):
        self.load([synthetic_row()])
        self.cfg["baseline_start"] = "2026-08-02"
        with self.assertRaisesRegex(ValueError, "Config changed"):
            self.load([synthetic_row(route="R221")], "new.csv")

    def test_frozen_baseline_integrity_detects_tampering(self):
        self.load([synthetic_row()])
        with self.db:
            p.freeze(self.db, "SYNTHETIC_TEST_APPROVER", "Synthetic")
            self.db.execute("DELETE FROM sources")
            self.db.execute("DELETE FROM pairs")
        with self.assertRaisesRegex(ValueError, "integrity"):
            p.aggregate(self.db)

    def test_export_archives_prior_results(self):
        self.load([synthetic_row()])
        output = self.root / "results.csv.gz"
        p.export(self.db, output)
        old_hash = p.sha(output)
        self.load([synthetic_row(route="R221")], "week2.csv")
        with patch.object(p, "PRIVATE", self.root):
            p.export(self.db, output)
        self.assertEqual(p.sha(self.root / "archive" / (old_hash + ".csv.gz")), old_hash)
        self.assertTrue((self.root / "archive" / (old_hash + ".csv.gz.qa.json")).exists())

    def test_summary_totals_deterministic_gzip_and_browser_parser(self):
        self.load([synthetic_row(route=route) for route in self.cfg["routes"]])
        a, b = self.root / "a.csv.gz", self.root / "b.csv.gz"
        report = p.export(self.db, a)
        p.export(self.db, b)
        self.assertEqual(a.read_bytes(), b.read_bytes())
        self.assertEqual(report["pairs"], 3)
        records = list(csv.DictReader(gzip.decompress(a.read_bytes()).decode().splitlines()))
        self.assertEqual(sum(int(r["pairs"]) for r in records), 3)
        self.assertAlmostEqual(sum(float(r["observed_miles"]) for r in records), 3.3)
        module = (p.ROOT / "site/model.mjs").as_uri()
        script = f'''import {{ readFileSync }} from 'node:fs';
import {{ parseCSV, distribution }} from {json.dumps(module)};
const stream = new Blob([readFileSync(process.argv[1])]).stream().pipeThrough(new DecompressionStream('gzip'));
const rows = parseCSV(await new Response(stream).text());
if (rows.length !== 3 || distribution(rows).onTime !== 3) throw new Error('Browser gzip/CSV totals differ');'''
        subprocess.run(["node", "--input-type=module", "-e", script, str(a)], check=True, capture_output=True)

    def approved_fixture(self):
        self.load([synthetic_row(route=route) for route in self.cfg["routes"]])
        with self.db:
            p.freeze(self.db, "SYNTHETIC_TEST_APPROVER", "Synthetic test only")
        data = self.root / "test.csv.gz"
        report = p.export(self.db, data)
        approval = self.root / "approval.json"
        review = {"approved": True, "approved_by": "SYNTHETIC_TEST_APPROVER", "approved_at": "2026-10-18",
            "evidence": "Synthetic unit test only; no agency release", "sha256": report["sha256"],
            "bytes": report["bytes"], "metrics": build_site.RELEASE_METRICS}
        approval.write_text(json.dumps(review))
        return data, approval

    def test_release_gate_exact_file_metrics_and_size(self):
        data, approval = self.approved_fixture()
        self.assertEqual(build_site.validate_release(data, approval)["pairs"], 3)
        with patch.object(build_site, "LIMIT", 1):
            with self.assertRaisesRegex(ValueError, "95 MiB"):
                build_site.validate_release(data, approval)
        review = json.loads(approval.read_text())
        review["metrics"] = []
        approval.write_text(json.dumps(review))
        with self.assertRaisesRegex(ValueError, "every displayed metric"):
            build_site.validate_release(data, approval)
        data.write_bytes(data.read_bytes() + b"x")
        with self.assertRaisesRegex(ValueError, "Exact dataset"):
            build_site.validate_release(data, approval)

    def test_size_limit_stops_export_and_preserves_previous(self):
        self.load([synthetic_row()])
        output = self.root / "previous.csv.gz"
        output.write_bytes(b"previous")
        with patch.object(p, "LIMIT", 1):
            with self.assertRaisesRegex(ValueError, "95 MiB"):
                p.export(self.db, output)
        self.assertEqual(output.read_bytes(), b"previous")

    def test_build_path_and_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "ServiceImpactModel" / "Commuter"
            self.assertEqual(build_site.build(target)["status"], "pending")
            self.assertFalse((target / "data").exists())
            data, approval = self.approved_fixture()
            metadata = self.release_metadata(data)
            manifest = build_site.build(target, data, approval, "test/ServiceImpactModel", "2026-10-18", metadata)
            self.assertEqual(manifest["dataset"], "https://api.github.com/repos/test/ServiceImpactModel/releases/assets/123")
            self.assertEqual(manifest["sha256"], p.sha(data))
            self.assertFalse((target / "data").exists())
            self.assertFalse(list(target.rglob("*.csv.gz")))
            self.assertLess((target / "manifest.json").stat().st_size, 4096)
            self.assertTrue((target / "model.mjs").exists())
            self.assertTrue((target / "data.mjs").exists())
            with self.assertRaisesRegex(ValueError, "Existing approved release preserved"):
                build_site.build(target)

    def release_metadata(self, data):
        identity = release.identity("test/ServiceImpactModel", "2026-10-18", p.sha(data))
        path = self.root / "github-release.json"
        path.write_text(json.dumps({"tag_name": identity["tag"], "draft": False, "prerelease": False,
            "html_url": f"https://github.com/test/ServiceImpactModel/releases/tag/{identity['tag']}",
            "assets": [{"name": identity["asset_name"], "id": 123, "size": data.stat().st_size,
                        "digest": "sha256:" + p.sha(data), "state": "uploaded",
                        "url": "https://api.github.com/repos/test/ServiceImpactModel/releases/assets/123",
                        "browser_download_url": identity["download_url"]}]}))
        return path

    def test_dated_release_preparation_preserves_snapshot(self):
        data, approval = self.approved_fixture()
        with patch.object(release, "PRIVATE", self.root):
            prepared = release.prepare(data, approval, "test/ServiceImpactModel", "2026-10-18")
            self.assertFalse(prepared["uploaded"])
            path = Path(prepared["prepared_file"])
            self.assertIn("2026-10-18", path.name)
            self.assertEqual(p.sha(path), p.sha(data))
            self.assertEqual(release.prepare(data, approval, "test/ServiceImpactModel", "2026-10-18"), prepared)
            path.write_bytes(b"prior snapshot preserved")
            with self.assertRaisesRegex(ValueError, "without overwriting"):
                release.prepare(data, approval, "test/ServiceImpactModel", "2026-10-18")
            self.assertEqual(path.read_bytes(), b"prior snapshot preserved")

    def test_manifest_refuses_mismatched_uploaded_release(self):
        data, approval = self.approved_fixture()
        path = self.release_metadata(data)
        original = path.read_text()
        for field, value in [("digest", "sha256:" + "0" * 64), ("size", 1), ("state", "new"),
                             ("url", "https://example.com/data"), ("id", True)]:
            metadata = json.loads(original)
            metadata["assets"][0][field] = value
            path.write_text(json.dumps(metadata))
            with self.assertRaises(ValueError):
                build_site.build(self.root / "site", data, approval, "test/ServiceImpactModel", "2026-10-18", path)
            self.assertFalse((self.root / "site").exists())
        path.write_text(original)
        with self.assertRaisesRegex(ValueError, "dated repository/tag"):
            build_site.build(self.root / "site", data, approval, "test/ServiceImpactModel", "2026-10-19", path)
        with self.assertRaisesRegex(ValueError, "Supply"):
            build_site.build(self.root / "site", data, approval)

    def test_site_refuses_legacy_data_directory_without_deleting_it(self):
        site = self.root / "site"
        (site / "data").mkdir(parents=True)
        legacy = site / "data" / "old.csv.gz"
        legacy.write_bytes(b"preserve")
        with self.assertRaisesRegex(ValueError, "code and a manifest only"):
            build_site.build(site)
        self.assertEqual(legacy.read_bytes(), b"preserve")

    def test_private_output_enforcement(self):
        with self.assertRaisesRegex(ValueError, "CMBT/private"):
            p.private_path(p.ROOT.parent / "Commuter" / "raw.csv")

    def test_utf16_schema_inspection_and_unknown_mappings(self):
        path = self.root / "source.csv"
        path.write_text("OPD_DATE\tROUTE\tTrip\n10/09/2026\t162\tTEST\n", encoding="utf-16")
        report = ivoms.inspect(path)
        self.assertEqual(report["columns"], ["OPD_DATE", "ROUTE", "Trip"])
        self.assertEqual(report["delimiter"], "tab")
        mapping = json.loads((p.ROOT / "ivoms_mapping.example.json").read_text())
        with self.assertRaisesRegex(ValueError, "vehicle_id"):
            ivoms.adapt(path, self.root / "canonical.csv", mapping, self.cfg)

    def test_service_day_rollover_and_dst(self):
        self.assertEqual(ivoms.service_time("10/09/2026", "01:00:00", 3), "2026-10-10T01:00:00-05:00")
        self.assertEqual(ivoms.service_time("10/09/2026", "25:00:00", 3), "2026-10-10T01:00:00-05:00")
        with self.assertRaisesRegex(ValueError, "DST"):
            ivoms.service_time("10/31/2026", "01:30:00", 3)

    def test_native_adapter_to_ingest_with_provenance_and_missing_presence(self):
        mapping = json.loads((p.ROOT / "ivoms_mapping.example.json").read_text())
        mapping.update(vehicle_id="TEST_VEHICLE_COLUMN", sequence="TEST_SEQUENCE_COLUMN")
        fields = [v for k, v in mapping.items() if k not in {"movement_values", "service_day_rollover_hour", "notes"}]
        source = self.root / "native.csv"
        with source.open("w", newline="", encoding="utf-16") as stream:
            writer = csv.DictWriter(stream, fields, delimiter="\t")
            writer.writeheader()
            for sequence, stop, clock in [(1, "TEST_A", "20:58:00"), (2, "TEST_B", "20:59:00")]:
                raw = {"service_date": "10/09/2026", "route": "162", "direction": "TEST_OUTBOUND",
                    "trip_id": "TEST_TRIP", "vehicle_id": "TEST_VEHICLE", "sequence": str(sequence),
                    "stop": f"Synthetic ({stop})", "scheduled_departure": clock, "scheduled_arrival": clock,
                    "actual_departure": clock, "actual_arrival": clock, "odometer": str(sequence),
                    "load": "" if sequence == 1 else "0", "boardings": "0", "alightings": "0", "pattern_type": "Service Journey"}
                writer.writerow({mapping[k]: v for k, v in raw.items()})
        canonical = self.root / "native-pairs.csv"
        report = ivoms.adapt(source, canonical, mapping, self.cfg)
        self.assertEqual(report["pairs"], 1)
        ingested = p.ingest(self.db, canonical, "2026-10-18", self.cfg)
        self.assertEqual(ingested["source_adapter"]["source_sha256"], p.sha(source))
        result = p.aggregate(self.db)[0]
        self.assertEqual(result["passenger_presence"], "unknown")
        self.assertEqual(result["observed_miles"], 1)
        self.assertEqual(sum(result["terminal_delay_histogram"].values()), 1)

    def test_missing_terminal_warning_and_duplicate_terminal_rejected(self):
        self.load([synthetic_row(terminal_event="false")])
        self.assertIn("missing_verified_terminal_for_trip", p.aggregate(self.db)[0]["qa_flags"])
        self.load([synthetic_row(from_sequence="2", to_sequence="3"),
                   synthetic_row(from_sequence="3", to_sequence="4")], "repeated_terminal.csv")
        with self.assertRaisesRegex(ValueError, "More than one terminal"):
            p.aggregate(self.db)


if __name__ == "__main__":
    unittest.main()
