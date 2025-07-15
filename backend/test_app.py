from unittest.mock import patch
import sys
import types
import unittest

# Import missing functions from app.py
from app import calculate_interval_changes, format_crypto_data, process_product_data, price_history

# Update mocking strategy
import flask
import flask_socketio

class MockFlask:
    def __init__(self, *args, **kwargs):
        pass

class MockSocketIO:
    def __init__(self, *args, **kwargs):
        pass

flask.Flask = MockFlask
flask_socketio.SocketIO = MockSocketIO


class TestCalculateIntervalChanges(unittest.TestCase):
    def setUp(self):
        price_history.clear()

    @patch('app.time.time')
    def test_calculate_interval_changes(self, mock_time):
        from app import CONFIG
        CONFIG['INTERVAL_MINUTES'] = 3
        mock_time.side_effect = [1000.0, 1180.0]

        initial_data = {'BTC-USD': 100.0}
        # First call to set initial prices
        calculate_interval_changes(initial_data)

        # Second call calculates change over the interval
        result2 = calculate_interval_changes({'BTC-USD': 110.0})

        self.assertEqual(len(result2), 1)
        coin = result2[0]
        self.assertEqual(coin['symbol'], 'BTC-USD')
        self.assertEqual(coin['current_price'], 110.0)
        self.assertEqual(coin['initial_price_3min'], 100.0)
        self.assertAlmostEqual(coin['price_change_percentage_3min'], 10.0)
        self.assertAlmostEqual(coin['actual_interval_minutes'], 3.0)


class TestFormatCryptoData(unittest.TestCase):
    def test_format_crypto_data(self):
        crypto_data = [
              {
                'symbol': 'BTC-USD',
                'current_price': 110.0,
                'initial_price_3min': 100.0,
                'price_change_percentage_3min': 10.0,
                'actual_interval_minutes': 3.0,
            }
        ]  
         
        result = format_crypto_data(crypto_data)
        expected = [
    {
        'symbol': 'BTC-USD',
        'current': 110.0,
        'initial_3min': 100.0,
        'gain': 10.0,
        'interval_minutes': 3.0,
    }
]
        self.assertEqual(result, expected)


class TestProcessProductData(unittest.TestCase):
    def test_process_product_data(self):
        sample_data = [
            {"id": "BTC-USD", "base_currency": "BTC", "quote_currency": "USD"},
            {"id": "ETH-USD", "base_currency": "ETH", "quote_currency": "USD"},
        ]
        stats_data = {
            "BTC-USD": {"volume": 1000000},
            "ETH-USD": {"volume": 500000},
        }
        ticker_data = {
            "BTC-USD": {"price": 30000},
            "ETH-USD": {"price": 2000},
        }
        expected_output = [
            {"symbol": "BTC-USD", "base": "BTC", "quote": "USD", "volume": 1000000, "price": 30000},
            {"symbol": "ETH-USD", "base": "ETH", "quote": "USD", "volume": 500000, "price": 2000},
        ]
        result = process_product_data(sample_data, stats_data, ticker_data)
        self.assertEqual(result, expected_output)

if __name__ == '__main__':
    unittest.main()