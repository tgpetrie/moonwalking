"""Data-integrity checks for the offline scoring input checkpoint."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.scoring_data.freeze_daily_panel import DAY, compare_hourly, daily_rows, freeze, verify


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="moonwalking-checkpoint-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.destination = self.root / "checkpoint"
        self.candidate_map = self.root / "candidates.json"
        self.candidate_map.write_text(json.dumps({"BTC": {"hl_name": "BTC", "first_ts": 0}}))
        self.row = [0, 90, 110, 95, 100, 20]
        self.write_product([self.row])
        (self.source / "products.json").write_text(json.dumps([{"id": "BTC-USD"}]))
        (self.source / "manifest.json").write_text(json.dumps({"floor": "1970-01-01T00:00:00Z", "end": "1970-01-04T00:00:00Z"}))
        self.archive = self.root / "archive.sqlite"
        with closing(sqlite3.connect(self.archive)) as db, db:
            db.execute("CREATE TABLE candles (product_id TEXT, granularity INTEGER, ts INTEGER, close REAL)")
            db.executemany("INSERT INTO candles VALUES ('BTC-USD',3600,?,100)", [(h * 3600,) for h in range(24)])

    def write_product(self, rows):
        (self.source / "BTC-USD.json").write_text(json.dumps({
            "product_id": "BTC-USD", "granularity": DAY, "status": "online",
            "windows": [{"http_status": 200, "response": rows}],
        }))

    def test_freeze_preserves_source_and_case_conflicting_manifests(self):
        before = {p.name: p.read_bytes() for p in self.source.iterdir()}
        result = freeze(self.source, self.destination, self.archive, self.candidate_map)
        self.assertEqual(result["crosscheck_acceptance"], "pass")
        self.assertEqual(result["raw_files_verified"], 3)
        self.assertEqual(result["total_usable_daily_candles"], 1)
        self.assertEqual(result["provider_identity_status"], "ticker_candidates_only_not_identity_verified")
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.source.iterdir()})
        self.assertEqual((self.destination / "raw/manifest.json").read_bytes(), before["manifest.json"])
        self.assertTrue((self.destination / "MANIFEST.json").is_file())

    def test_corrupted_copy_is_detected(self):
        freeze(self.source, self.destination, self.archive, self.candidate_map)
        (self.destination / "raw/BTC-USD.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "Hash or size differs"):
            verify(self.destination)

    def test_conflicting_duplicates_are_excluded_instead_of_selected(self):
        changed = self.row.copy()
        changed[4] = 101
        self.write_product([self.row, self.row, changed, [DAY, 90, 110, 95, 100, 20]])
        rows, report = daily_rows(self.source / "BTC-USD.json", 0, 3 * DAY)
        self.assertNotIn(0, rows)
        self.assertIn(DAY, rows)
        self.assertEqual(report["duplicate_rows"], 2)
        self.assertEqual(report["conflicting_days_excluded"], 1)

    def test_partial_days_are_not_treated_as_daily_close_evidence(self):
        with closing(sqlite3.connect(self.archive)) as db, db:
            db.execute("DELETE FROM candles WHERE ts=0")
        result = compare_hourly({"BTC-USD": {0: self.row}}, self.archive, 0.001)
        self.assertEqual(result["compared_complete_days"], 0)
        self.assertEqual(result["partial_hourly_days_not_compared"], 1)
        self.assertIsNone(result["match_fraction"])

    def test_gaps_and_out_of_bounds_candles_are_not_filled(self):
        self.write_product([self.row, [2 * DAY, 90, 110, 95, 100, 20], [3 * DAY, 90, 110, 95, 100, 20]])
        rows, report = daily_rows(self.source / "BTC-USD.json", 0, 3 * DAY)
        self.assertEqual(len(rows), 2)
        self.assertNotIn(DAY, rows)
        self.assertEqual(report["missing_days_inside_span"], 1)
        self.assertEqual(report["out_of_bounds_rows_excluded"], 1)

    def test_existing_checkpoint_cannot_be_overwritten(self):
        freeze(self.source, self.destination, self.archive, self.candidate_map)
        with self.assertRaises(FileExistsError):
            freeze(self.source, self.destination, self.archive, self.candidate_map)

    def test_nested_destination_is_refused(self):
        with self.assertRaisesRegex(ValueError, "separate trees"):
            freeze(self.source, self.source / "copy", self.archive, self.candidate_map)

    def test_identity_mismatch_is_refused(self):
        path = self.source / "BTC-USD.json"
        doc = json.loads(path.read_text())
        doc["product_id"] = "BCH-USD"
        path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, "Identity/granularity mismatch"):
            daily_rows(path, 0, 3 * DAY)


if __name__ == "__main__":
    unittest.main()
