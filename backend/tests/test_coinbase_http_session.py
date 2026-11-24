"""Coinbase ticker and candle calls share one pooled HTTP session."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

for path in (str(BACKEND_ROOT), str(REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    import app as backend_app
except Exception:  # pragma: no cover - fallback import path
    from backend import app as backend_app


def test_one_session_is_shared_across_threads(monkeypatch):
    monkeypatch.setattr(backend_app, "_COINBASE_HTTP", None)

    with ThreadPoolExecutor(max_workers=8) as pool:
        sessions = list(pool.map(lambda _: backend_app._coinbase_http(), range(32)))

    assert len({id(s) for s in sessions}) == 1
    adapter = sessions[0].get_adapter("https://api.exchange.coinbase.com/products")
    assert adapter._pool_connections == 16
    assert adapter._pool_maxsize == 16


def test_candle_fetch_goes_through_the_shared_session(monkeypatch):
    calls = []

    class Response:
        status_code = 200
        ok = True

        def json(self):
            return [[1, 1.0, 1.0, 1.0, 1.0, 5.0]]

    class Session:
        def get(self, url, params=None, timeout=None):
            calls.append(url)
            return Response()

    monkeypatch.setattr(backend_app, "_COINBASE_HTTP", Session())

    backend_app._fetch_coinbase_candles("BTC-USD", granularity=60, count=1)

    assert calls == ["https://api.exchange.coinbase.com/products/BTC-USD/candles"]
