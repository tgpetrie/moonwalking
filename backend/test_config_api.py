import pytest
from app import app, CONFIG

@pytest.fixture(scope='module')
def client():
    app.testing = True
    with app.test_client() as c:
        yield c

def test_get_config(client):
    r = client.get('/api/config')
    assert r.status_code == 200
    data = r.get_json()
    assert 'config' in data and 'limits' in data
    assert data['config']['CACHE_TTL'] == CONFIG['CACHE_TTL']


def test_config_update_valid_partial(client):
    original = CONFIG['CACHE_TTL']
    payload = {'CACHE_TTL': original + 5}
    r = client.post('/api/config', json=payload)
    assert r.status_code in (200,207)
    body = r.get_json()
    assert 'applied' in body and 'errors' in body
    assert body['applied']['CACHE_TTL'] == original + 5
    assert CONFIG['CACHE_TTL'] == original + 5


def test_config_update_out_of_bounds(client):
    # MIN_CHANGE_THRESHOLD max=1000.0; push beyond to trigger error
    r = client.post('/api/config', json={'MIN_CHANGE_THRESHOLD': 2000})
    assert r.status_code == 400
    body = r.get_json()
    assert 'MIN_CHANGE_THRESHOLD' in body['errors']


def test_config_update_invalid_type(client):
    r = client.post('/api/config', json={'API_TIMEOUT': 'notint'})
    assert r.status_code == 400
    body = r.get_json()
    assert 'API_TIMEOUT' in body['errors']


def test_config_update_unknown_key(client):
    r = client.post('/api/config', json={'UNKNOWN_SETTING': 123})
    assert r.status_code == 400
    body = r.get_json()
    assert 'UNKNOWN_SETTING' in body['errors']
