"""Offline boundary/validation checks; no network or owner stores."""
import unittest
from snapshot_coinbase_daily import DAY, normalize


class SnapshotTests(unittest.TestCase):
    def test_filters_endpoint_spillover_and_deduplicates_boundaries(self):
        # Illustrative synthetic prices, not FET observations.
        row = [DAY, 1, 3, 2, 2.5, 10]
        result = normalize([[0, 1, 3, 2, 2, 10], row, row, [2 * DAY, 1, 3, 2, 2, 10]], DAY, 2 * DAY)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["end"], 2 * DAY)
        self.assertTrue(result[0]["complete"])

    def test_conflicting_boundaries_fail(self):
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            normalize([[DAY, 1, 3, 2, 2, 10], [DAY, 1, 3, 2, 2.5, 10]], DAY, 2 * DAY)

    def test_invalid_data_fails_instead_of_becoming_an_empty_period(self):
        for row in [[DAY, 3, 1, 2, 2, 10], [DAY, 1, 3, 2, float("nan"), 10],
                    [DAY + 1, 1, 3, 2, 2, 10], [DAY, 1, 3, 2, 2, -1]]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                normalize([row], DAY, 2 * DAY)

    def test_gaps_are_left_unfilled(self):
        result = normalize([[DAY, 1, 3, 2, 2, 10], [3 * DAY, 1, 3, 2, 2, 10]], DAY, 4 * DAY)
        self.assertEqual([r["start"] for r in result], [DAY, 3 * DAY])


if __name__ == "__main__":
    unittest.main()
