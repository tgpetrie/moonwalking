import os
import json
import pytest

from app import app

@pytest.fixture
def client(monkeypatch):
    # Ensure seeding is enabled via env
    monkeypatch.setenv('USE_1MIN_SEED', '1')
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c

def test_gainers_table_1min_seeded(client):
    resp = client.get('/api/component/gainers-table-1min')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)
    # seeded marker must exist when USE_1MIN_SEED is set and use canonical marker
    assert data.get('swr', {}).get('source') == 'fixture-seed'
    assert data.get('swr', {}).get('seed') is True
    assert data.get('count', 0) > 0
    assert isinstance(data.get('data'), list)
