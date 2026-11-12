"""Record one read-only Coinbase spot quote window for the paper simulator."""

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, DecimalException
import json
from pathlib import Path
import re
import time

from backend.portfolio_mode import (
    CoinbaseAdvancedTradeClient,
    CoinbaseRequestError,
    PortfolioModeError,
    UnsafeCoinbasePermissions,
    _weighted_fill_inventory,
)
from scripts.coinbase_paper_exit import (
    BPS,
    PILOT_SCHEMA,
    PILOT_SETTINGS,
    _number,
    _scenario_inputs,
)


POLL_MS = PILOT_SETTINGS["poll_interval_ms"]
FULL_WINDOW_SECONDS = 4 * 60 * 60
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class UnverifiedCostBasisError(ValueError):
    """The selected quantity could not be reconciled to USD fills."""


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Coinbase timestamp is missing")
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise ValueError("timestamp must include its UTC offset")
    return stamp


def _now_ms():
    return time.time_ns() // 1_000_000


def _epoch_ms(stamp):
    return (stamp - EPOCH) // timedelta(milliseconds=1)


def _require_view_only(client):
    permissions = client.get_key_permissions()
    if not (
        permissions.get("can_view") is True
        and permissions.get("can_trade") is False
        and permissions.get("can_transfer") is False
    ):
        raise UnsafeCoinbasePermissions(
            "Paper collection requires a View-only Coinbase key."
        )


def _holding(client, asset):
    accounts = client.list_accounts(require_complete=True)
    matches = [
        account
        for account in accounts.items
        if account.get("currency") == asset
        and account.get("active") is not False
        and account.get("ready") is not False
    ]
    if not accounts.complete or len(matches) != 1:
        raise UnverifiedCostBasisError(
            "complete history and one matching account are required"
        )
    account = matches[0]
    try:
        available = _number(account["available_balance"], "value", allow_zero=True)
        held = _number(account["hold"], "value", allow_zero=True)
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        raise UnverifiedCostBasisError("account quantities are unavailable") from error
    return available, held


def _usd_fills(fills, product_id, cutoff):
    unique = {}
    for fill in fills:
        entry_id = fill.get("entry_id")
        if not isinstance(entry_id, str) or not entry_id:
            raise ValueError("fill identity is missing")
        if entry_id in unique:
            if unique[entry_id][1] != fill:
                raise ValueError("conflicting records for the same fill")
            continue
        if fill.get("product_id") != product_id or fill.get("side") not in {
            "BUY",
            "SELL",
        }:
            raise ValueError(
                "holding history includes a fill outside the selected USD spot pair"
            )
        if type(fill.get("size_in_quote")) is not bool:
            raise ValueError("fill size unit is unknown")
        _number(fill, "size")
        _number(fill, "price")
        _number(fill, "commission", allow_zero=True)
        trade_time = _timestamp(fill.get("trade_time"))
        if trade_time >= cutoff:
            raise ValueError("fill arrived after the position snapshot boundary")
        unique[entry_id] = (trade_time, fill)
    ordered = sorted(unique.values(), key=lambda row: row[0])
    for (earlier, first), (later, second) in zip(ordered, ordered[1:]):
        if earlier == later and first["side"] != second["side"]:
            raise ValueError("opposite-side fills share a timestamp")
    return [fill for _, fill in ordered]


def verify_slice_cost_basis(client, product_id, quantity):
    """Reconcile a fixed slice to the selected holding's weighted USD cost."""
    if not isinstance(product_id, str) or not re.fullmatch(
        r"[A-Z0-9]+-USD", product_id
    ):
        raise ValueError("product_id must identify a USD spot pair")
    quantity = _number({"quantity": quantity}, "quantity")
    _require_view_only(client)
    asset = product_id.removesuffix("-USD")
    available, held = _holding(client, asset)
    if available < quantity:
        raise UnverifiedCostBasisError("selected quantity exceeds available balance")
    cutoff = datetime.now(timezone.utc)
    fills = client.list_fills(asset=asset, require_complete=True)
    if not fills.complete:
        raise UnverifiedCostBasisError("Coinbase fill pagination is incomplete")
    try:
        ordered = _usd_fills(fills.items, product_id, cutoff)
        covered, cost = _weighted_fill_inventory(ordered, require_covered_sales=True)
    except (ValueError, DecimalException) as error:
        raise UnverifiedCostBasisError(str(error)) from error
    if covered != available + held or cost <= 0:
        raise UnverifiedCostBasisError(
            "USD fills do not reconcile to the whole holding"
        )
    if _holding(client, asset) != (available, held):
        raise UnverifiedCostBasisError("holding changed during cost-basis verification")
    return {
        "entry_cost_usd": cost * quantity / covered,
        "cost_basis_verified": True,
        "cost_basis_coverage_pct": "100",
        "source_fill_ids": [fill["entry_id"] for fill in ordered],
        "cost_basis_asof_utc": cutoff.isoformat(),
    }


def fetch_fee_tier_bps(client):
    summary = client.get(
        "/api/v3/brokerage/transaction_summary",
        params={"product_type": "SPOT"},
    )
    fee = _number(summary.get("fee_tier") or {}, "taker_fee_rate", allow_zero=True)
    if fee >= 1:
        raise ValueError("Coinbase taker fee must be a fraction below one")
    return fee * BPS


def poll_top_of_book(client, product_id, *, now_ms=_now_ms):
    """Timestamp receipt and keep Coinbase's book timestamp independently."""
    try:
        response = client.get(
            "/api/v3/brokerage/product_book",
            params={"product_id": product_id, "limit": 1},
        )
        observed = now_ms()
        book = response["pricebook"]
        if book["product_id"] != product_id:
            raise ValueError("book product differs from the request")
        bid = book["bids"][0]
        return {
            "observed_at_ms": observed,
            "exchange_time_ms": _epoch_ms(_timestamp(book["time"])),
            "bid_usd": _number(bid, "price"),
            "bid_size": _number(bid, "size", allow_zero=True),
        }
    except (
        CoinbaseRequestError,
        KeyError,
        IndexError,
        TypeError,
        AttributeError,
        ValueError,
    ):
        return {"observed_at_ms": now_ms(), "quote_status": "UNAVAILABLE"}


def collect_quotes(client, spec, *, now_ms=_now_ms, sleep=time.sleep):
    start, end = spec["window_start_ms"], spec["window_end_ms"]
    quotes = []
    for slot in range(start, end, POLL_MS):
        now = now_ms()
        if now >= slot + POLL_MS:
            continue
        if now < slot:
            sleep((slot - now) / 1_000)
        quote = poll_top_of_book(client, spec["product_id"], now_ms=now_ms)
        observed = quote["observed_at_ms"]
        if observed > end:
            break
        if observed < slot or (quotes and observed <= quotes[-1]["observed_at_ms"]):
            raise ValueError("local clock moved backward during collection")
        quotes.append(quote)
    return quotes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", required=True, help="USD spot pair")
    parser.add_argument("--quantity", required=True)
    parser.add_argument(
        "--start-utc", required=True, help="Future UTC time with offset"
    )
    parser.add_argument("--duration-seconds", type=int, default=FULL_WINDOW_SECONDS)
    parser.add_argument(
        "--slippage-bps", required=True, help="Paper execution assumption"
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="New private scenario JSON"
    )
    args = parser.parse_args()
    try:
        start = _timestamp(args.start_utc)
        if (
            start.utcoffset().total_seconds() != 0
            or not 1 <= args.duration_seconds <= FULL_WINDOW_SECONDS
        ):
            raise ValueError(
                "choose a UTC start and a duration between 1 and 14400 seconds"
            )
        if args.duration_seconds == FULL_WINDOW_SECONDS and (
            start.hour % 4 or start.minute or start.second or start.microsecond
        ):
            raise ValueError("four-hour windows start at a UTC four-hour boundary")
        start_ms = _epoch_ms(start)
        if _now_ms() >= start_ms:
            raise ValueError("start time must still be in the future")
        output = args.out.resolve()
        if (
            output.is_relative_to(Path(__file__).resolve().parents[1])
            or output.exists()
        ):
            raise ValueError("choose a new output file outside the Git checkout")
        if not output.parent.is_dir():
            raise ValueError("output parent directory must already exist")
        spec = {
            "schema_version": PILOT_SCHEMA,
            "window_id": f"{start.isoformat()}_{args.product}_{args.duration_seconds}s",
            "window_start_ms": start_ms,
            "window_end_ms": start_ms + args.duration_seconds * 1_000,
            **PILOT_SETTINGS,
            "product_id": args.product,
            "quantity": args.quantity,
            "slippage_bps": args.slippage_bps,
            "thresholds": {"rebound_usd": 50, "rebound_pct": 8, "net_profit_pct": 8},
        }
        # Validate user-controlled inputs before any authenticated requests.
        _scenario_inputs({**spec, "entry_cost_usd": 1, "exit_fee_bps": 0})
        wait = (start_ms - _now_ms()) / 1_000 - 60
        if wait > 0:
            time.sleep(wait)
        client = CoinbaseAdvancedTradeClient.from_environment()
        spec.update(verify_slice_cost_basis(client, args.product, args.quantity))
        spec["exit_fee_bps"] = fetch_fee_tier_bps(client)
        spec["fee_tier_source"] = "coinbase_transaction_summary_taker"
        if _now_ms() >= start_ms:
            raise ValueError("position and fee verification missed the declared start")
        spec["quotes"] = collect_quotes(client, spec)
        with output.open("x", encoding="utf-8") as tape:
            json.dump(spec, tape, default=str, indent=2)
            tape.write("\n")
        print(output)
    except (OSError, ValueError, DecimalException, PortfolioModeError) as error:
        parser.exit(2, f"{parser.prog}: {error}\n")


if __name__ == "__main__":
    main()
