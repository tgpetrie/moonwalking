import json
import os
import pytest
from app import app, THRESHOLDS

@pytest.fixture(scope="module")
def client():
    app.testing = True
    # Ensure a temp thresholds file path (avoid clobbering real file)
    # Redirect to a temp file inside test directory
    tmp_path = os.path.join(os.path.dirname(__file__), 'thresholds_test.json')
    # If existing from prior run, remove
    try:
        if os.path.isfile(tmp_path):
            os.remove(tmp_path)
    except Exception:
        pass
    # Monkeypatch the module-level file variable
    import app as app_module
    app_module._THRESHOLDS_FILE = tmp_path
    with app.test_client() as c:
        yield c
    # Cleanup
    try:
        if os.path.isfile(tmp_path):
            os.remove(tmp_path)
    except Exception:
        pass

def test_get_thresholds(client):
    resp = client.get('/api/thresholds')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'thresholds' in data
    # Ensure all known keys present
    for k in THRESHOLDS.keys():
        assert k in data['thresholds']


def test_post_valid_update_persists_and_returns_200_or_207(client):
    payload = {
        'pump_thrust_confirm_ratio_min': THRESHOLDS['pump_thrust_confirm_ratio_min'] + 0.05
    }
    resp = client.post('/api/thresholds', json=payload)
    assert resp.status_code in (200,207)
    body = resp.get_json()
    assert 'applied' in body and 'errors' in body
    assert 'pump_thrust_confirm_ratio_min' in body['applied']
    # Verify in-memory updated
    assert THRESHOLDS['pump_thrust_confirm_ratio_min'] == payload['pump_thrust_confirm_ratio_min']
    # Verify persisted file reflects change
    import app as app_module
    with open(app_module._THRESHOLDS_FILE,'r') as f:
        persisted = json.load(f)
    assert float(persisted['pump_thrust_confirm_ratio_min']) == payload['pump_thrust_confirm_ratio_min']


def test_post_mixed_valid_and_invalid_returns_207(client):
    payload = {
        'narrowing_vol_sd_max': THRESHOLDS['narrowing_vol_sd_max'] * 1.1,
        'unknown_key_xyz': 123,
        'accel_fade_min_thrust_seconds': -5  # invalid (<0)
    }
    resp = client.post('/api/thresholds', json=payload)
    # Should apply first key, reject others -> 207
    assert resp.status_code == 207
    body = resp.get_json()
    assert 'applied' in body and 'errors' in body
    assert 'narrowing_vol_sd_max' in body['applied']
    assert 'unknown_key_xyz' in body['errors']
    assert 'accel_fade_min_thrust_seconds' in body['errors']


def test_post_all_invalid_returns_400(client):
    payload = {
        'pump_thrust_confirm_ratio_min': -1,  # invalid ratio
        'narrowing_vol_sd_max': 0,            # invalid sd max
    }
    resp = client.post('/api/thresholds', json=payload)
    assert resp.status_code == 400
    body = resp.get_json()
    assert body['applied'] == {}
    assert set(body['errors'].keys()) == set(payload.keys())


def test_prometheus_threshold_metrics_exposed(client):
    resp = client.get('/metrics.prom')
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    # Look for at least one threshold gauge line
    assert 'threshold_pump_thrust_confirm_ratio_min' in text
    assert 'threshold_narrowing_vol_sd_max' in text
