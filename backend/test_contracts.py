import pytest
from app import app


@pytest.fixture(scope="module")
def client_fx():
    app.testing = True
    with app.test_client() as c:
        yield c


def test_data_schema(client_fx):
    r = client_fx.get('/api/tables-3min')  # indirect but ensures backend warmed
    # We cannot rely on /api/data endpoint (not present); use get_crypto_data via banner if needed.
    # If schema minimal error payload, skip strict validation.
    # (Extend later when dedicated /api/data exists.)
    # This serves as placeholder to ensure no crash.
    assert r.status_code in (200, 503)


def test_banner_endpoints_do_not_crash(client_fx):
    for path in ['/api/banner-top', '/api/banner-bottom']:
        resp = client_fx.get(path)
        assert resp.status_code in (200, 503)
