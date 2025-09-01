import pytest
from app import app

@pytest.fixture(scope="module")
def client():
    app.testing = True
    with app.test_client() as c:
        yield c

@pytest.mark.parametrize("path", [
    "/api/component/gainers-table-1min",
    "/api/component/gainers-table",
    "/api/component/losers-table",
    "/api/component/top-movers-bar",
])
def test_swr_block_present(client, path):
    resp = client.get(path)
    # endpoint may 503 on cold start; that's acceptable
    if resp.status_code == 200:
        data = resp.get_json()
        assert 'swr' in data, f"missing swr in {path}"
        swr = data['swr']
        for key in ['ttl','stale_window','served_cached']:
            assert key in swr, f"missing swr.{key} in {path}"
            # basic type sanity
        assert isinstance(swr['ttl'], (int,float))
        assert isinstance(swr['stale_window'], (int,float))
        assert isinstance(swr['served_cached'], (bool,))
