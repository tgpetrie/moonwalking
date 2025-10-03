import pytest
from app import app

@pytest.fixture(scope="module")
def client():
    app.testing = True
    with app.test_client() as c:
        yield c

def test_metrics_contains_circuit_breaker_block(client):
    resp = client.get('/api/metrics')
    assert resp.status_code == 200
    data = resp.get_json()
    # circuit_breaker should be present if price_fetch metrics resolved
    cb = data.get('circuit_breaker')
    assert cb is not None, f"circuit_breaker block missing in metrics JSON: keys={list(data.keys())}"
    for k in ('state','failures','open_until','is_open','is_half_open'):
        assert k in cb, f"Missing key {k} in circuit_breaker block: {cb}"