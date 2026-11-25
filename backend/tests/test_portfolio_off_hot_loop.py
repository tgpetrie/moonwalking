"""The owner-portfolio refresh runs off the price loop, and the loop paces to wall time."""

from pathlib import Path
import ast
import inspect
import sys
import textwrap
import threading

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

for path in (str(BACKEND_ROOT), str(REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    import app as backend_app
except Exception:  # pragma: no cover - fallback import path
    from backend import app as backend_app

import portfolio_mode
from portfolio_mode import CoinbaseRequestError, PortfolioService


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class _FlakyService(PortfolioService):
    """A PortfolioService whose network load can be scripted."""

    def __init__(self, loads):
        super().__init__(client=None)
        self._loads = list(loads)
        self.load_calls = 0

    def _load(self):
        self.load_calls += 1
        result = self._loads.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _snapshot(*symbols):
    return {"holdings": [{"symbol": s, "is_cash": False} for s in symbols]}


# --- fetch=False never blocks and never loses the last good holdings --------


def test_fetch_false_never_touches_the_network():
    service = _FlakyService([_snapshot("BTC")])
    assert service.held_symbols(fetch=False) == set()
    assert service.load_calls == 0


def test_fetch_false_keeps_holdings_long_past_every_ttl(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(portfolio_mode.time, "monotonic", clock)
    service = _FlakyService([_snapshot("BTC", "ETH")])

    assert service.held_symbols(fetch=True) == {"BTC", "ETH"}
    # Well beyond the 30s fresh TTL, the 300s stale TTL and a 120s refresh gap.
    clock.now += 10 * service.stale_ttl_seconds
    assert service.held_symbols(fetch=False) == {"BTC", "ETH"}
    assert service.load_calls == 1


def test_failed_refresh_does_not_clear_the_cache(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(portfolio_mode.time, "monotonic", clock)
    service = _FlakyService(
        [_snapshot("SOL"), CoinbaseRequestError("down"), _snapshot("SOL", "AVAX")]
    )

    service.held_symbols(fetch=True)
    clock.now += 2 * service.stale_ttl_seconds  # past stale: the refresh raises
    try:
        service.held_symbols(fetch=True)
    except CoinbaseRequestError:
        pass
    assert service.held_symbols(fetch=False) == {"SOL"}

    clock.now += 2 * service.stale_ttl_seconds
    assert service.held_symbols(fetch=True) == {"SOL", "AVAX"}
    assert service.held_symbols(fetch=False) == {"SOL", "AVAX"}


# --- the compute pass reads the cache; the refresher owns the network -------


def _calls_in(func, name):
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    ]


def test_compute_pass_reads_priority_symbols_from_cache_only():
    calls = _calls_in(
        backend_app._compute_snapshots_from_cache, "_notification_priority_symbols"
    )
    assert calls, "compute pass should still prioritize notifications"
    for call in calls:
        fetch = [kw for kw in call.keywords if kw.arg == "fetch"]
        assert fetch and isinstance(fetch[0].value, ast.Constant)
        assert fetch[0].value.value is False


def test_refresher_warms_immediately_then_repeats_and_survives_errors(monkeypatch):
    stop = threading.Event()
    results = [RuntimeError("boom"), {"BTC"}, {"BTC", "ETH"}]
    seen = []

    def fake_refresh():
        seen.append(len(seen))
        item = results.pop(0)
        if len(seen) == 3:
            stop.set()
        if isinstance(item, Exception):
            raise item  # the loop's own guard must absorb even this
        return item

    waits = []
    monkeypatch.setattr(backend_app, "_owner_portfolio_refresh_once", fake_refresh)
    monkeypatch.setattr(stop, "wait", lambda timeout: waits.append(timeout))

    backend_app._owner_portfolio_refresh_loop(stop_event=stop, interval_s=120)

    assert len(seen) == 3  # first refresh ran before any wait (warm-up)
    assert waits == [120, 120, 120]


def test_refresh_once_never_raises(monkeypatch):
    def broken(*, fetch=False):
        raise RuntimeError("no key configured")

    monkeypatch.setattr(portfolio_mode, "owner_held_symbols", broken)
    assert backend_app._owner_portfolio_refresh_once() == set()


def test_refresher_stops_promptly_when_signalled():
    stop = threading.Event()
    stop.set()
    t = threading.Thread(
        target=backend_app._owner_portfolio_refresh_loop,
        kwargs={"stop_event": stop, "interval_s": 3600},
    )
    t.start()
    t.join(timeout=2)
    assert not t.is_alive()


def test_refresh_interval_env(monkeypatch):
    monkeypatch.delenv("MW_PORTFOLIO_REFRESH_SECONDS", raising=False)
    assert backend_app._owner_portfolio_refresh_interval_s() == 120.0
    monkeypatch.setenv("MW_PORTFOLIO_REFRESH_SECONDS", "5")
    assert backend_app._owner_portfolio_refresh_interval_s() == 30.0
    monkeypatch.setenv("MW_PORTFOLIO_REFRESH_SECONDS", "junk")
    assert backend_app._owner_portfolio_refresh_interval_s() == 120.0


# --- elapsed-aware pacing ---------------------------------------------------


def test_loop_sleep_subtracts_elapsed_work():
    assert backend_app._loop_sleep_seconds(8, 3.0) == 5.0
    assert backend_app._loop_sleep_seconds(8, 0.0) == 8.0


def test_loop_sleep_has_a_floor_when_work_overruns():
    assert backend_app._loop_sleep_seconds(8, 7.9) == 0.5
    assert backend_app._loop_sleep_seconds(8, 40.0) == 0.5


def test_fetch_due_tolerates_waking_a_few_ms_early():
    # Paced sleep can land just short of the interval; the fetch must not
    # slip a whole cycle (which would silently double the fetch cadence).
    assert backend_app._price_fetch_due(1007.995, 1000.0, 8)
    assert backend_app._price_fetch_due(1008.0, 1000.0, 8)
    assert not backend_app._price_fetch_due(1004.0, 1000.0, 8)


def test_paced_loop_fetches_every_interval(monkeypatch):
    """Simulate the loop with a fake clock: work of 3s per cycle → 8s cadence."""
    clock = _Clock()
    # The real loop fetches once before entering, so iteration 1 only computes.
    fetch_times = [clock.now]
    last_fetch = clock.now
    clock.now += 8.0
    for _ in range(4):
        started = clock.now
        if backend_app._price_fetch_due(started, last_fetch, 8):
            last_fetch = started
            fetch_times.append(started)
        clock.now += 3.0  # fetch + compute work
        clock.now += backend_app._loop_sleep_seconds(8, clock.now - started)
    gaps = [b - a for a, b in zip(fetch_times, fetch_times[1:])]
    assert len(fetch_times) == 5
    assert all(abs(g - 8.0) < 1e-9 for g in gaps)


# --- sessions skip ~/.netrc and proxy env lookups ---------------------------


def test_coinbase_sessions_do_not_trust_env(monkeypatch):
    monkeypatch.setattr(backend_app, "_COINBASE_HTTP", None)
    assert backend_app._coinbase_http().trust_env is False
    client = portfolio_mode.CoinbaseAdvancedTradeClient("k", "s")
    assert client.http.trust_env is False
