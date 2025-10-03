import time
import types
import pytest
from unittest.mock import patch, MagicMock

# Import module under test
import price_fetch

@pytest.fixture(autouse=True)
def reset_state():
    # Reset module-level caches/rate to deterministic baseline each test
    price_fetch._products_cache.update({'items': None, 'fetched_at': 0.0, 'ttl': price_fetch.PRODUCTS_CACHE_TTL})
    price_fetch._last_snapshot.update({'data': {}, 'fetched_at': 0.0})
    price_fetch._rate.update({'failures':0,'next':0.0,'last_error':None})
    yield


def _mk_products(ids):
    return [
        {"id": sym, "quote_currency": "USD", "status": "online"} for sym in ids
    ]

@patch('requests.get')
def test_fetch_prices_basic_success(mock_get):
    # First call returns product list
    products = _mk_products(['BTC-USD','ETH-USD'])
    prod_resp = MagicMock(status_code=200, json=lambda: products)
    # Ticker responses
    btc_resp = MagicMock(status_code=200, json=lambda: {"price": "50000"})
    eth_resp = MagicMock(status_code=200, json=lambda: {"price": "4000"})
    mock_get.side_effect = [prod_resp, btc_resp, eth_resp]

    prices = price_fetch.fetch_prices()
    assert prices['BTC-USD'] == 50000.0
    assert prices['ETH-USD'] == 4000.0
    # Ensure snapshot stored
    assert price_fetch._last_snapshot['data']

@patch('requests.get')
def test_fetch_prices_rate_limit_uses_snapshot(mock_get):
    # Seed snapshot
    price_fetch._last_snapshot['data'] = {'BTC-USD': 100.0}
    price_fetch._last_snapshot['fetched_at'] = time.time()
    # Force backoff window active
    price_fetch._rate['next'] = time.time() + 5
    # Should short-circuit without calling products endpoint
    prices = price_fetch.fetch_prices()
    assert prices == {'BTC-USD': 100.0}
    mock_get.assert_not_called()

@patch('requests.get')
def test_fetch_prices_rollback_to_snapshot_on_fail(mock_get):
    # Successful first retrieval to build snapshot
    products = _mk_products(['BTC-USD'])
    prod_resp = MagicMock(status_code=200, json=lambda: products)
    btc_resp = MagicMock(status_code=200, json=lambda: {"price": "123"})
    mock_get.side_effect = [prod_resp, btc_resp]
    first = price_fetch.fetch_prices()
    assert first['BTC-USD'] == 123.0

    # Now simulate failure: products 500
    fail_resp = MagicMock(status_code=500, json=lambda: {})
    mock_get.side_effect = [fail_resp]
    recovered = price_fetch.fetch_prices()
    assert recovered['BTC-USD'] == 123.0

@patch('requests.get')
def test_fetch_prices_products_cache(mock_get):
    # Initial product load
    products = _mk_products(['BTC-USD'])
    prod_resp = MagicMock(status_code=200, json=lambda: products)
    btc_resp = MagicMock(status_code=200, json=lambda: {"price": "111"})
    mock_get.side_effect = [prod_resp, btc_resp]
    price_fetch.fetch_prices()
    # Second call: provide only ticker (should not invoke products endpoint again)
    btc_resp2 = MagicMock(status_code=200, json=lambda: {"price": "112"})
    mock_get.side_effect = [btc_resp2]
    prices2 = price_fetch.fetch_prices()
    assert prices2['BTC-USD'] in (111.0, 112.0)  # could reuse snapshot if concurrency limited
    # Ensure products endpoint called only once
    product_calls = [c for c in mock_get.call_args_list if 'products' in c[0][0] and c[0][0].endswith('/products')]
    assert len(product_calls) == 1
