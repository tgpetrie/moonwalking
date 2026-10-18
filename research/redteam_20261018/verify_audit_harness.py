"""NEW COPY/ADAPTATION of test_resolution_costs.py; illustrative unit fixtures only.
Actual audit and endpoint evidence are checked separately from these fixtures.
"""

import datetime, hashlib, importlib.util, json, pathlib, sqlite3, subprocess, unittest
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent
BASE = pathlib.Path(".runtime/redteam_20261018")


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A = load("audit_experiments")
F = load("public_source_fetcher")


class AuditChecks(unittest.TestCase):
    def test_copy_path_guard(self):
        with self.assertRaises(ValueError):
            A.ro("../outside.sqlite")

    def test_database_is_read_only(self):
        db = A.ro("recon.sqlite")
        with self.assertRaises(sqlite3.OperationalError):
            db.execute("CREATE TABLE should_never_exist (x)")
        db.close()

    def test_stored_R_cost_matches_source_assumption(self):
        db = A.ro("recon.sqlite")
        error = db.execute(
            "SELECT MAX(ABS(((CASE WHEN res21=1 THEN 2 WHEN res21=-1 THEN -1 ELSE MIN(2,MAX(-1,r24)) END)-netR21)*atr_pct-0.002)) FROM recon"
        ).fetchone()[0]
        db.close()
        self.assertLess(error, 1e-10)

    def test_frozen_sources_match_manifest(self):
        for r in json.loads((BASE / "results_final/source_manifest.json").read_text()):
            self.assertEqual(
                hashlib.sha256((ROOT / r["file"]).read_bytes()).hexdigest(), r["sha256"]
            )

    def test_data_copies_remain_identical(self):
        for r in json.loads((BASE / "copy_manifest.json").read_text()):
            with open(r["copy"], "rb") as f:
                digest = hashlib.file_digest(f, "sha256").hexdigest()
            self.assertEqual(digest, r["sha256"])

    def test_illustrative_dedupe_order_dependence(self):
        # Synthetic rows, not measured market effects.
        a = ("X", 10, "L", "up", 0.01, 0, 0, 0, 0, 0, 70)
        b = ("X", 20, "L", "up", 0.01, 0, 0, 0, 0, 0, 90)
        self.assertEqual(A.dedupe([a, b], "earliest")[0][1], 10)
        self.assertEqual(A.dedupe([a, b], "latest")[0][1], 20)
        self.assertEqual(A.dedupe([a, b], "max_confidence")[0][10], 90)

    def test_empty_control_window_is_unmatched(self):
        r = ("X", 0, "L", "up", 0.01, 0, 0, 0, 0, 0, 70)
        pool = {("X", "up"): np.array([[10000000, 0.01, 1, 0, 0, 0, 0]])}
        matched, unmatched = A.match([r], pool, exclude_hours=set())
        self.assertEqual(matched, [])
        self.assertEqual(len(unmatched), 1)

    def test_block_bootstrap_keeps_weighted_point_estimate(self):
        # Illustrative unequal block sizes: weighted mean 0.1, equal-week mean 5.
        t = np.array([0] * 99 + [7 * 86400])
        x = np.array([0] * 99 + [10.0])
        self.assertAlmostEqual(A.boot(x, t)["mean"], 0.1)
        self.assertEqual(A.boot(x, t)["blocks"], 2)

    def test_public_private_route_guard(self):
        with self.assertRaises(ValueError):
            F.fetch("bad", "www.okx.com", "/api/v5/account/balance")
        with self.assertRaises(ValueError):
            F.fetch("bad", "example.com", "/")

    def test_archive_url_guard(self):
        with self.assertRaises(ValueError):
            F.archive_sample("bad", "https://example.com/private.zip", "zip")

    def test_requests_are_spaced(self):
        for directory in ("public_samples_initial", "public_samples_history"):
            for line in (BASE / directory / "requests.jsonl").read_text().splitlines():
                row = json.loads(line)
                gap = row["request_start_gap_seconds"]
                if gap is not None:
                    self.assertGreaterEqual(gap, 1)

    def test_copied_database_has_no_added_tables(self):
        d = A.ro("recon.sqlite")
        names = [
            r[0] for r in d.execute("select name from sqlite_master where type='table'")
        ]
        d.close()
        self.assertEqual(names, ["recon"])

    def test_working_diff_has_no_original_edits(self):
        result = subprocess.run(
            ["git", "diff", "--name-status", "50c8d873"],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.splitlines():
            status, path = line.split("\t", 1)
            self.assertEqual(status, "A")
            self.assertTrue(path.startswith("research/redteam_20261018/"))


if __name__ == "__main__":
    unittest.main(argv=["audit-checks"], verbosity=2)
