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
from statistics import mean, median

EXPECTED_DIGEST = "7a3eca1482726d7b5bc431c41bb2fc73929f4abe3635afb2edf5e9315ddea82c"
START = int(datetime(2026, 10, 28, tzinfo=timezone.utc).timestamp())
END = int(datetime(2026, 11, 13, tzinfo=timezone.utc).timestamp())


def top_fraction_weights(scores, fraction):
    """Weight ties equally at a fixed budget."""
    counts = Counter(scores)
    remaining = math.ceil(len(scores) * fraction)
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
               feature_snapshot_json, gross_return_15m,
               max_favorable_15m, outcome_15m
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
        gradable = (
            isinstance(outcome_15m, (int, float))
            and math.isfinite(outcome_15m)
            and row["outcome_15m"] not in (None, "interrupted")
            and isinstance(row["max_favorable_15m"], (int, float))
            and math.isfinite(row["max_favorable_15m"])
        )
        days[key].append(
            (
                scores,
                row["max_favorable_15m"] if gradable else None,
                outcome_15m if gradable else None,
            )
        )
    return days


def summarize(days):
    by_board = defaultdict(list)
    for (board, direction, _), rows in days.items():
        peaks = [peak for _, peak, _ in rows if peak is not None]
        thresholds = sorted(peaks, reverse=True)
        threshold = thresholds[math.ceil(len(thresholds) * 0.05) - 1]
        matched = [row for row in rows if row[0] is not None]
        baseline_count = sum(
            peak >= threshold for _, peak, _ in matched if peak is not None
        )
        graded_count = sum(peak is not None for _, peak, _ in matched)
        rates = {}
        for name in matched[0][0]:
            weights = top_fraction_weights(
                [scores[name] for scores, *_ in matched], 0.2
            )
            flagged = sum(weights[scores[name]] for scores, *_ in matched)
            graded = sum(
                weights[scores[name]] for scores, peak, _ in matched if peak is not None
            )
            hits = sum(
                weights[scores[name]]
                for scores, peak, _ in matched
                if peak is not None and peak >= threshold
            )
            observed_one = sum(
                weights[scores[name]]
                for scores, peak, _ in matched
                if peak is not None and peak >= 1
            )
            terminal_one = sum(
                weights[scores[name]]
                for scores, peak, terminal in matched
                if peak is not None and terminal >= 1
            )
            rates[name] = (
                hits / graded,
                (baseline_count - hits) / (graded_count - graded),
                graded / flagged,
                observed_one / graded,
                terminal_one / graded,
            )
        by_board[board, direction].append(
            {
                "rows": len(rows),
                "matched": len(matched),
                "graded": graded_count,
                "threshold": threshold,
                "base_rate": baseline_count / graded_count,
                "mean_flags": math.ceil(len(matched) * 0.2),
                "rates": rates,
            }
        )

    return by_board


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()
    capture = args.capture.resolve()
    with capture.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != EXPECTED_DIGEST:
            parser.error("Capture SHA-256 differs from the archived replication input.")
    with closing(
        sqlite3.connect(capture.as_uri() + "?mode=ro&immutable=1", uri=True)
    ) as con:
        con.row_factory = sqlite3.Row
        by_board = summarize(load_days(con))

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
                    "daily_tail_floor_pct": [
                        round(f(x["threshold"] for x in per_day), 3)
                        for f in (min, median, max)
                    ],
                    "flags_per_calendar_hour": round(
                        mean(x["mean_flags"] for x in per_day) / 24, 2
                    ),
                }
            ),
        )
        for name in per_day[0]["rates"]:
            summary = [
                round(100 * mean(x["rates"][name][i] for x in per_day), 2)
                for i in range(5)
            ]
            better_than_move = sum(
                x["rates"][name][0] > x["rates"]["board_move"][0] for x in per_day
            )
            print(
                name,
                json.dumps(
                    dict(
                        zip(
                            (
                                "flagged_runner_pct",
                                "unflagged_runner_pct",
                                "flagged_gradable_pct",
                                "flagged_peak_ge_1pct",
                                "flagged_terminal_ge_1pct",
                            ),
                            summary,
                            strict=True,
                        ),
                        days_beating_board_move=better_than_move,
                    )
                ),
            )


if __name__ == "__main__":
    main()
