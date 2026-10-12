from __future__ import annotations

import time
from typing import Any, Iterable

from .contracts import AgentObservation


BOARD_TABLES = (
    "gainers_1m",
    "gainers_3m",
    "losers_3m",
    "banner_1h_price",
    "banner_1h_volume",
)


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if value == value and value not in (float("inf"), float("-inf")) else None


def _ts_seconds(value: Any) -> float | None:
    numeric = _num(value)
    if numeric is None or numeric <= 0:
        return None
    return numeric / 1000 if numeric > 10_000_000_000 else numeric


def _symbol_from_row(row: dict) -> str | None:
    symbol = row.get("symbol") or row.get("base_symbol")
    product_id = row.get("product_id") or row.get("productId")
    if symbol:
        return str(symbol).upper().split("-")[0]
    if product_id:
        return str(product_id).upper().split("-")[0]
    return None


def _product_id_from_row(row: dict) -> str | None:
    product_id = row.get("product_id") or row.get("productId")
    symbol = _symbol_from_row(row)
    if product_id:
        return str(product_id).upper()
    if symbol:
        return f"{symbol}-USD"
    return None


def _first_present(row: dict, keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row:
            return row.get(key)
    return None


def analyze_board_snapshot(
    snapshot: dict | None, *, now: float | None = None, max_age_seconds: int = 180
) -> list[AgentObservation]:
    now = time.time() if now is None else now
    agent = "data_quality"
    observations: list[AgentObservation] = []
    if not isinstance(snapshot, dict):
        return [
            AgentObservation(
                agent=agent,
                kind="missing_board_snapshot",
                severity="critical",
                summary="No board snapshot was provided to the local agents.",
                source={"surface": "board"},
            )
        ]

    snapshot_ts = _ts_seconds(
        snapshot.get("timestamp") or snapshot.get("ts") or snapshot.get("ts_ms")
    )
    if snapshot_ts and now - snapshot_ts > max_age_seconds:
        observations.append(
            AgentObservation(
                agent=agent,
                kind="stale_board_snapshot",
                severity="warning",
                summary="The board snapshot is stale, so trend agents should not score it as live.",
                evidence={
                    "age_seconds": round(now - snapshot_ts, 1),
                    "max_age_seconds": max_age_seconds,
                },
                source={"surface": "board"},
            )
        )

    for table_name in BOARD_TABLES:
        rows = snapshot.get(table_name)
        if rows is None:
            continue
        if not isinstance(rows, list):
            observations.append(
                AgentObservation(
                    agent=agent,
                    kind="invalid_board_table",
                    severity="warning",
                    summary=f"{table_name} is not a list, so agents skipped it.",
                    evidence={"table": table_name, "type": type(rows).__name__},
                    source={"surface": "board", "table": table_name},
                )
            )
            continue
        if not rows:
            observations.append(
                AgentObservation(
                    agent=agent,
                    kind="empty_board_table",
                    severity="info",
                    summary=f"{table_name} is empty right now.",
                    evidence={"table": table_name},
                    source={"surface": "board", "table": table_name},
                )
            )
            continue

        seen: set[str] = set()
        duplicate_ids: list[str] = []
        missing_price: list[str] = []
        missing_identity = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            product_id = _product_id_from_row(row)
            if not product_id:
                missing_identity += 1
            elif product_id in seen:
                duplicate_ids.append(product_id)
            else:
                seen.add(product_id)
            price = _num(
                row.get("price_now")
                if "price_now" in row
                else row.get("currentPrice", row.get("price"))
            )
            if price is None or price <= 0:
                missing_price.append(product_id or _symbol_from_row(row) or "unknown")

        if duplicate_ids:
            observations.append(
                AgentObservation(
                    agent=agent,
                    kind="duplicate_product_ids",
                    severity="warning",
                    summary=f"{table_name} contains duplicate product ids.",
                    evidence={"table": table_name, "product_ids": duplicate_ids[:20]},
                    source={"surface": "board", "table": table_name},
                )
            )
        if missing_identity:
            observations.append(
                AgentObservation(
                    agent=agent,
                    kind="missing_product_identity",
                    severity="warning",
                    summary=f"{table_name} has rows without product_id or symbol.",
                    evidence={"table": table_name, "row_count": missing_identity},
                    source={"surface": "board", "table": table_name},
                )
            )
        if missing_price:
            observations.append(
                AgentObservation(
                    agent=agent,
                    kind="missing_or_invalid_price",
                    severity="warning",
                    summary=f"{table_name} has rows without a usable current price.",
                    evidence={"table": table_name, "rows": missing_price[:20]},
                    source={"surface": "board", "table": table_name},
                )
            )
    return observations


def analyze_coin_pressure_payload(payload: dict | None) -> list[AgentObservation]:
    if not isinstance(payload, dict):
        return []
    agent = "data_quality"
    observations: list[AgentObservation] = []
    symbol = str(payload.get("symbol") or payload.get("product_id") or "").split("-")[0]

    current_price = _num(payload.get("current_price") or payload.get("price_now"))
    quote = payload.get("quote")
    if current_price is None and isinstance(quote, dict):
        current_price = _num(quote.get("price") or quote.get("price_usd"))
    if current_price is None:
        observations.append(
            AgentObservation(
                agent=agent,
                kind="coin_pressure_missing_price",
                severity="warning",
                symbol=symbol or None,
                summary="Coin Pressure does not expose a usable current price in this payload.",
                evidence={"top_level_keys": sorted(payload.keys())[:30]},
                source={"surface": "coin_pressure"},
            )
        )

    no_live_text = str(payload.get("message") or payload.get("read") or "").lower()
    has_live_signal = bool(payload.get("live_signal") or payload.get("signal"))
    if (not has_live_signal) and "not enough live tape" in no_live_text:
        observations.append(
            AgentObservation(
                agent=agent,
                kind="coin_pressure_no_live_tape",
                severity="info",
                symbol=symbol or None,
                summary="Coin Pressure is explicitly waiting for more live tape.",
                evidence={"message": payload.get("message") or payload.get("read")},
                source={"surface": "coin_pressure"},
            )
        )
    return observations


def analyze_track_record(records: Iterable[dict] | None) -> list[AgentObservation]:
    if not records:
        return []
    items = [item for item in records if isinstance(item, dict)]
    if not items:
        return []
    zero_rows = []
    for item in items:
        observed = _num(
            _first_present(
                item, ("observed_periods", "measured_periods", "sample_size", "n")
            )
        )
        target = _num(_first_present(item, ("target_periods", "market_periods")))
        if observed == 0 and (target is None or target > 0):
            zero_rows.append(item)
    if zero_rows and len(zero_rows) == len(items):
        return [
            AgentObservation(
                agent="data_quality",
                kind="track_record_unmeasured",
                severity="info",
                summary="Every supplied track-record row is still unmeasured, so success rates should stay hidden.",
                evidence={"rows": len(items), "zero_rows": len(zero_rows)},
                source={"surface": "track_record"},
            )
        ]
    return []


class DataQualityAgent:
    name = "data_quality"
    model_version = "data-quality-v1"

    def run(self, context: dict | None) -> list[AgentObservation]:
        context = context or {}
        observations: list[AgentObservation] = []
        observations.extend(analyze_board_snapshot(context.get("board_snapshot")))
        observations.extend(analyze_coin_pressure_payload(context.get("coin_pressure")))
        observations.extend(analyze_track_record(context.get("track_record")))
        return observations
