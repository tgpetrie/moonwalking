import pytest
from app import app

@pytest.fixture(scope="module")
def client():
    app.testing = True
    with app.test_client() as c:
        yield c

def test_openapi_contains_thresholds_path(client):
    resp = client.get('/api/openapi.json')
    assert resp.status_code == 200
    spec = resp.get_json()
    assert '/api/thresholds' in spec['paths']
    thresholds_path = spec['paths']['/api/thresholds']
    assert 'get' in thresholds_path and 'post' in thresholds_path
    get_resp = thresholds_path['get']['responses']['200']
    assert 'application/json' in get_resp['content']


def test_thresholds_post_invalid_body_returns_400(client):
    # invalid because ratios must be >0
    resp = client.post('/api/thresholds', json={'pump_thrust_confirm_ratio_min': 0})
    assert resp.status_code == 400
    body = resp.get_json()
    assert 'errors' in body and 'pump_thrust_confirm_ratio_min' in body['errors']


def test_thresholds_post_non_numeric_returns_400(client):
    resp = client.post('/api/thresholds', json={'pump_thrust_confirm_ratio_min': 'abc'})
    # Should be rejected completely -> 400
    assert resp.status_code == 400
    body = resp.get_json()
    assert body['applied'] == {}
    assert 'pump_thrust_confirm_ratio_min' in body['errors']
