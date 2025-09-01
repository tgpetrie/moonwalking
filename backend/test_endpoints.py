import json
import pytest
from jsonschema import validate

from app import app
from schemas import DATA_SCHEMA, SIGNALS_SCHEMA

@pytest.fixture(scope="module")
def client():
    app.testing = True
    with app.test_client() as c:
        yield c

def _assert_keys(data, keys):
    for k in keys:
        assert k in data, f"missing key {k} in {data.keys()}"

@pytest.mark.parametrize("path,root_keys", [
    ("/api/banner-top", ["items","count","limit","age_seconds","stale","ts"]),
    ("/api/banner-bottom", ["items","count","limit","age_seconds","stale","ts"]),
])
def test_banner_endpoints_shape(client, path, root_keys):
    resp = client.get(path)
    assert resp.status_code in (200,503)
    data = resp.get_json()
    assert isinstance(data, dict)
    if resp.status_code == 200:
        _assert_keys(data, root_keys)
        assert isinstance(data["items"], list)


def test_tables_3min_endpoint_shape(client):
    resp = client.get("/api/tables-3min")
    assert resp.status_code in (200,503)
    data = resp.get_json()
    assert isinstance(data, dict)
    if resp.status_code == 200 and 'error' not in data:
        _assert_keys(data, ["interval_minutes","gainers","losers","counts","limit","ts"]) 
        assert isinstance(data["gainers"], list)
        assert isinstance(data["losers"], list)


def test_health_endpoint_contract(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    _assert_keys(data, ["status","uptime_seconds","errors_5xx"])
    assert data["status"] == 'ok'
    assert isinstance(data["uptime_seconds"], (int,float))

def test_metrics_endpoint_contract(client):
    resp = client.get("/api/metrics")
    assert resp.status_code == 200
    data = resp.get_json()
    _assert_keys(data, ["status","uptime_seconds","errors_5xx"])
    # price_fetch metrics optional but if present ensure shape
    pf = data.get("price_fetch")
    if pf:
        for k in ["total_calls","products_cache_hits","snapshot_served"]:
            assert k in pf

def test_signals_schema_example():
    sample = [
        {"symbol":"BTC-USD","direction":"up","score":1.2,"ts": 1234567890}
    ]
    validate(sample, SIGNALS_SCHEMA)
