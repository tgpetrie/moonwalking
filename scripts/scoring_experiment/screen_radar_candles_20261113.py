"""Run exploratory candle screens against the existing offline archive."""

import argparse
import csv
import json
import math
import sqlite3
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

import numpy as np
import pandas as pd

from live_movers_run import CAPTURE, boot_moving, verify_inputs
from screen_board_runners_20261113 import sustained_move

START = int(datetime(2026, 9, 7, tzinfo=timezone.utc).timestamp())
SPLIT = START + 21 * 86400
END = START + 35 * 86400
FIRST_MINUTE = START // 60 - 1441
LAST_MINUTE = END // 60 + 16
STABLECOINS = {"USDC", "USDT", "DAI", "PYUSD", "GUSD", "USDS", "EURC"}
CANDLES = Path.home() / ".moonwalking/data/candle_archive.sqlite"


def read_only(path):
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    db.execute("PRAGMA query_only=ON")
    return db


def load_market(db):
    products = [
        product
        for (product,) in db.execute(
            "SELECT DISTINCT product_id FROM candles WHERE granularity = 60 ORDER BY 1"
        )
        if product.endswith("-USD") and product[:-4] not in STABLECOINS
    ]
    close = np.full((len(products), LAST_MINUTE - FIRST_MINUTE), np.nan)
    volume = np.full_like(close, np.nan)
    for i, product in enumerate(products):
        rows = db.execute(
            """SELECT ts, close, volume FROM candles
               WHERE product_id = ? AND granularity = 60 AND ts >= ? AND ts < ?""",
            (product, 60 * FIRST_MINUTE, 60 * LAST_MINUTE),
        )
        for stamp, price, size in rows:
            if stamp % 60 == 0 and price > 0 and math.isfinite(price):
                minute = stamp // 60 - FIRST_MINUTE
                close[i, minute] = price
                if size >= 0 and math.isfinite(size):
                    volume[i, minute] = price * size
    return products, close, volume


def load_board_rows(capture):
    with (capture / "eligible_episodes.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        eligible = {
            int(row["id"]): row
            for row in csv.DictReader(handle)
            if START <= int(row["entered_ts"]) < END
        }
    # The frozen episode index already requires observed 5m and 15m marks.
    columns = """id, board, product_id, direction, entered_ts, start_change_pct,
        feature_snapshot_json, gross_return_5m, gross_return_15m, gross_return_30m,
        max_favorable_15m, max_adverse_15m, outcome_15m"""
    with closing(read_only(capture / "board_episodes.sqlite")) as db:
        rows = db.execute(
            f"SELECT {columns} FROM episodes WHERE entered_ts >= ? AND entered_ts < ?",
            (START, END),
        )
        for (
            identity,
            board,
            product,
            direction,
            entered,
            move,
            snapshot,
            five,
            fifteen,
            thirty,
            peak,
            adverse,
            status,
        ) in rows:
            frozen = eligible.pop(identity, None)
            if frozen is None:
                continue
            assert (
                frozen["board"],
                frozen["direction"],
                frozen["product_id"],
                int(frozen["entered_ts"]),
            ) == (board, direction, product, entered)
            captured = json.loads(snapshot)["captured_ts"]
            graded = status not in (None, "interrupted") and all(
                value is not None and math.isfinite(value)
                for value in (five, fifteen, thirty, peak, adverse)
            )
            if move is None or not math.isfinite(move):
                continue
            sign = -1 if direction == "down" else 1
            yield (
                identity,
                f"{board}/{direction}",
                product,
                captured,
                entered,
                sign * move,
                sign,
                sustained_move(peak, five, fifteen, thirty) if graded else None,
                sustained_move(-adverse, -five, -fifteen, -thirty) if graded else None,
            )
    assert not eligible


def board_features(rows, products, close, volume):
    scores = rows.copy()
    index = {product: i for i, product in enumerate(products)}
    scores = scores[scores["product"].isin(index)].copy()
    coin = scores["product"].map(index).to_numpy()
    # The bar closes at open + 60 and becomes eligible at open + 120.
    minute = scores["captured"].to_numpy() // 60 - FIRST_MINUTE - 2
    btc = index["BTC-USD"]
    with np.errstate(invalid="ignore"):
        history = np.log(close[coin[:, None], minute[:, None] - 3 - np.arange(61)])
        sigma = np.sqrt(np.mean(np.diff(history, axis=1) ** 2, axis=1))
        scores["unusual_move"] = scores["raw_move"] / np.maximum(sigma, 0.001)
        scores["usd_activity"] = volume[
            coin[:, None], minute[:, None] - np.arange(3)
        ].sum(axis=1)
        coin_return = np.log(close[coin, minute] / close[coin, minute - 3])
        btc_return = np.log(close[btc, minute] / close[btc, minute - 3])
        scores["btc_relative"] = np.where(
            coin == btc, np.nan, scores["sign"] * (coin_return - btc_return)
        )
    return rows.merge(
        scores[["id", "unusual_move", "usd_activity", "btc_relative"]],
        on="id",
        how="left",
        validate="one_to_one",
    )


def ranked_rates(rows, signal):
    budget = len(rows) // 4
    flags = rows.sort_values(
        [signal, "raw_move", "id"], ascending=[False, False, True]
    ).head(budget)
    grades = flags.dropna(subset=["runner"])
    if grades.empty:
        return None
    return (
        grades["runner"].mean(),
        grades["reversal"].mean(),
        len(grades),
        budget,
    )


def board_results(rows):
    rows["day"] = pd.to_datetime(rows["entered"], unit="s", utc=True).dt.strftime(
        "%Y-%m-%d"
    )
    for stratum, board in rows.groupby("board"):
        for signal in ("unusual_move", "usd_activity", "btc_relative"):
            matched = board.dropna(subset=[signal])
            results = []
            for day, same_day in matched.groupby("day"):
                if len(same_day) < 20:
                    continue
                reference = ranked_rates(same_day, "raw_move")
                candidate = ranked_rates(same_day, signal)
                full = ranked_rates(board[board["day"] == day], "raw_move")
                if reference and candidate and full:
                    results.append((day, *candidate, *reference, full[0], full[1]))
            daily = pd.DataFrame(
                results,
                columns=[
                    "day",
                    "runner",
                    "reversal",
                    "grades",
                    "flags",
                    "ref_runner",
                    "ref_reversal",
                    "ref_grades",
                    "ref_flags",
                    "full_runner",
                    "full_reversal",
                ],
            ).set_index("day")
            daily["gain"] = daily["runner"] - daily["ref_runner"]
            daily["gap"] = daily["runner"] - daily["reversal"]
            split = datetime.fromtimestamp(SPLIT, timezone.utc).date().isoformat()
            windows = [daily[daily.index < split], daily[daily.index >= split]]
            interval = boot_moving(daily["gain"] * 100, 5000, 20261113)
            result = {
                "rows": len(board),
                "matched": len(matched),
                "matched_graded": int(matched["runner"].notna().sum()),
                "products": int(board["product"].nunique()),
                "matched_products": int(matched["product"].nunique()),
                "product_days": int(
                    board[["product", "day"]].drop_duplicates().shape[0]
                ),
                "matched_product_days": int(
                    matched[["product", "day"]].drop_duplicates().shape[0]
                ),
                "windows": [
                    {
                        "days": len(window),
                        **{
                            k: round(float(window[k].mean()) * 100, 2)
                            for k in (
                                "runner",
                                "reversal",
                                "ref_runner",
                                "ref_reversal",
                                "full_runner",
                                "full_reversal",
                                "gain",
                                "gap",
                            )
                        },
                        "flag_grade_pct": round(
                            100 * window["grades"].sum() / window["flags"].sum(), 2
                        ),
                        "reference_grade_pct": round(
                            100
                            * window["ref_grades"].sum()
                            / window["ref_flags"].sum(),
                            2,
                        ),
                    }
                    for window in windows
                ],
                "gain_block_95_pp": interval,
            }
            print(stratum, signal, json.dumps(result), flush=True)


def ranking_inputs(close, volume):
    # Dense masks are computed only across the declared archived roster.
    log_close = np.log(close)
    activity = np.isfinite(close).astype(np.int32)
    observed = np.pad(np.cumsum(activity, axis=1, dtype=np.int32), ((0, 0), (1, 0)))
    with np.errstate(invalid="ignore"):
        squared = np.diff(log_close, axis=1, prepend=np.nan) ** 2
    squared_sum = np.pad(np.cumsum(np.nan_to_num(squared), axis=1), ((0, 0), (1, 0)))
    dollar_sum = np.pad(np.cumsum(np.nan_to_num(volume), axis=1), ((0, 0), (1, 0)))
    volume_count = np.pad(
        np.cumsum(np.isfinite(volume), axis=1, dtype=np.int32), ((0, 0), (1, 0))
    )
    return log_close, observed, squared_sum, dollar_sum, volume_count


def ranked_movers(log_close, observed, minute):
    one = log_close[:, minute] - log_close[:, minute - 1]
    three = log_close[:, minute] - log_close[:, minute - 3]
    active = (observed[:, minute + 1] - observed[:, minute - 1439] >= 30) & (
        observed[:, minute + 1] - observed[:, minute - 59] >= 5
    )
    return one, three, active


def top_eight(one, three, active, sign):
    leaders = set()
    for values in (one * sign, three * sign):
        available = np.flatnonzero(active & np.isfinite(values) & (values > 0))
        order = np.argsort(-values[available], kind="stable")
        leaders.update(available[order[:8]])
    return leaders


def early_grade(close, log_close, observed, product, cutoff, available_minute):
    start_price = close[product, available_minute]
    forward = close[product, cutoff : cutoff + 15]
    if len(forward) != 15 or not np.isfinite(forward).all():
        return None
    returns = (forward / start_price - 1) * 100
    if returns[14] >= 1 and returns[4] > -0.5:
        sign = 1
    elif returns[14] <= -1 and returns[4] < 0.5:
        sign = -1
    else:
        return 0, None
    lead = None
    for offset in range(1, 11):
        minute = available_minute + offset
        one, three, active = ranked_movers(log_close, observed, minute)
        if product in top_eight(one, three, active, sign):
            lead = offset
            break
    return sign if lead is not None or (sign * returns).max() >= 1.5 else 0, lead


def early_results(close, volume):
    log_close, observed, squared, dollar, volume_count = ranking_inputs(close, volume)
    for feature in ("usd_pace", "unusual_move"):
        last = {arm: np.full(close.shape[0], -100) for arm in ("raw_move", feature)}
        samples = {arm: [] for arm in last}
        candidate_counts = []
        for cutoff in range(START // 60 - FIRST_MINUTE, END // 60 - FIRST_MINUTE, 5):
            minute = cutoff - 2
            one, three, active = ranked_movers(log_close, observed, minute)
            eligible = active & np.isfinite(one) & (three >= math.log1p(0.003))
            eligible[list(top_eight(one, three, active, 1))] = False
            if feature == "usd_pace":
                recent = dollar[:, minute + 1] - dollar[:, minute - 2]
                earlier = dollar[:, minute - 2] - dollar[:, minute - 59]
                score = np.log((recent + 500) / (earlier / 19 + 500))
                eligible &= (
                    volume_count[:, minute + 1] - volume_count[:, minute - 59] == 60
                )
            else:
                variance = (squared[:, minute - 2] - squared[:, minute - 62]) / 60
                score = three / np.maximum(np.sqrt(np.maximum(variance, 0)), 0.001)
                eligible &= observed[:, minute - 2] - observed[:, minute - 63] == 61
            candidate_counts.append(int(eligible.sum()))
            for arm, values in (("raw_move", three), (feature, score)):
                candidates = np.flatnonzero(eligible & (cutoff - last[arm] >= 60))
                if not len(candidates):
                    continue
                product = candidates[np.argmax(values[candidates])]
                last[arm][product] = cutoff
                samples[arm].append(
                    early_grade(close, log_close, observed, product, cutoff, minute)
                )
        for arm, flags in samples.items():
            graded = [grade for grade in flags if grade is not None]
            successful_leads = [
                lead for result, lead in graded if result == 1 and lead is not None
            ]
            print(
                "early_watch",
                feature,
                arm,
                json.dumps(
                    {
                        "cutoffs": len(candidate_counts),
                        "cutoffs_with_candidates": sum(n > 0 for n in candidate_counts),
                        "flags": len(flags),
                        "graded": len(graded),
                        "runner_pct": round(
                            100 * mean(result == 1 for result, _ in graded), 2
                        ),
                        "reversal_pct": round(
                            100 * mean(result == -1 for result, _ in graded), 2
                        ),
                        "successful_graduations": len(successful_leads),
                        "median_lead_min": (
                            float(np.median(successful_leads))
                            if successful_leads
                            else None
                        ),
                    }
                ),
                flush=True,
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", choices=("board", "early"))
    parser.add_argument("--capture", type=Path, default=CAPTURE)
    parser.add_argument("--archive", type=Path, default=CANDLES)
    args = parser.parse_args()
    with closing(read_only(args.archive)) as db:
        db.execute("BEGIN")
        products, close, volume = load_market(db)
    print(
        "roster",
        len(products),
        "traded_minute_bars",
        int(np.isfinite(close).sum()),
        flush=True,
    )
    if args.study == "board":
        verify_inputs(args.capture)
        rows = pd.DataFrame(
            load_board_rows(args.capture),
            columns=[
                "id",
                "board",
                "product",
                "captured",
                "entered",
                "raw_move",
                "sign",
                "runner",
                "reversal",
            ],
        )
        board_results(board_features(rows, products, close, volume))
    else:
        early_results(close, volume)


if __name__ == "__main__":
    main()
