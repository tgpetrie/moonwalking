"""Prospective evaluation labels only. Never import into live ranking code.

No I/O occurs on import. Inputs are immutable receipt-time snapshots; late
recovery must not replace them. Baselines must be causal at the anchor.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path


CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs/research/INSTANT_TARGET_CONTRACT_V1.json"
)
V2_CONTRACT_PATH = CONTRACT_PATH.with_name("INSTANT_TARGET_CONTRACT_V2_DRAFT.json")


def load_contract(path=None):
    raw = Path(path or CONTRACT_PATH).read_text(encoding="utf-8").encode("utf-8")
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class Sample:
    """State available at ts_ms; counts/volume cover [ts_ms-5000, ts_ms)."""

    product_id: str
    ts_ms: int
    bid: float | None
    ask: float | None
    btc_bid: float | None
    btc_ask: float | None
    quote_ts_ms: int
    btc_quote_ts_ms: int
    available_ts_ms: int
    trade_count: int
    quote_volume_usd: float
    coverage_verified: bool
    price_source: str = "mid"
    btc_price_source: str = "mid"
    trade_count_at_bucket_start: int | None = None

    @property
    def mid(self):
        return (self.bid + self.ask) / 2

    @property
    def btc_mid(self):
        return (self.btc_bid + self.btc_ask) / 2

    @property
    def spread_bps(self):
        return (self.ask - self.bid) / self.mid * 10000


@dataclass(frozen=True)
class Baseline:
    sigma_1m: float
    beta: float
    return_count: int
    end_ts_ms: int
    available_ts_ms: int
    beta_available_ts_ms: int
    beta_fallback: bool
    pace_trade_median_30s: float
    pace_quote_usd_median_30s: float
    pace_window_count: int
    pace_end_ts_ms: int
    pace_available_ts_ms: int


def finite(value):
    return (
        isinstance(value, (float, int))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


class TargetEvaluator:
    def __init__(self, samples, contract_path=None):
        self.cfg, self.contract_sha256 = load_contract(contract_path)
        if self.cfg["version"] not in ("instant-target-v1", "instant-target-v2-draft"):
            raise ValueError("unsupported target contract")
        self.is_v2 = self.cfg["version"] == "instant-target-v2-draft"
        self.implementation_sha256 = hashlib.sha256(
            Path(__file__).read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest()
        self.rows = {}
        self.product_id = None
        previous = None
        for row in samples:
            if (
                not isinstance(row.ts_ms, int)
                or isinstance(row.ts_ms, bool)
                or row.ts_ms % self.cfg["grid_ms"]
            ):
                raise ValueError("sample timestamps must lie on the 5s grid")
            if previous is not None and row.ts_ms <= previous:
                raise ValueError("samples must be strictly increasing and unique")
            if self.product_id is not None and row.product_id != self.product_id:
                raise ValueError("one product per evaluator")
            self.product_id = row.product_id
            self.rows[row.ts_ms] = row
            previous = row.ts_ms
        if not self.rows:
            raise ValueError("samples are required")

    def _quality(self, start, end):
        for ts in range(start, end + 1, self.cfg["grid_ms"]):
            row = self.rows.get(ts)
            if row is None:
                return "missing_grid_point"
            if row.coverage_verified is not True:
                return "unverified_coverage"
            if any(
                type(value) is not int
                for value in (row.available_ts_ms, row.quote_ts_ms, row.btc_quote_ts_ms)
            ):
                return "invalid_timestamp"
            if row.available_ts_ms > ts:
                return "future_receipt"
            if row.price_source != "mid" or row.btc_price_source != "mid":
                return "price_fallback"
            for bid, ask, observed in (
                (row.bid, row.ask, row.quote_ts_ms),
                (row.btc_bid, row.btc_ask, row.btc_quote_ts_ms),
            ):
                if not finite(bid) or not finite(ask) or bid <= 0 or ask < bid:
                    return "invalid_quote"
                if not 0 <= ts - observed <= self.cfg["max_quote_age_ms"]:
                    return "stale_or_future_quote"
            if type(row.trade_count) is not int or row.trade_count < 0:
                return "invalid_trade_count"
            if not finite(row.quote_volume_usd) or row.quote_volume_usd < 0:
                return "invalid_volume"
        return None

    def _baseline_quality(self, baseline, anchor):
        if baseline is None:
            return "missing_baseline"
        if (
            any(
                type(value) is not int
                for value in (
                    baseline.return_count,
                    baseline.end_ts_ms,
                    baseline.available_ts_ms,
                    baseline.beta_available_ts_ms,
                )
            )
            or type(baseline.beta_fallback) is not bool
        ):
            return "invalid_baseline_metadata"
        if (
            not finite(baseline.sigma_1m)
            or baseline.sigma_1m < 0
            or not finite(baseline.beta)
        ):
            return "invalid_baseline"
        if baseline.return_count < self.cfg["minimum_baseline_returns"]:
            return "baseline_warming"
        baseline_cutoff = anchor
        if self.is_v2:
            # Reviewed from Claude d711832. Apply only in the explicit v2
            # draft so the pinned v1 definition and outputs remain reproducible.
            baseline_cutoff -= (
                self.cfg["onset"]["velocity_window_seconds"] * 1000
                + self.cfg["grid_ms"]
            )
        if baseline.end_ts_ms != baseline_cutoff // 60000 * 60000:
            return "baseline_window_misaligned"
        if baseline.available_ts_ms > anchor or baseline.beta_available_ts_ms > anchor:
            return "future_baseline"
        return None

    def _residual(self, start, end, beta, direction):
        a, b = self.rows[start], self.rows[end]
        return direction * (
            math.log(b.mid / a.mid) - beta * math.log(b.btc_mid / a.btc_mid)
        )

    def evaluate(self, anchor, baseline, direction, horizon_seconds, asof_ts_ms):
        """Grade every eligible grid anchor, including no-move observations.

        Status 'ready' means a complete label, not a successful impulse.
        All returned outcome/onset fields are evaluation-only.
        """
        if type(horizon_seconds) is not int or type(asof_ts_ms) is not int:
            raise ValueError("horizon and as-of timestamp must be integers")
        if (
            direction not in ("up", "down")
            or horizon_seconds not in self.cfg["outcome_horizons_seconds"]
        ):
            raise ValueError("unsupported direction or horizon")
        if type(anchor) is not int or anchor % self.cfg["grid_ms"]:
            raise ValueError("anchor must lie on the 5s grid")
        sign = 1 if direction == "up" else -1
        end = anchor + horizon_seconds * 1000
        result = dict(
            contract_version=self.cfg["version"],
            contract_sha256=self.contract_sha256,
            evaluation_only=True,
            product_id=self.product_id,
            anchor_ts_ms=anchor,
            horizon_seconds=horizon_seconds,
            direction=direction,
            label_maturity_ts_ms=end,
            status="pending",
            reason="horizon_not_mature",
            verified_forward=None,
            verified_onset=None,
        )
        if self.is_v2:
            result.update(
                evaluator_sha256=self.implementation_sha256,
                primary_pointwise_target="verified_forward",
                physical_onset_defined=False,
            )
        if asof_ts_ms < end:
            return result
        reason = self._baseline_quality(baseline, anchor) or self._quality(anchor, end)
        if reason:
            return {**result, "status": "unavailable", "reason": reason}
        boundary_count = self.rows[
            anchor + self.cfg["grid_ms"]
        ].trade_count_at_bucket_start
        if (
            type(boundary_count) is not int
            or not 0
            <= boundary_count
            <= self.rows[anchor + self.cfg["grid_ms"]].trade_count
        ):
            return {
                **result,
                "status": "unavailable",
                "reason": "unknown_boundary_trade_count",
            }
        sigma = max(baseline.sigma_1m, self.cfg["sigma_floor_1m"])
        path = [
            (ts, self._residual(anchor, ts, baseline.beta, sign))
            for ts in range(anchor, end + 1, self.cfg["grid_ms"])
        ]
        peak_ts, peak = max(path, key=lambda pair: pair[1])  # first tie wins
        terminal = path[-1][1]
        adverse = min(value for _, value in path)
        retention = terminal / peak if peak > 0 else None
        first, last = self.rows[anchor], self.rows[end]
        rules = self.cfg["impulse"]
        threshold = max(
            rules["terminal_sigma_multiple"] * sigma * math.sqrt(horizon_seconds / 60),
            rules["minimum_terminal_log_return"],
            rules["entry_spread_multiple"] * first.spread_bps / 10000,
        )
        trades = sum(self.rows[ts].trade_count for ts, _ in path[1:]) - boundary_count
        tolerance = self.cfg["comparison_tolerance"]
        verified = (
            terminal + tolerance >= threshold
            and retention is not None
            and retention + tolerance >= rules["minimum_peak_retention"]
            and trades >= rules["minimum_forward_matches"]
        )
        gross_bps = sign * (last.mid / first.mid - 1) * 10000
        spread_cost = (first.spread_bps + last.spread_bps) / 2
        result.update(
            status="ready",
            reason=None,
            verified_forward=verified,
            sigma_1m=sigma,
            sigma_floor_applied=baseline.sigma_1m < sigma,
            beta=baseline.beta,
            beta_fallback=baseline.beta_fallback,
            terminal_residual_log=terminal,
            required_terminal_log=threshold,
            peak_residual_log=peak,
            peak_ts_ms=peak_ts,
            adverse_residual_log=adverse,
            retention=retention,
            forward_trade_count=trades,
            gross_coin_return_bps=gross_bps,
            cost_scenarios=[
                dict(
                    fee_bps_per_side=fee,
                    net_coin_return_bps=gross_bps - spread_cost - 2 * fee,
                )
                for fee in self.cfg["costs"]["fee_bps_per_side_scenarios"]
            ],
        )
        onset = self.cfg["onset"]
        velocity_ms = onset["velocity_window_seconds"] * 1000
        step = self.cfg["grid_ms"]
        if self.is_v2:
            reference = anchor - velocity_ms
            context_reason = self._quality(reference, anchor)
            result.update(
                pre_window_reference_ts_ms=reference,
                pre_window_reference_is_physical_origin=False,
                pre_window_reference_status=(
                    "unavailable" if context_reason else "ready"
                ),
                pre_window_reference_reason=context_reason,
            )
            if not context_reason:
                reference_path = [
                    (ts, self._residual(reference, ts, baseline.beta, sign))
                    for ts in range(reference, end + 1, step)
                ]
                reference_peak_ts, reference_peak = max(
                    reference_path, key=lambda pair: pair[1]
                )
                result.update(
                    pre_window_peak_ts_ms=reference_peak_ts,
                    pre_window_peak_residual_log=reference_peak,
                )
        reason = self._quality(anchor - velocity_ms - step, anchor)
        if any(
            type(value) is not int
            for value in (
                baseline.pace_window_count,
                baseline.pace_end_ts_ms,
                baseline.pace_available_ts_ms,
            )
        ):
            return {
                **result,
                "onset_status": "unavailable",
                "onset_reason": "invalid_pace_metadata",
            }
        if baseline.pace_window_count < onset["minimum_prior_pace_windows"]:
            reason = reason or "pace_warming"
        if (
            baseline.pace_end_ts_ms != anchor - velocity_ms
            or baseline.pace_available_ts_ms > anchor
        ):
            reason = reason or "future_pace_baseline"
        medians = (baseline.pace_trade_median_30s, baseline.pace_quote_usd_median_30s)
        if not all(finite(value) and value >= 0 for value in medians) or not any(
            value > 0 for value in medians
        ):
            reason = reason or "pace_unavailable"
        if reason:
            return {**result, "onset_status": "unavailable", "onset_reason": reason}
        current_velocity = self._residual(
            anchor - velocity_ms, anchor, baseline.beta, sign
        ) / (sigma / math.sqrt(2))
        previous_velocity = self._residual(
            anchor - velocity_ms - step, anchor - step, baseline.beta, sign
        ) / (sigma / math.sqrt(2))
        recent = [
            self.rows[ts] for ts in range(anchor - velocity_ms + step, anchor + 1, step)
        ]
        recent_trades = sum(row.trade_count for row in recent)
        recent_volume = sum(row.quote_volume_usd for row in recent)
        pace = max(
            (
                value / median
                for value, median in zip((recent_trades, recent_volume), medians)
                if median > 0
            ),
            default=0,
        )
        candidate = (
            previous_velocity < onset["velocity_crossing_sigma"] - tolerance
            and current_velocity + tolerance >= onset["velocity_crossing_sigma"]
            and recent_trades >= onset["minimum_matches_30s"]
            and pace > onset["pace_multiple_strictly_greater_than"] + tolerance
        )
        breakout_ts = next(
            (
                ts
                for ts, value in path[1:]
                if ts <= anchor + onset["breakout_deadline_seconds"] * 1000
                and value + tolerance >= onset["breakout_sigma"] * sigma
            ),
            None,
        )
        no_retrace = adverse >= -onset["no_retrace_tolerance_log"]
        result.update(
            onset_status="ready",
            onset_reason=None,
            onset_candidate=candidate,
            previous_velocity_sigma=previous_velocity,
            velocity_sigma=current_velocity,
            pace_multiple=pace,
            recent_trade_count=recent_trades,
            breakout_ts_ms=breakout_ts,
            no_retrace=no_retrace,
            verified_onset=bool(
                candidate and verified and breakout_ts is not None and no_retrace
            ),
        )
        return result

    def alert_timing(self, label, publish_ts_ms):
        """Retrospective event association; never a live stage or input."""
        if self.is_v2:
            return self._v2_alert_timing(label, publish_ts_ms, strict_trigger=True)
        if type(publish_ts_ms) is not int:
            raise ValueError("publication timestamp must be an integer")
        if (
            label.get("contract_sha256") != self.contract_sha256
            or label.get("product_id") != self.product_id
            or not label.get("verified_onset")
        ):
            raise ValueError(
                "a verified onset from this contract and product is required"
            )
        anchor = label["anchor_ts_ms"]
        rules = self.cfg["events"]
        if (
            not anchor - rules["prediction_lead_limit_seconds"] * 1000
            <= publish_ts_ms
            <= label["label_maturity_ts_ms"]
        ):
            return dict(evaluation_only=True, timing="outside_event_window")
        # Backward as-of lookup only. Never use the next grid point at publication.
        ts = publish_ts_ms // self.cfg["grid_ms"] * self.cfg["grid_ms"]
        reason = self._quality(ts, ts)
        if reason:
            return dict(evaluation_only=True, timing="unavailable", reason=reason)
        row = self.rows[ts]
        if (
            max(publish_ts_ms - row.quote_ts_ms, publish_ts_ms - row.btc_quote_ts_ms)
            > self.cfg["max_quote_age_ms"]
        ):
            return dict(
                evaluation_only=True, timing="unavailable", reason="stale_alert_quote"
            )
        sign = 1 if label["direction"] == "up" else -1
        consumed = (
            self._residual(anchor, ts, label["beta"], sign) / label["peak_residual_log"]
        )
        timing = (
            "pre_onset_prediction"
            if publish_ts_ms < anchor
            else (
                "early_detection"
                if publish_ts_ms <= label["peak_ts_ms"]
                and consumed
                < rules["early_detection_consumed_fraction_strictly_below"]
                - self.cfg["comparison_tolerance"]
                else "late_detection"
            )
        )
        return dict(
            evaluation_only=True,
            timing=timing,
            detection_delay_seconds=(publish_ts_ms - anchor) / 1000,
            lead_to_peak_seconds=(label["peak_ts_ms"] - publish_ts_ms) / 1000,
            consumed_fraction=consumed,
            price_snapshot_ts_ms=ts,
        )

    def forward_alert_timing(self, label, publish_ts_ms):
        """v2 forward-window association, without inferring a physical onset."""
        if not self.is_v2:
            raise ValueError("forward-window timing requires the explicit v2 draft")
        return self._v2_alert_timing(label, publish_ts_ms, strict_trigger=False)

    def _v2_alert_timing(self, label, publish_ts_ms, strict_trigger):
        if type(publish_ts_ms) is not int:
            raise ValueError("publication timestamp must be an integer")
        required = "verified_onset" if strict_trigger else "verified_forward"
        if (
            label.get("contract_sha256") != self.contract_sha256
            or label.get("evaluator_sha256") != self.implementation_sha256
            or label.get("product_id") != self.product_id
            or label.get("status") != "ready"
            or label.get(required) is not True
        ):
            raise ValueError(
                "a complete verified label from this evaluator is required"
            )
        peak = label.get("peak_residual_log")
        if not finite(peak) or peak <= 0:
            raise ValueError("a positive finite forward peak is required")
        anchor = label["anchor_ts_ms"]
        lead_ms = self.cfg["events"]["prediction_lead_limit_seconds"] * 1000
        if not anchor - lead_ms <= publish_ts_ms <= label["label_maturity_ts_ms"]:
            return dict(evaluation_only=True, timing="outside_event_window")
        ts = publish_ts_ms // self.cfg["grid_ms"] * self.cfg["grid_ms"]
        reason = self._quality(ts, ts)
        if reason:
            return dict(evaluation_only=True, timing="unavailable", reason=reason)
        row = self.rows[ts]
        if (
            max(publish_ts_ms - row.quote_ts_ms, publish_ts_ms - row.btc_quote_ts_ms)
            > self.cfg["max_quote_age_ms"]
        ):
            return dict(
                evaluation_only=True, timing="unavailable", reason="stale_alert_quote"
            )
        sign = 1 if label["direction"] == "up" else -1
        post_fraction = self._residual(anchor, ts, label["beta"], sign) / peak
        output = dict(
            evaluation_only=True,
            physical_onset_defined=False,
            post_anchor_consumed_fraction=post_fraction,
            post_anchor_reference_ts_ms=anchor,
            offset_from_anchor_seconds=(publish_ts_ms - anchor) / 1000,
            lead_to_forward_peak_seconds=(label["peak_ts_ms"] - publish_ts_ms) / 1000,
            price_snapshot_ts_ms=ts,
            pre_window_consumed_fraction=None,
            pre_window_reference_ts_ms=label.get("pre_window_reference_ts_ms"),
            pre_window_reference_is_physical_origin=False,
        )
        reference_peak = label.get("pre_window_peak_residual_log")
        if (
            label.get("pre_window_reference_status") == "ready"
            and finite(reference_peak)
            and reference_peak > 0
        ):
            output["pre_window_consumed_fraction"] = (
                self._residual(
                    label["pre_window_reference_ts_ms"], ts, label["beta"], sign
                )
                / reference_peak
            )
            output["lead_to_pre_window_peak_seconds"] = (
                label["pre_window_peak_ts_ms"] - publish_ts_ms
            ) / 1000
        if strict_trigger:
            fraction = output["pre_window_consumed_fraction"]
            if fraction is None:
                return dict(
                    evaluation_only=True,
                    timing="unavailable",
                    reason="pre_window_reference_unavailable",
                )
            early = (
                publish_ts_ms <= label["pre_window_peak_ts_ms"]
                and fraction
                < self.cfg["events"]["early_detection_consumed_fraction_strictly_below"]
                - self.cfg["comparison_tolerance"]
            )
            output["timing"] = (
                "before_activity_trigger"
                if publish_ts_ms < anchor
                else (
                    "early_after_activity_trigger"
                    if early
                    else "late_after_activity_trigger"
                )
            )
            output["association_kind"] = "strict_activity_trigger"
        else:
            output["timing"] = (
                "before_forward_window_anchor"
                if publish_ts_ms < anchor
                else (
                    "within_forward_window_before_peak"
                    if publish_ts_ms <= label["peak_ts_ms"]
                    else "within_forward_window_after_peak"
                )
            )
            output["association_kind"] = "forward_window_not_physical_impulse"
        return output


def event_catalog(labels, *, target="verified_onset"):
    """Earliest verified event owns [onset,onset+H), per product/direction/H.

    This retrospective deduplication is separate from the live 15m per-coin
    alert cooldown. Unverified/pending rows never suppress another event.
    """
    labels = list(labels)
    if target not in ("verified_onset", "verified_forward"):
        raise ValueError("unsupported catalog target")
    selected, ends = [], {}
    hashes = {row["contract_sha256"] for row in labels}
    if len(hashes) > 1:
        raise ValueError("cannot mix target contracts")
    implementations = {row.get("evaluator_sha256") for row in labels}
    if len(implementations) > 1:
        raise ValueError("cannot mix evaluator implementations")
    for row in sorted(
        labels,
        key=lambda row: (
            row["anchor_ts_ms"],
            row["product_id"],
            row["direction"],
            row["horizon_seconds"],
        ),
    ):
        key = row["product_id"], row["direction"], row["horizon_seconds"]
        if (
            row.get(target) is True
            and row.get("status") == "ready"
            and row["anchor_ts_ms"] >= ends.get(key, -math.inf)
        ):
            selected.append(row)
            ends[key] = row["label_maturity_ts_ms"]
    return selected


def forward_event_catalog(labels):
    """Catalog forward windows independently of activity/no-retrace gates.

    These are deduplicated qualifying forecast windows, not a definition of
    physical move onset or a completed operational missed-move denominator.
    """
    labels = list(labels)
    if any(row.get("contract_version") != "instant-target-v2-draft" for row in labels):
        raise ValueError("forward-window catalog requires labels from the explicit v2 draft")
    return [
        {**row, "catalog_kind": "forward_window_not_physical_impulse"}
        for row in event_catalog(labels, target="verified_forward")
    ]
