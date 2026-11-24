"""Pair legacy offline ticker snapshots at one immutable knowledge cutoff."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from instant_targets import Sample


VERSION = "instant-paired-sample-v1-draft"
CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "docs/research/INSTANT_PAIRED_SAMPLE_CONTRACT_V1_DRAFT.json"
)


@dataclass(frozen=True)
class PairedSample:
    version: str
    product_id: str
    ts_ms: int
    sample: Sample | None
    unavailable_reasons: tuple[str, ...]
    coin_flow_available: bool
    producer_recorder_sha256: str
    input_provenance_sha256: str
    adapter_sha256: str
    adapter_contract_sha256: str


def paired_sample(store, product, cutoff, *, benchmark="BTC-USD"):
    """No retrospective-asof override. Unavailable rows stay explicit and absent.

    Uses ReplayStore's existing evidence assertions and receipt quote TTL. It
    does not upgrade their trust or accept coverage-monitor proofs as quotes.
    """
    raw = CONTRACT.read_text(encoding="utf-8").encode("utf-8")
    cfg = json.loads(raw)
    if (
        cfg["version"] != VERSION
        or cfg["grid_ms"] != 5000
        or cfg["retrospective_override_allowed"] is not False
    ):
        raise ValueError("paired-sample contract and implementation differ")
    coin = store.snapshot(product, cutoff)
    btc = coin if product == benchmark else store.snapshot(benchmark, cutoff)
    reasons = tuple(
        f"{name}:{row['reason']}"
        for name, row in (("coin", coin), ("benchmark", btc))
        if row["reason"]
    )
    known = max(coin["available_ts_ms"], btc["available_ts_ms"])
    if known > cutoff:
        reasons += ("input_available_after_cutoff",)
    sample = (
        None
        if reasons
        else Sample(
            product_id=product,
            ts_ms=cutoff,
            bid=coin["bid"],
            ask=coin["ask"],
            btc_bid=btc["bid"],
            btc_ask=btc["ask"],
            quote_ts_ms=coin["quote_ts_ms"],
            btc_quote_ts_ms=btc["quote_ts_ms"],
            available_ts_ms=known,
            trade_count=coin["trade_count"],
            quote_volume_usd=coin["quote_volume_usd"],
            coverage_verified=coin["coverage_verified"] and btc["coverage_verified"],
            trade_count_at_bucket_start=coin["trade_count_at_bucket_start"],
        )
    )
    provenance = store.provenance()
    return PairedSample(
        VERSION,
        product,
        cutoff,
        sample,
        reasons,
        coin["flow_available"],
        provenance["producer_recorder_sha256"],
        hashlib.sha256(
            json.dumps(
                provenance, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        ).hexdigest(),
        hashlib.sha256(
            Path(__file__).read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest(),
        hashlib.sha256(raw).hexdigest(),
    )
