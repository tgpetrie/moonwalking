"""Offline decision snapshots and later cutoff-anchored grading."""

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path

from instant_coverage import _integer
from instant_input_evidence import BENCHMARK, GRID_MS, _json, _sha
from instant_publication import PublicationTiming, publication_timing
from instant_targets import V2_CONTRACT_PATH, load_contract
from instant_timed_baseline import PACE_MS
from instant_timed_features import build_timed_features


DECISION_VERSION = "instant-delayed-decision-v1-draft"
GRADE_VERSION = "instant-later-cutoff-grade-v1-draft"
SOURCE = Path(__file__)


@dataclass(frozen=True)
class DecisionEvidence:
    version: str
    product_id: str
    direction: str
    feature_cutoff_ts_ms: int
    knowledge_asof_ts_ms: int
    feature_computation_completed_ts_ms: int
    decision_completed_ts_ms: int
    feature_json: str
    anchor_quotes_json: str
    implementation_sha256: str

    @property
    def sha256(self):
        return _sha(_json(asdict(self)).encode("utf-8"))


@dataclass(frozen=True)
class ObservedPublication:
    decision: DecisionEvidence
    timing: PublicationTiming
    observation_recorded_ts_ms: int
    durable_publication_verified: bool = False


def prepare_decision(recorder, product, cutoff, direction, *, asof):
    """Freeze a diagnostic input row before recording a publication."""
    row = build_timed_features(recorder, product, cutoff, direction, asof=asof)
    quotes = {
        pid: recorder._quote_at(pid, cutoff, asof)[0]
        for pid in dict.fromkeys((product, BENCHMARK))
    }
    features_json, quotes_json = _json(row), _json(quotes)
    implementation = _sha(SOURCE.read_text(encoding="utf-8").encode("utf-8"))
    return DecisionEvidence(
        DECISION_VERSION,
        product,
        direction,
        cutoff,
        asof,
        row["computation_completed_ts_ms"],
        recorder._now(),
        features_json,
        quotes_json,
        implementation,
    )


def _prefix_at(recorder, asof):
    prefix = hashlib.sha256()
    count = 0
    for packet in recorder.packets:
        if packet.available_ts_ms > asof:
            return count, prefix.hexdigest(), packet
        prefix.update((_json(asdict(packet)) + "\n").encode("utf-8"))
        count += 1
    return count, prefix.hexdigest(), None


def _check_prefix(recorder, decision, row):
    baseline = row["baseline"]
    if recorder.inventory_sha256 != baseline["inventory_sha256"] or (
        recorder.inventory_recorded_ts_ms != baseline["inventory_recorded_ts_ms"]
    ):
        raise ValueError("decision and recorder inventory differ")
    sources = (
        ("input", recorder),
        ("book", recorder.book),
        ("monitor", recorder.book.monitor),
    )
    if any(
        baseline[f"{name}_implementation_sha256"] != source.source_sha256
        or baseline[f"{name}_contract_sha256"] != source.contract_sha256
        for name, source in sources
    ):
        raise ValueError("decision and recorder source provenance differ")
    count, digest, _ = _prefix_at(recorder, decision.knowledge_asof_ts_ms)
    if (count, digest) != (
        baseline["known_packet_count"],
        baseline["known_packet_prefix_sha256"],
    ):
        raise ValueError("decision and recorder evidence prefix differ")


def observe_publication(
    recorder, decision, *, publication_id, published, max_feature_age_ms=None
):
    """Bind an observed timestamp. Its source remains a caller assertion."""
    if recorder.failed:
        raise ValueError("failed evidence recorder")
    _integer(published)
    row = json.loads(decision.feature_json)
    _check_prefix(recorder, decision, row)
    timing = publication_timing(
        publication_id=publication_id,
        product_id=decision.product_id,
        feature_cutoff=decision.feature_cutoff_ts_ms,
        inputs_available=decision.feature_computation_completed_ts_ms,
        decision_completed=decision.decision_completed_ts_ms,
        published=published,
        max_feature_age_ms=max_feature_age_ms,
    )
    recorded = recorder._now()
    if published > recorded:
        raise ValueError("publication time has not been reached")
    return ObservedPublication(decision, timing, recorded)


def _input_trade_windows(row):
    baseline = row["baseline"]
    product, cutoff = row["product_id"], row["feature_cutoff_ts_ms"]
    for pid in dict.fromkeys((product, BENCHMARK)):
        yield pid, baseline["sigma_start_ts_ms"] - GRID_MS, baseline["sigma_end_ts_ms"]
    yield product, baseline["pace_start_ts_ms"], baseline["pace_end_ts_ms"]
    yield product, cutoff - PACE_MS, cutoff
    yield product, row["candle_start_ts_ms"], row["candle_end_ts_ms"]


def _mid(quote):
    bid, ask = float(quote["bid"]), float(quote["ask"])
    return bid + (ask - bid) / 2


def _forward_metrics(quotes, product, direction, volatility, trades, horizon, cfg):
    first_coin, first_btc = (_mid(quotes[0][pid]) for pid in (product, BENCHMARK))
    sign = 1 if direction == "up" else -1
    path = [
        sign
        * (
            (math.log(_mid(point[product])) - math.log(first_coin))
            - volatility["beta"]
            * (math.log(_mid(point[BENCHMARK])) - math.log(first_btc))
        )
        for point in quotes
    ]
    sigma = max(volatility["sigma_1m"], cfg["sigma_floor_1m"])
    rules = cfg["impulse"]
    entry = quotes[0][product]
    spread = (float(entry["ask"]) - float(entry["bid"])) / first_coin
    required = max(
        rules["terminal_sigma_multiple"] * sigma * math.sqrt(horizon / 60),
        rules["minimum_terminal_log_return"],
        rules["entry_spread_multiple"] * spread,
    )
    terminal, peak = path[-1], max(path)
    retention = terminal / peak if peak > 0 else None
    tolerance = cfg["comparison_tolerance"]
    verified = (
        terminal + tolerance >= required
        and retention is not None
        and retention + tolerance >= rules["minimum_peak_retention"]
        and trades >= rules["minimum_forward_matches"]
    )
    return dict(
        status="ready",
        reason=None,
        cutoff_verified_forward=verified,
        terminal_residual_log=terminal,
        required_terminal_log=required,
        peak_residual_log=peak,
        retention=retention,
        forward_match_count=trades,
    )


def _mature_grade(recorder, decision, row, end, asof, horizon, cfg):
    product, start = decision.product_id, decision.feature_cutoff_ts_ms
    missing = [
        name for name, result in row["features"].items() if result["status"] != "ready"
    ]
    if missing:
        return dict(
            status="unavailable",
            reason="decision_features_unavailable",
            missing_features=missing,
        )

    # Later conflicts may invalidate an input proof but cannot change the
    # frozen feature, baseline, or anchor price that the decision actually used.
    for pid, left, right in _input_trade_windows(row):
        _, _, reason, _ = recorder._trade_window(pid, left, right, asof)
        if reason:
            return dict(
                status="unavailable",
                reason=reason,
                evidence_scope="decision_trade_window",
                product_with_missing_evidence=pid,
            )

    trade_count = None
    for pid in dict.fromkeys((product, BENCHMARK)):
        _, trades, reason, _ = recorder._trade_window(pid, start - GRID_MS, end, asof)
        if reason:
            return dict(
                status="unavailable",
                reason=reason,
                evidence_scope="outcome_trade_window",
                product_with_missing_evidence=pid,
            )
        if pid == product:
            trade_count = sum(start < trade.receipt_ts_ms < end for trade in trades)

    anchor_quotes = json.loads(decision.anchor_quotes_json)
    quotes = []
    for cutoff in range(start, end + 1, GRID_MS):
        point = {}
        for pid in anchor_quotes:
            quote, _ = recorder._quote_at(pid, cutoff, asof)
            if not quote["available"]:
                return dict(
                    status="unavailable",
                    reason=quote["reason"],
                    evidence_scope="outcome_quote",
                    missing_quote_ts_ms=cutoff,
                    product_with_missing_evidence=pid,
                )
            if cutoff == start and quote != anchor_quotes[pid]:
                return dict(
                    status="unavailable",
                    reason="decision_anchor_quote_changed",
                    product_with_missing_evidence=pid,
                )
            point[pid] = quote
        quotes.append(anchor_quotes if cutoff == start else point)

    return _forward_metrics(
        quotes,
        product,
        decision.direction,
        row["baseline"]["volatility"],
        trade_count,
        horizon,
        cfg,
    )


def grade_publication(recorder, publication, horizon_seconds, *, asof):
    """Compute a new offline grade without modifying the decision snapshot."""
    if recorder.failed:
        raise ValueError("failed evidence recorder")
    cfg, impulse_sha = load_contract(V2_CONTRACT_PATH)
    if (
        type(horizon_seconds) is not int
        or horizon_seconds not in cfg["outcome_horizons_seconds"]
    ):
        raise ValueError("unsupported horizon")
    _integer(asof)
    if not publication.observation_recorded_ts_ms <= asof <= recorder._now():
        raise ValueError(
            "grading as-of must include recorded publication and have elapsed"
        )
    decision = publication.decision
    row = json.loads(decision.feature_json)
    _check_prefix(recorder, decision, row)
    end = decision.feature_cutoff_ts_ms + horizon_seconds * 1000
    count, prefix, pending_packet = _prefix_at(recorder, asof)
    result = dict(
        version=GRADE_VERSION,
        grading_packet_count=count,
        grading_packet_prefix_sha256=prefix,
        decision_sha256=decision.sha256,
        publication_id=publication.timing.publication_id,
        published_ts_ms=publication.timing.published_ts_ms,
        product_id=decision.product_id,
        direction=decision.direction,
        feature_cutoff_ts_ms=decision.feature_cutoff_ts_ms,
        horizon_seconds=horizon_seconds,
        horizon_end_ts_ms=end,
        knowledge_asof_ts_ms=asof,
        publication_before_horizon_end=publication.timing.published_ts_ms < end,
        impulse_rule_source_sha256=impulse_sha,
        scope="offline_cutoff_outcome_diagnostic",
        evaluation_only=True,
        fitting_allowed=False,
        status="pending",
        reason="horizon_not_mature",
        cutoff_verified_forward=None,
    )
    if asof >= end:
        # A lower-level monitor may have processed a packet while the final
        # payload is pending. Decline grading across that partial handoff.
        if (
            pending_packet
            and pending_packet.receipt_ts_ms < asof
            and pending_packet.processing_started_ts_ms <= asof
        ):
            result.update(
                status="unavailable", reason="grading_payload_processing_incomplete"
            )
        else:
            result.update(
                _mature_grade(recorder, decision, row, end, asof, horizon_seconds, cfg)
            )
    result["grade_computation_completed_ts_ms"] = recorder._now()
    return result
