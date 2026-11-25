"""Stage 2: the guarded dry-run exit prices a sale across the bid ladder.

Every outcome stays a simulation: nothing here can reach an order route.
"""

from decimal import ROUND_DOWN, Decimal

import pytest

from agents.cycle_context import fetch_live_quotes, fetch_top_of_book
from agents.cycle_strategist import TRIM_TO_USDC, CycleStrategistAgent
from agents.store import AgentStore

NOW = 1_800_000_000.0
NOW_MS = int(NOW * 1000)
# The mixed context trims 37.5% of a 10 SOL position: 3.75 SOL against a
# $175 reference. The top bid alone holds only 1 SOL.
LADDER = [[174.8, 1.0], [174.7, 2.0], [174.6, 5.0]]
SHORT_LADDER = [[174.8, 1.0], [174.7, 1.0]]


def _quote(bid=174.8, size=1.0, age_ms=1_000, **changes):
    return {
        "product_id": "SOL-USD",
        "observed_at_ms": NOW_MS - age_ms,
        "exchange_time_ms": NOW_MS - age_ms - 100,
        "bid_usd": bid,
        "ask_usd": bid * 1.001,
        "bid_size": size,
        **changes,
    }


def _context(quote):
    trim = {
        "symbol": "SOL",
        "product_id": "SOL-USD",
        "available": True,
        "price": 175.0,
        "rollover_target_box": {"low": 150.0, "high": 200.0},
    }
    return {
        "cycle_scan": {
            "industry": {
                "available": True,
                "liquidity_rotation_stage": "stage_1_macro_compression",
            },
            "coins": [trim],
        },
        "positions": [{"symbol": "SOL", "quantity": 10}],
        "quotes": {"SOL-USD": quote} if quote is not None else {},
    }


@pytest.fixture
def store(tmp_path):
    store = AgentStore(tmp_path / "agents.sqlite")
    store.set_autonomy_settings(autonomy_mode="auto_protect_exits")
    return store


def _trim(store, quote):
    agent = CycleStrategistAgent(store)
    agent.run({"now_ts": NOW, **_context(quote)})
    return {p["action"]: p for p in agent.last_proposals}[TRIM_TO_USDC]


def test_a_thin_top_bid_with_depth_behind_it_now_executes_across_the_ladder(store):
    trim = _trim(store, _quote(bids=LADDER))
    assert trim["status"] == "auto_executed_dry_run"
    execution = trim["execution"]
    assert execution["order_type"] == "simulated_sell_across_bids"
    assert execution["base_size"] == 3.75
    assert execution["bid_usd"] == 174.8
    assert execution["levels_consumed"] == 3
    # 1 @ 174.8 + 2 @ 174.7 + 0.75 @ 174.6 = 655.15, slipped 10 bps, no fee.
    gross = Decimal("655.15")
    assert execution["gross_book_proceeds_usd"] == pytest.approx(float(gross))
    assert execution["estimated_vwap_usd"] == pytest.approx(
        float(gross / Decimal("3.75"))
    )
    assert execution["fill_price"] == pytest.approx(
        float(gross / Decimal("3.75") * Decimal("0.999"))
    )
    net = (gross * Decimal("0.999")).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    assert execution["proceeds_usd"] == float(net) == 654.49
    assert execution["depth_cost_vs_top_bid_usd"] == pytest.approx(
        174.8 * 3.75 - 655.15
    )
    assert execution["dry_run"] is True and execution["order_submitted"] is False


def test_the_same_thin_top_bid_without_a_ladder_is_still_refused(store):
    trim = _trim(store, _quote())
    assert trim["status"] == "blocked_by_guard"
    assert trim["execution"]["block_reasons"] == ["insufficient_top_of_book_size"]


def test_a_ladder_that_cannot_cover_the_exit_is_blocked_explicitly(store):
    trim = _trim(store, _quote(bids=SHORT_LADDER))
    assert trim["status"] == "blocked_by_guard"
    reasons = trim["execution"]["block_reasons"]
    assert "insufficient_book_depth" in reasons
    assert "insufficient_top_of_book_size" not in reasons
    assert trim["execution"]["depth_shortfall_quantity"] == pytest.approx(1.75)
    assert "proceeds_usd" not in trim["execution"]


@pytest.mark.parametrize(
    ("bids", "reason"),
    [
        ([[174.9, 5.0]], "quote_ladder_mismatch"),
        ([[174.8, 1.0], [174.8, 5.0]], "invalid_bid_ladder"),
        ([[174.8, 1.0], [174.9, 5.0]], "invalid_bid_ladder"),
        ([[174.8, 1.0], [174.7, 0.0]], "invalid_bid_ladder"),
        ([], "invalid_bid_ladder"),
        ("not a ladder", "invalid_bid_ladder"),
    ],
)
def test_a_malformed_ladder_blocks_the_exit(store, bids, reason):
    trim = _trim(store, _quote(bids=bids))
    assert trim["status"] == "blocked_by_guard"
    assert reason in trim["execution"]["block_reasons"]


def test_a_ladder_does_not_bypass_the_existing_guards(store):
    for quote, reason in (
        (_quote(bids=LADDER, age_ms=60_000), "quote_stale"),
        (_quote(bids=LADDER, ask_usd=174.0), "quote_crossed_book"),
        (_quote(160.0, bids=[[160.0, 9.0]]), "quote_deviates_from_reference"),
    ):
        trim = _trim(store, quote)
        assert trim["status"] == "blocked_by_guard"
        assert reason in trim["execution"]["block_reasons"]


@pytest.mark.parametrize(
    "settings",
    [
        {"execution_mode": "live_guarded"},
        {"daily_order_cap": 0},
        {"emergency_pause": True},
    ],
)
def test_live_guarded_pause_and_cap_are_unchanged_with_a_ladder(store, settings):
    store.set_autonomy_settings(**settings)
    trim = _trim(store, _quote(bids=LADDER))
    assert trim["status"] in ("blocked_by_guard", "pending_approval")
    assert trim["status"] != "auto_executed_dry_run"
    if settings.get("execution_mode") == "live_guarded":
        assert trim["execution"]["block_reasons"] == ["live_order_route_unavailable"]
    if settings.get("daily_order_cap") == 0:
        assert trim["execution"]["block_reasons"] == ["daily_order_cap_reached"]
    if settings.get("emergency_pause"):
        assert trim["execution"]["held_reason"] == "emergency_pause"
    assert store.count_auto_orders_since(0) == 0


@pytest.mark.parametrize(
    ("settings", "quote"),
    [
        ({}, _quote(bids=LADDER)),
        ({}, _quote(size=10.0)),
        ({}, _quote(bids=SHORT_LADDER)),
        ({}, _quote(age_ms=60_000)),
        ({}, None),
        ({"execution_mode": "live_guarded"}, _quote(bids=LADDER)),
        ({"daily_order_cap": 0}, _quote(bids=LADDER)),
    ],
)
def test_every_executor_outcome_says_it_is_a_dry_run_that_submitted_nothing(
    store, settings, quote
):
    if settings:
        store.set_autonomy_settings(**settings)
    execution = _trim(store, quote)["execution"]
    assert execution["dry_run"] is True
    assert execution["order_submitted"] is False


# ─── live quote fetcher ─────────────────────────────────────────────────────


class _Book:
    status_code = 200

    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


def _level_two_book():
    return {
        "bids": [
            ["174.80", "1.0", 2],
            ["174.70", "2.0", 1],
            ["174.60", "5.0", 4],
            ["174.50", "9", 1],
        ],
        "asks": [["174.90", "4", 1], ["175.00", "8", 2]],
        "sequence": 1,
        "auction_mode": False,
        "time": "2027-01-15T08:00:00.250Z",
    }


def test_the_fetcher_stays_level_one_unless_depth_is_requested():
    calls = []

    def http_get(url, **kwargs):
        calls.append(kwargs["params"])
        return _Book(_level_two_book())

    quote = fetch_top_of_book("SOL-USD", http_get=http_get, now_ms=lambda: NOW_MS)
    assert calls == [{"level": 1}]
    assert "bids" not in quote
    assert quote["source"] == "coinbase_exchange_book_level_1"


def test_the_fetcher_returns_a_trimmed_ladder_when_depth_is_requested():
    calls = []

    def http_get(url, **kwargs):
        calls.append(kwargs["params"])
        return _Book(_level_two_book())

    quote = fetch_top_of_book(
        "SOL-USD", http_get=http_get, now_ms=lambda: NOW_MS, depth_levels=3
    )
    assert calls == [{"level": 2}]
    assert quote["quote_status"] == "AVAILABLE"
    assert quote["source"] == "coinbase_exchange_book_level_2"
    assert quote["bids"] == [[174.8, 1.0], [174.7, 2.0], [174.6, 5.0]]
    assert (quote["bid_usd"], quote["bid_size"], quote["ask_usd"]) == (
        174.8,
        1.0,
        174.9,
    )
    assert quote["book_levels_requested"] == 3


@pytest.mark.parametrize("depth", [0, -1, 51, 2.5, True, "3"])
def test_an_invalid_depth_request_is_unavailable_not_an_error(depth):
    quote = fetch_top_of_book(
        "SOL-USD",
        http_get=lambda url, **kw: _Book(_level_two_book()),
        now_ms=lambda: NOW_MS,
        depth_levels=depth,
    )
    assert quote == {
        "product_id": "SOL-USD",
        "quote_status": "UNAVAILABLE",
        "reason": "invalid_depth_levels",
    }


def test_fetch_live_quotes_passes_the_depth_request_through():
    params = []

    def http_get(url, **kwargs):
        params.append(kwargs["params"])
        return _Book(_level_two_book())

    quotes = fetch_live_quotes(
        ["SOL"], http_get=http_get, now_ms=lambda: NOW_MS, depth_levels=2
    )
    assert params == [{"level": 2}]
    assert quotes["SOL-USD"]["bids"] == [[174.8, 1.0], [174.7, 2.0]]
