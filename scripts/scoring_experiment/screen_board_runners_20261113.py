"""Reproduce the exploratory runner screen on the verified November 13 snapshot."""

import argparse
import hashlib
import json
import math
import sqlite3
from collections import Counter, defaultdict, deque
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from statistics import mean, median

EXPECTED_DIGEST = "7a3eca1482726d7b5bc431c41bb2fc73929f4abe3635afb2edf5e9315ddea82c"
START = int(datetime(2026, 10, 28, tzinfo=timezone.utc).timestamp())
END = int(datetime(2026, 11, 13, tzinfo=timezone.utc).timestamp())


def top_fraction_weights(scores, fraction, *, round_up=True):
    """Weight ties equally at a fixed budget."""
    counts = Counter(scores)
    round_budget = math.ceil if round_up else math.floor
    remaining = round_budget(len(scores) * fraction)
    weights = {}
    for score, count in sorted(counts.items(), reverse=True):
        weights[score] = min(count, remaining) / count
        remaining = max(0, remaining - count)
    return weights


def load_days(con):
    prior = defaultdict(deque)
    days = defaultdict(list)
    for row in con.execute(
        """
        SELECT id, board, product_id, direction, entered_ts, entry_rank, start_change_pct,
               feature_snapshot_json, gross_return_5m, gross_return_15m, gross_return_30m,
               max_favorable_15m, max_adverse_15m, outcome_15m
        FROM episodes WHERE entered_ts >= ? AND entered_ts < ? ORDER BY entered_ts,id
    """,
        (START - 86400, END),
    ):
        ts = row["entered_ts"]
        history = prior[row["board"], row["product_id"]]
        while history and history[0] < ts - 86400:
            history.popleft()
        repeat = len(history)
        assert not history or history[-1] < ts
        history.append(ts)
        if ts < START:
            continue
        key = (row["board"], row["direction"], ts // 86400)
        snapshot = json.loads(row["feature_snapshot_json"] or "null") or {}
        raw = snapshot.get("raw_inputs") or {}
        fields = [
            snapshot.get("live_score"),
            raw.get("pct_1m"),
            raw.get("pct_3m"),
            raw.get("volume_change_1h_pct"),
            row["start_change_pct"],
        ]
        scores = None
        if (
            all(
                isinstance(value, (int, float)) and math.isfinite(value)
                for value in fields
            )
            and isinstance(snapshot.get("captured_ts"), int)
            and 0 <= ts - snapshot["captured_ts"] <= 60
        ):
            live, move_1m, move_3m, volume, board_move = fields
            if min(move_1m, move_3m) > -100:
                sign = 1 if row["direction"] == "up" else -1
                speed = (
                    sign
                    * (3 * math.log1p(move_1m / 100) - math.log1p(move_3m / 100))
                    / 2
                )
                scores = {
                    "board_move": sign * board_move,
                    "entry_rank": -row["entry_rank"],
                    "live_score": sign * live,
                    "acceleration": speed,
                    "volume_change_1h": volume,
                    "prior_entries_24h": repeat,
                }
        outcome_15m = row["gross_return_15m"]
        peak = row["max_favorable_15m"]
        drawdown = row["max_adverse_15m"]
        gradable = (
            isinstance(outcome_15m, (int, float))
            and math.isfinite(outcome_15m)
            and row["outcome_15m"] not in (None, "interrupted")
            and isinstance(peak, (int, float))
            and math.isfinite(peak)
        )
        if gradable and (
            not isinstance(drawdown, (int, float)) or not math.isfinite(drawdown)
        ):
            raise ValueError(f"Adverse excursion missing for gradable row {row['id']}")
        days[key].append(
            (
                scores,
                peak if gradable else None,
                drawdown if gradable else None,
                outcome_15m if gradable else None,
                row["gross_return_5m"],
                row["gross_return_30m"],
            )
        )
    return days


def summarize(days):
    by_board = defaultdict(list)
    for (board, direction, _), rows in sorted(days.items()):
        outcomes = [
            (peak, adverse) for _, peak, adverse, *_ in rows if peak is not None
        ]
        tail_index = math.ceil(len(outcomes) * 0.05) - 1
        runner_cutoff = sorted((peak for peak, _ in outcomes), reverse=True)[tail_index]
        crasher_cutoff = sorted(adverse for _, adverse in outcomes)[tail_index]
        matched = [row for row in rows if row[0] is not None]
        gradable = [row for row in matched if row[1] is not None]
        runners = sum(peak >= runner_cutoff for _, peak, *_ in gradable)
        crashers = sum(adverse <= crasher_cutoff for _, _, adverse, *_ in gradable)
        rates = {
            name: flag_rates(
                matched,
                gradable,
                name,
                runner_cutoff,
                crasher_cutoff,
                runners,
                crashers,
            )
            for name in matched[0][0]
        }
        by_board[board, direction].append(
            {
                "rows": len(rows),
                "matched": len(matched),
                "graded": len(gradable),
                "threshold": runner_cutoff,
                "crasher_threshold": crasher_cutoff,
                "base_rate": runners / len(gradable),
                "crasher_base_rate": crashers / len(gradable),
                "mean_flags": math.ceil(len(matched) * 0.2),
                "rates": rates,
            }
        )

    return by_board


def flag_rates(
    matched, gradable, name, runner_cutoff, crasher_cutoff, runners, crashers
):
    weights = top_fraction_weights([scores[name] for scores, *_ in matched], 0.2)
    flagged = sum(weights[scores[name]] for scores, *_ in matched)
    graded = sum(weights[scores[name]] for scores, *_ in gradable)
    unflagged = len(gradable) - graded
    runner_hits = crasher_hits = both_hits = favorable_one = adverse_one = (
        terminal_one
    ) = 0.0
    for scores, peak, adverse, terminal, *_ in gradable:
        weight = weights[scores[name]]
        runner = peak >= runner_cutoff
        crasher = adverse <= crasher_cutoff
        runner_hits += weight * runner
        crasher_hits += weight * crasher
        both_hits += weight * (runner and crasher)
        favorable_one += weight * (peak >= 1)
        adverse_one += weight * (adverse <= -1)
        terminal_one += weight * (terminal >= 1)
    return {
        "flagged_runner_pct": runner_hits / graded,
        "unflagged_runner_pct": (runners - runner_hits) / unflagged,
        "flagged_crasher_pct": crasher_hits / graded,
        "unflagged_crasher_pct": (crashers - crasher_hits) / unflagged,
        "flagged_both_pct": both_hits / graded,
        "flagged_gradable_pct": graded / flagged,
        "flagged_peak_ge_1pct": favorable_one / graded,
        "flagged_adverse_le_minus_1pct": adverse_one / graded,
        "flagged_terminal_ge_1pct": terminal_one / graded,
        "runner_minus_crasher_pp": (runner_hits - crasher_hits) / graded,
    }


def block_interval(values):
    """Exploratory 95% interval using overlapping three-day blocks."""
    blocks = [values[index : index + 3] for index in range(len(values) - 2)]
    rng = Random(20261113)
    draws = []
    for _ in range(5000):
        sampled = rng.choices(blocks, k=math.ceil(len(values) / 3))
        draws.append(
            mean([value for block in sampled for value in block][: len(values)])
        )
    draws.sort()
    return [round(100 * draws[index], 2) for index in (125, 4874)]


def sustained_move(peak, return_5m, return_15m, return_30m):
    """Carbon's proposed absolute label, using gross direction-aligned returns."""
    return return_15m >= 1 and return_5m > -0.5 and max(peak, return_30m) >= 1.5


def summarize_sustained(days):
    by_board = defaultdict(list)
    for (board, direction, _), rows in sorted(days.items()):
        matched = [row for row in rows if row[0] is not None]
        graded = [
            (
                scores,
                sustained_move(peak, five, fifteen, thirty),
                sustained_move(-adverse, -five, -fifteen, -thirty),
            )
            for scores, peak, adverse, fifteen, five, thirty in matched
            if peak is not None
            and all(
                isinstance(value, (int, float)) and math.isfinite(value)
                for value in (five, thirty)
            )
        ]
        rates = {}
        for name in matched[0][0]:
            weights = top_fraction_weights(
                [scores[name] for scores, *_ in matched], 0.25, round_up=False
            )
            observed = sum(weights[scores[name]] for scores, *_ in graded)
            rates[name] = (
                sum(weights[scores[name]] * runner for scores, runner, _ in graded)
                / observed,
                sum(weights[scores[name]] * reversal for scores, _, reversal in graded)
                / observed,
            )
        by_board[board, direction].append(
            (
                len(graded),
                mean(runner for _, runner, _ in graded),
                mean(reversal for _, _, reversal in graded),
                rates,
            )
        )
    return by_board


def print_sustained(days):
    for (board, direction), per_day in sorted(summarize_sustained(days).items()):
        print(
            board,
            direction,
            json.dumps(
                {
                    "days": len(per_day),
                    "graded": sum(count for count, *_ in per_day),
                    "base_runner_pct": round(
                        100 * mean(runner for _, runner, _, _ in per_day), 2
                    ),
                    "base_reversal_pct": round(
                        100 * mean(reversal for _, _, reversal, _ in per_day), 2
                    ),
                }
            ),
        )
        for name in per_day[0][3]:
            pairs = [rates[name] for _, _, _, rates in per_day]
            gap = [runner - reversal for runner, reversal in pairs]
            print(
                name,
                json.dumps(
                    {
                        "flagged_runner_pct": round(
                            100 * mean(runner for runner, _ in pairs), 2
                        ),
                        "flagged_reversal_pct": round(
                            100 * mean(reversal for _, reversal in pairs), 2
                        ),
                        "runner_minus_reversal_pp": round(100 * mean(gap), 2),
                        "runner_minus_reversal_block95_pp": block_interval(gap),
                    }
                ),
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument(
        "--carbon", action="store_true", help="Use the sustained-move labels."
    )
    args = parser.parse_args()
    capture = args.capture.resolve()
    with capture.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != EXPECTED_DIGEST:
            parser.error("Capture SHA-256 differs from the archived replication input.")
    with closing(
        sqlite3.connect(capture.as_uri() + "?mode=ro&immutable=1", uri=True)
    ) as con:
        con.row_factory = sqlite3.Row
        days = load_days(con)
    if args.carbon:
        print_sustained(days)
        return
    by_board = summarize(days)

    for (board, direction), per_day in sorted(by_board.items()):
        print(
            board,
            direction,
            json.dumps(
                {
                    "days": len(per_day),
                    "rows": sum(x["rows"] for x in per_day),
                    "matched": sum(x["matched"] for x in per_day),
                    "graded": sum(x["graded"] for x in per_day),
                    "base_pct": round(100 * mean(x["base_rate"] for x in per_day), 2),
                    "crasher_base_pct": round(
                        100 * mean(x["crasher_base_rate"] for x in per_day), 2
                    ),
                    "daily_tail_floor_pct": [
                        round(f(x["threshold"] for x in per_day), 3)
                        for f in (min, median, max)
                    ],
                    "daily_crasher_cutoff_pct": [
                        round(f(x["crasher_threshold"] for x in per_day), 3)
                        for f in (min, median, max)
                    ],
                    "flags_per_calendar_hour": round(
                        mean(x["mean_flags"] for x in per_day) / 24, 2
                    ),
                }
            ),
        )
        for name in per_day[0]["rates"]:
            rates = [x["rates"][name] for x in per_day]
            summary = {
                key: round(100 * mean(row[key] for row in rates), 2) for key in rates[0]
            }
            gap = [row["runner_minus_crasher_pp"] for row in rates]
            gap_over_move = [
                row["runner_minus_crasher_pp"]
                - day["rates"]["board_move"]["runner_minus_crasher_pp"]
                for row, day in zip(rates, per_day, strict=True)
            ]
            better_than_move = sum(
                x["rates"][name]["flagged_runner_pct"]
                > x["rates"]["board_move"]["flagged_runner_pct"]
                for x in per_day
            )
            print(
                name,
                json.dumps(
                    dict(
                        summary,
                        days_beating_board_move=better_than_move,
                        days_runner_rate_above_crasher_rate=sum(
                            value > 0 for value in gap
                        ),
                        runner_minus_crasher_block95_pp=block_interval(gap),
                        gap_vs_board_move_pp=round(100 * mean(gap_over_move), 2),
                        gap_vs_board_move_block95_pp=block_interval(gap_over_move),
                    )
                ),
            )


if __name__ == "__main__":
    main()
