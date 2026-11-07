"""Run one continuous synthetic 67-minute stream through the real journal."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

from instant_coverage import WARMUP_PACKET_LIMIT
from instant_input_evidence import _file_sha
from instant_source_pilot import (
    CHANNELS,
    DURATION_S,
    LATER_ASOF_MS,
    PRODUCTS,
    SOFT_RECORD_BYTES,
    WARMUP_MS,
    capture,
)
from instant_stream_journal import StreamJournal, read_segment
from instant_timed_features import build_timed_features


# Depths observed in the initial four snapshots, with synthetic prices/sizes.
DEPTHS = dict(zip(PRODUCTS, ((17558, 22137), (2848, 10094), (49, 564), (104, 617))))
BOOK_FRAMES = dict(zip(PRODUCTS, (17, 12, 1, 12)))
CHANGES = dict(zip(PRODUCTS, (5, 3, 4, 4)))
PACKET_STOP = WARMUP_PACKET_LIMIT - 10


def _price(level):
    return f"{1000 + level / 100:.2f}"


def frames():
    yield 0, dict(
        type="subscriptions",
        channels=[
            dict(
                name="level2_50" if name == "level2_batch" else name,
                product_ids=PRODUCTS,
            )
            for name in CHANNELS
        ],
    )
    for product, (bids, asks) in DEPTHS.items():
        yield 0, dict(
            type="snapshot",
            product_id=product,
            bids=[[_price(-i), "1.12345678"] for i in range(1, bids + 1)],
            asks=[[_price(i), "1.12345678"] for i in range(1, asks + 1)],
        )
    watermarks = Counter({product: 10000 for product in PRODUCTS})
    for second in range(DURATION_S + 1):
        timestamp = datetime.fromtimestamp(second, timezone.utc).isoformat()
        batch = [
            dict(
                type="heartbeat",
                product_id=pid,
                last_trade_id=watermarks[pid],
                time=timestamp,
            )
            for pid in PRODUCTS
        ]
        for product, count in BOOK_FRAMES.items():
            for i in range(count):
                size = "1.12345678" if (i + second) % 2 else "2.12345678"
                batch.append(
                    dict(
                        type="l2update",
                        product_id=product,
                        time=timestamp,
                        changes=[
                            ["buy", _price(-level), size]
                            for level in range(1, CHANGES[product] + 1)
                        ],
                    )
                )
        participants = [PRODUCTS[0]] * 5 + [PRODUCTS[1]] * 2
        if second % 71 == 0:
            participants[-1] = PRODUCTS[2]
        if second % 109 == 0:
            participants[-2] = PRODUCTS[3]
        for pid in participants:
            watermarks[pid] += 1
            common = dict(
                product_id=pid,
                time=timestamp,
                trade_id=watermarks[pid],
                sequence=second * 60,
                price="1000.00",
            )
            batch.append(
                dict(
                    type="match",
                    **common,
                    side="sell",
                    size="0.12345678",
                    maker_order_id="11111111-1111-1111-1111-111111111111",
                    taker_order_id="22222222-2222-2222-2222-222222222222",
                )
            )
            batch.append(
                dict(
                    type="ticker",
                    **common,
                    side="buy",
                    last_size="0.12345678",
                    best_bid="999.99",
                    best_ask="1000.01",
                    best_bid_size="1.12345678",
                    best_ask_size="1.12345678",
                    open_24h="998.12",
                    high_24h="1010.12",
                    low_24h="992.12",
                    volume_24h="10000.12345678",
                    volume_30d="200000.12345678",
                )
            )
        for index, message in enumerate(batch, 1):
            yield second * 1000 + index * 1000 // (len(batch) + 1), message


class SyntheticSocket:
    def __init__(self):
        self.now = 0
        self._frames = frames()

    def wall_ms(self):
        return self.now

    def monotonic(self):
        return self.now / 1000

    def monotonic_ns(self):
        return self.now * 1000000

    def send(self, raw):
        assert json.loads(raw) == dict(
            type="subscribe", product_ids=list(PRODUCTS), channels=list(CHANNELS)
        )

    def recv(self):
        self.now, message = next(self._frames)
        return json.dumps(message, separators=(",", ":"))

    def close(self, timeout):
        self._frames.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    path = out / "synthetic.sqlite"
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    source = SyntheticSocket()
    start = time.perf_counter()
    with StreamJournal(
        path,
        PRODUCTS,
        WARMUP_MS,
        WARMUP_MS + 5000,
        max_packets=WARMUP_PACKET_LIMIT,
        clock_ms=source.wall_ms,
        monotonic_ns=source.monotonic_ns,
    ) as journal:
        run = capture(
            journal,
            lambda: source,
            monotonic=source.monotonic,
            duration_s=DURATION_S,
            packet_stop=PACKET_STOP,
            byte_stop=SOFT_RECORD_BYTES,
        )
        seconds = time.perf_counter() - start
        readiness = {}
        if not journal.evidence.failed:
            journal.finish()
            if source.now >= WARMUP_MS + LATER_ASOF_MS:
                for product in PRODUCTS:
                    started = time.perf_counter()
                    row = build_timed_features(
                        journal.evidence,
                        product,
                        WARMUP_MS,
                        "up",
                        asof=WARMUP_MS + LATER_ASOF_MS,
                    )
                    readiness[product] = dict(
                        baseline={
                            k: row["baseline"][k].get("reason", "ready")
                            for k in ("volatility", "pace")
                        },
                        features={
                            k: v.get("reason", "ready")
                            for k, v in row["features"].items()
                        },
                        calculation_ms=round((time.perf_counter() - started) * 1000, 3),
                    )
        logical_bytes = journal.record_bytes
    runtime_clock = time.get_clock_info("perf_counter")
    report = dict(
        version="instant-warmup-capacity-v1-draft",
        scope="synthetic_frames_virtual_receipt_clock_real_sqlite_commits",
        code_commit=commit,
        expected_virtual_seconds=DURATION_S,
        observed_virtual_ms=source.now,
        host_capture_seconds=round(seconds, 3),
        stop=run["stop"],
        connections=run["attempts"],
        frames=run["frames"],
        callback_through_commit={
            key: metrics["callback_through_commit"]
            for key, metrics in run["latencies"].items()
        },
        duration_clock=runtime_clock.implementation,
        duration_resolution_ns=runtime_clock.resolution * 1e9,
        snapshot_depths=DEPTHS,
        warmup_readiness=readiness,
        logical_record_bytes=logical_bytes,
        journal_bytes=path.stat().st_size,
        journal_sha256=_file_sha(path),
        segment=read_segment(path),
        feed_gate_pass=False,
        fitting_allowed=False,
    )
    (out / "REPORT.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Capacity run stopped: {run['stop']}. Report at {out / 'REPORT.json'}",
        flush=True,
    )


if __name__ == "__main__":
    main()
