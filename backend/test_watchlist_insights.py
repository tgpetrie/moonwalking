import unittest
from watchlist_insights import Memory, smart_watchlist_insights


class TestSmartWatchlistInsights(unittest.TestCase):
    def test_drop_alert(self):
        mem = Memory()
        mem.add("User added BTC to their watchlist at $100")
        mem.add("BTC is now at $94 (-6.00%)")
        result = smart_watchlist_insights(mem)
        self.assertIn("has dropped", result)

    def test_large_cap_suggestion(self):
        mem = Memory()
        mem.add("User added BTC to their watchlist at $100")
        mem.add("User added ETH to their watchlist at $200")
        mem.add("User added SOL to their watchlist at $30")
        mem.add("BTC is now at $110 (10.00%)")
        mem.add("ETH is now at $210 (5.00%)")
        mem.add("SOL is now at $35 (16.00%)")
        result = smart_watchlist_insights(mem)
        self.assertIn("large-cap tokens", result)


if __name__ == '__main__':
    unittest.main()
