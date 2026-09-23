import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as backend_app


@pytest.fixture
def api():
    return backend_app.app.test_client()


def test_rejects_invalid_symbol(api):
    response = api.get("/api/coin-icons?symbols=BTC,not valid")
    assert response.status_code == 400


def test_rejects_oversized_batch(api):
    symbols = ",".join(f"SYM{i}" for i in range(300))
    response = api.get(f"/api/coin-icons?symbols={symbols}")
    assert response.status_code == 400


def test_already_cached_symbols_return_without_new_lookups(api, monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "peek_coin_icon_url",
        lambda symbol: (True, f"https://example.test/{symbol.lower()}.png"),
    )
    calls = []
    monkeypatch.setattr(
        backend_app, "fetch_coin_icon_url", lambda symbol: calls.append(symbol)
    )

    response = api.get("/api/coin-icons?symbols=BTC,ETH")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["icons"] == {
        "BTC": "https://example.test/btc.png",
        "ETH": "https://example.test/eth.png",
    }
    assert payload["pending"] == []
    assert calls == []  # nothing needed a live lookup


def test_uncached_batch_is_capped_and_names_the_rest_as_pending(api, monkeypatch):
    monkeypatch.setattr(backend_app, "peek_coin_icon_url", lambda symbol: (False, None))
    resolved = []

    def fake_fetch(symbol):
        resolved.append(symbol)
        return f"https://example.test/{symbol.lower()}.png"

    monkeypatch.setattr(backend_app, "fetch_coin_icon_url", fake_fetch)

    symbols = [f"SYM{i}" for i in range(12)]
    response = api.get(f"/api/coin-icons?symbols={','.join(symbols)}")
    assert response.status_code == 200
    payload = response.get_json()

    assert len(resolved) == backend_app._ICON_BATCH_RESOLVE_CAP
    assert set(payload["icons"].keys()) == set(resolved)
    assert payload["pending"] == symbols[backend_app._ICON_BATCH_RESOLVE_CAP :]


def test_a_lookup_failure_reports_the_symbol_unavailable_not_an_error(api, monkeypatch):
    monkeypatch.setattr(backend_app, "peek_coin_icon_url", lambda symbol: (False, None))

    def raises(symbol):
        raise RuntimeError("network down")

    monkeypatch.setattr(backend_app, "fetch_coin_icon_url", raises)

    response = api.get("/api/coin-icons?symbols=BTC")
    assert response.status_code == 200
    assert response.get_json()["icons"] == {"BTC": None}
