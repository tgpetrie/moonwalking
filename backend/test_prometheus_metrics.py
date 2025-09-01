import pytest
from app import app

@pytest.fixture(scope="module")
def client():
    app.testing = True
    with app.test_client() as c:
        yield c

def test_prometheus_swr_metrics_present(client):
    # Optionally touch an SWR endpoint to ensure decorator initialized
    client.get('/api/component/gainers-table-1min')
    resp = client.get('/metrics.prom')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Core SWR metric names we expect
    expected = [
        'swr_gainers_1m_cache_age_seconds',
        'swr_gainers_1m_calls_total',
        'swr_gainers_3m_calls_total',
        'swr_losers_3m_calls_total',
        'swr_top_movers_bar_calls_total'
    ]
    for name in expected:
        assert name in body, f"Missing Prometheus metric line for {name}\nBody snippet: {body[:400]}"

def test_prometheus_circuit_breaker_metrics_present(client):
    resp = client.get('/metrics.prom')
    body = resp.get_data(as_text=True)
    # Breaker metrics should always be exported once price_fetch metrics accessed
    expected_cb = [
        'price_fetch_circuit_breaker_state',
        'price_fetch_circuit_breaker_failures',
    'price_fetch_circuit_breaker_open_until_epoch',
    'price_fetch_circuit_breaker_is_open',
    'price_fetch_circuit_breaker_is_half_open'
    ]
    for name in expected_cb:
        assert name in body, f"Missing circuit breaker metric {name}\nBody snippet: {body[:400]}"

def test_prometheus_price_fetch_advanced_metrics_present(client):
    resp = client.get('/metrics.prom')
    body = resp.get_data(as_text=True)
    advanced = [
        'price_fetch_p95_fetch_duration_ms',
        'price_fetch_error_rate_percent',
        'price_fetch_backoff_seconds_remaining'
    ]
    for name in advanced:
        assert name in body, f"Missing advanced price fetch metric {name}\nBody snippet: {body[:400]}"
