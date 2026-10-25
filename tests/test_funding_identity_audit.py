"""Research mapping QA: units, end-time alignment, and incomplete price evidence."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "scoring_data"))
import audit_funding_identity as audit


def fixture(factor=1):
    start = 1704067200000
    values = [1.0, 1.3, 0.9, 1.6, 1.1, 1.8, 1.5]
    bars, coinbase = [], {}
    for i, price in enumerate(values):
        t = start + i * audit.BAR_MS
        end = t + audit.BAR_MS - 1
        bars.append({"t": t, "T": end, "c": str(price * factor), "v": "100", "n": 10})
        coinbase[(end // audit.DAY_MS) * 86400] = [0, price, price, price, price, 100]
    return bars, coinbase


class FundingIdentityTests(unittest.TestCase):
    def test_consistent_market_prices_pass(self):
        bars, cb = fixture()
        result = audit.compare(bars, cb, 1, bars[-1]["T"] + 1)
        self.assertTrue(result["screen_pass"])
        self.assertAlmostEqual(result["return_correlation"], 1.0)

    def test_k_contract_requires_explicit_price_conversion(self):
        bars, cb = fixture(1000)
        self.assertTrue(audit.compare(bars, cb, 1000, bars[-1]["T"] + 1)["screen_pass"])
        bad = audit.compare(bars, cb, 1, bars[-1]["T"] + 1)
        self.assertFalse(bad["screen_pass"])
        self.assertEqual(bad["status"], "hold_price_correspondence_failed")

    def test_unfinished_and_zero_trade_bars_are_not_identity_evidence(self):
        bars, cb = fixture()
        bars[0]["n"] = 0
        bars[1]["v"] = "0"
        result = audit.compare(bars, cb, 1, bars[-1]["t"])
        self.assertEqual(result["common_complete_closes"], 4)
        self.assertEqual(result["dropped_bars"]["zero_trade_or_volume_bar"], 2)
        self.assertEqual(result["dropped_bars"]["ends_after_frozen_panel"], 1)
        self.assertFalse(result["screen_pass"])

    def test_missing_close_does_not_create_a_return_across_the_gap(self):
        bars, cb = fixture()
        del cb[(bars[3]["T"] // audit.DAY_MS) * 86400]
        result = audit.compare(bars, cb, 1, bars[-1]["T"] + 1)
        self.assertEqual(result["common_complete_closes"], 6)
        self.assertEqual(result["consecutive_return_pairs"], 4)

    def test_delisted_final_window_is_excluded(self):
        bars, cb = fixture()
        result = audit.compare(bars, cb, 1, bars[-1]["T"] + 1, delisted=True)
        self.assertEqual(result["common_complete_closes"], 6)
        self.assertEqual(result["dropped_bars"]["possibly_partial_delisting_window"], 1)

    def test_no_overlap_stays_unresolved(self):
        bars, cb = fixture()
        result = audit.compare(bars, {}, 1, bars[-1]["T"] + 1)
        self.assertFalse(result["screen_pass"])
        self.assertIsNone(result["return_correlation"])
        self.assertEqual(result["common_complete_closes"], 0)


if __name__ == "__main__":
    unittest.main()
