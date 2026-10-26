"""A simulated paginated download must respect the documented shared IP budget."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "scoring_experiment"))
import funding_fetch


class FundingFetchBudgetTests(unittest.TestCase):
    def test_full_history_pages_fit_within_1200_weight_per_minute(self):
        now = [0.0]
        calls = []

        def post(body):
            page = len(calls)
            n = 500 if page < 30 else 1
            # Documented weight: base 20 plus one per 20 returned items.
            weight = 20 + (n + 19) // 20
            calls.append((now[0], weight))
            rows = [{"coin": "X", "time": 1704067200000 + (page * 500 + i) * 3600000,
                     "fundingRate": "0", "premium": "0"} for i in range(n)]
            return json.dumps(rows).encode(), 200

        def sleep(seconds):
            now[0] += seconds

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(funding_fetch, "post", side_effect=post), patch.object(funding_fetch.time, "sleep", side_effect=sleep):
                funding_fetch.fetch_coin("X", Path(tmp), lambda _: None)
        self.assertEqual(len(calls), 31)
        largest_window = max(sum(weight for t, weight in calls if 0 <= end - t < 60) for end, _ in calls)
        self.assertLessEqual(largest_window, 1200)


if __name__ == "__main__":
    unittest.main()
