"""Fresh-data replication of the frozen live-movers rankers.

Protocol: docs/research/LIVE_MOVERS_FRESH_REPLICATION_PROTOCOL_20261113.md

    python scripts/scoring_experiment/live_movers_fresh_replication.py verify   # outcome-blind; may be repeated
    python scripts/scoring_experiment/live_movers_fresh_replication.py test     # once

verify  checks the frozen inputs, refits B2/M1 on the frozen train+discovery rows and requires the stored
        coefficients, copies the local ledger to a private capture and reports counts only.
test    scores the post-freeze window once with the unchanged models and applies the predeclared rule.

No parameter is fitted or selected on the fresh rows. The locked validation rows are never scored here.
"""
from __future__ import annotations

import argparse
import collections
import copy
import importlib.util
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/research/results/live_movers_fresh_replication_20261113"
WORK = Path.home() / ".moonwalking/analysis/live_movers_fresh_replication_20261113"
SOURCE = Path.home() / ".moonwalking/data/signal_outcomes.sqlite"
FROZEN_RESULT = ROOT / "docs/research/results/live_movers_comparison/results_test_live_movers.json"
PROTOCOL = ROOT / "docs/research/LIVE_MOVERS_FRESH_REPLICATION_PROTOCOL_20261113.md"

PHASES = {"secondary_gap": ["2026-10-18T00:00:00+00:00", "2026-10-28T00:00:00+00:00"],
          "test": ["2026-10-28T00:00:00+00:00", "2026-11-13T00:00:00+00:00"]}
CAPTURE_END = "2026-11-13T00:00:00+00:00"
PRIMARY = ("confirmation_3m_up/up", "h5")
SEED, REPS = 20261113, 5000
MIN_EFFECT, MIN_DAYS = 0.02, 12
PAIRS = (("B2", "B1"), ("B2", "B0"), ("M1", "B2"), ("M1", "B1"))


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/scoring_experiment/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fresh_config(cfg: dict) -> dict:
    """The frozen contract with only the date windows replaced."""
    out = copy.deepcopy(cfg)
    out["phases"] = copy.deepcopy(PHASES)
    return out


def frozen_models(run, freeze, cfg: dict) -> tuple[dict, dict]:
    """Refit on the frozen train+discovery rows with the frozen alphas; refuse unless stored coefficients reproduce."""
    stored = json.loads(FROZEN_RESULT.read_text(encoding="utf-8"))
    df = run.load_episodes(run.CAPTURE, cfg, freeze)
    models, report = {}, {}
    for sname, (board, direction) in run.STRATA.items():
        s = df[(df["board"] == board) & (df["direction"] == direction)]
        fit_rows = s[s["phase"].isin(["train", "discovery"])]
        for hname, label in run.LABELS.items():
            cell = stored["strata"][sname][hname]
            got = {}
            for name, nonlinear in (("B2", False), ("M1", True)):
                m = run.fit_ridge(fit_rows, label, cell["alpha"][name], nonlinear)
                models[(sname, hname, name)] = m
                got[name] = [round(float(b), 6) for b in m["beta"]]
                if got[name] != list(cell["test"]["coefficients"][name].values()):
                    raise SystemExit(f"Refusing: refitted {name} coefficients differ from the frozen result in {sname}/{hname}.")
            report[f"{sname}/{hname}"] = {"fit_rows": int(len(fit_rows)), "alpha": cell["alpha"], "coefficients_match": True}
    return models, report


def capture_ledger(source: Path, work: Path, freeze) -> dict:
    """Copy board rows before the capture end from the live ledger, read-only, into a private file. Never overwrites."""
    db = work / "board_episodes.sqlite"
    if db.exists():
        return {"path": str(db), "sha256": run_digest(db), "reused_existing_capture": True}
    work.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=30)
    src.execute("pragma query_only=on")
    src.execute("begin")
    cols = src.execute("pragma table_info(board_outcomes_v2)").fetchall()
    names = [c[1] for c in cols]
    quoted = lambda s: '"' + s.replace('"', '""') + '"'
    defs = [quoted(c[1]) + " " + (c[2] if c[2] in {"INTEGER", "REAL", "TEXT", "BLOB", "NUMERIC"} else "TEXT") for c in cols]
    dest = sqlite3.connect(db)
    dest.execute("create table episodes (" + ",".join(defs) + ")")
    cur = src.execute("select * from board_outcomes_v2 where entered_ts < ? order by id", (freeze.stamp(CAPTURE_END),))
    rows = 0
    with dest:
        while batch := cur.fetchmany(1000):
            dest.executemany("insert into episodes values (" + ",".join("?" for _ in names) + ")", batch)
            rows += len(batch)
    src.rollback()
    src.close()
    dest.execute("create unique index episode_id on episodes(id)")
    dest.execute("create index episode_time on episodes(entered_ts,id)")
    dest.commit()
    assert dest.execute("pragma integrity_check").fetchone()[0] == "ok"
    dest.close()
    return {"path": str(db), "sha256": run_digest(db), "rows": rows, "reused_existing_capture": False,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(), "capture_end_exclusive_utc": CAPTURE_END}


def run_digest(path: Path) -> str:
    return load("live_movers_run").digest(path)


def load_fresh(db: Path, cfg: dict, freeze, run) -> tuple[pd.DataFrame, dict]:
    """Frozen eligibility over the whole local ledger in order, so cooldown state is exact. Returns eligible window rows."""
    con = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cooldown, recs, rejects = {}, [], collections.Counter()
    for row in con.execute("select * from episodes order by entered_ts,id"):
        phase, why, snap = freeze.classify(row, cfg, cooldown)
        if why:
            rejects[why] += 1
            continue
        raw = snap["raw_inputs"]
        recs.append((row["id"], row["board"], row["product_id"], row["direction"], row["entered_ts"], phase,
                     run.num(raw["pct_1m"]), run.num(raw["pct_3m"]), run.num(raw["volume_change_1h_pct"]),
                     run.num(snap["live_score"]), run.num(row["start_change_pct"]),
                     run.num(row["gross_return_5m"]), run.num(row["gross_return_15m"])))
    con.close()
    df = pd.DataFrame(recs, columns=["id", "board", "product_id", "direction", "entered_ts", "phase", "pct_1m", "pct_3m",
                                     "vol", "live_score", "start_change_pct", "gross_return_5m", "gross_return_15m"])
    if df["id"].duplicated().any():
        raise SystemExit("Refusing: duplicate episode ids.")
    df["stratum"] = df["board"] + "/" + df["direction"]
    df["day"] = pd.to_datetime(df["entered_ts"], unit="s", utc=True).dt.strftime("%Y-%m-%d")
    return df, dict(rejects)


def coverage(df: pd.DataFrame) -> dict:
    """Counts only."""
    out = {}
    for phase in PHASES:
        p = df[df["phase"] == phase]
        out[phase] = {"rows": int(len(p)), "days": int(p["day"].nunique()), "products": int(p["product_id"].nunique()),
                      "rows_by_stratum_and_day": {s: g.groupby("day").size().astype(int).to_dict()
                                                  for s, g in p.groupby("stratum")}}
    return out


def interval(series: pd.Series, run) -> dict:
    s = series.dropna()
    return {"mean": float(s.mean()) if len(s) else None, "n_days": int(len(s)), "days_positive": int((s > 0).sum()),
            "iid_daily": run.boot_iid(s.to_numpy(), REPS, SEED), "moving_block_3d": run.boot_moving(s, REPS, SEED)}


def decide(primary: dict, b2: dict) -> str:
    """The predeclared rule. primary is the B2-B1 interval record; b2 is the B2 record."""
    iid, mov = primary["iid_daily"], primary["moving_block_3d"]
    if primary["n_days"] < MIN_DAYS or iid["lo"] is None or mov["lo"] is None:
        return "insufficient"
    if primary["mean"] <= 0 or (iid["hi"] < MIN_EFFECT and mov["hi"] < MIN_EFFECT):
        return "drop"
    if primary["mean"] >= MIN_EFFECT and iid["lo"] > 0 and mov["lo"] > 0 and b2["mean"] > 0:
        return "keep"
    return "inconclusive"


def score_cell(rows: pd.DataFrame, label: str, b2: dict, m1: dict, costs: list[float], run) -> dict:
    preds = {**run.baselines(rows), "B2": run.predict(b2, rows), "M1": run.predict(m1, rows)}
    ics = run.daily_ics(rows, preds, label)
    res = {"rows": int(len(rows)), "days_scored": int(len(ics)), "products": int(rows["product_id"].nunique()),
           "rows_on_scored_days": int(rows["day"].isin(ics.index).sum()),
           "daily_ic": ics.to_dict(orient="index"),
           "ic": {k: interval(ics[k], run) for k in run.MODELS} if len(ics) else {},
           "paired": {f"{a}-{b}": interval(ics[a] - ics[b], run) for a, b in PAIRS} if len(ics) else {},
           "bands": {}}
    for k in run.MODELS:
        bands = run.quintiles(rows, np.asarray(preds[k], dtype=float), label, costs) if len(rows) else []
        res["bands"][k] = {"by_rank_band": bands,
                           "top_minus_bottom_gross_pct": (bands[-1]["mean_gross_pct"] - bands[0]["mean_gross_pct"])
                           if len(bands) >= 2 else None}
    return res


def git_state(run) -> tuple[str, bool]:
    import subprocess
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "scripts", "docs/research"],
                                cwd=ROOT, capture_output=True, text=True).stdout.strip())
    return head, dirty


def write_once(folder: Path, name: str, obj: dict, exclusive: bool) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / name).open("x" if exclusive else "w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(obj, indent=2, default=float, allow_nan=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("phase", choices=("verify", "test"))
    phase = ap.parse_args().phase
    run, freeze = load("live_movers_run"), load("freeze_live_contract")
    cfg = json.loads((run.SPEC_DIR / "CONTRACT_PRODUCTION.json").read_text(encoding="utf-8"))
    hashes = run.verify_inputs()
    head, dirty = git_state(run)
    code = {name: run.digest(ROOT / name) for name in
            ("scripts/scoring_experiment/live_movers_fresh_replication.py", "scripts/scoring_experiment/live_movers_run.py",
             "scripts/scoring_experiment/freeze_live_contract.py")}
    out = {"phase": phase, "protocol_sha256": run.digest(PROTOCOL), "code_commit": head, "code_dirty": dirty,
           "code_hashes": code, "runtime_versions": {"numpy": np.__version__, "pandas": pd.__version__},
           "frozen_inputs": hashes, "frozen_result_sha256": run.digest(FROZEN_RESULT), "windows_utc": PHASES,
           "seed": SEED, "bootstrap_replicates": REPS, "minimum_effect_ic": MIN_EFFECT, "minimum_scored_days": MIN_DAYS}
    if phase == "test":
        if dirty:
            raise SystemExit("Refusing: uncommitted script or research changes; commit first so the result names its code.")
        vpath = WORK / "results_verify_fresh_replication.json"
        if not vpath.exists():
            raise SystemExit("Refusing: run verify first.")
        ver = json.loads(vpath.read_text(encoding="utf-8"))
        if ver["code_hashes"] != code or ver["protocol_sha256"] != out["protocol_sha256"]:
            raise SystemExit("Refusing: code or protocol changed since verify.")
        if any((f / "results_test_fresh_replication.json").exists() for f in (WORK, OUT)):
            raise SystemExit("Refusing: the fresh replication has already been run once.")
        try:
            write_once(WORK, "test_attempt_fresh_replication.json", {"code_commit": head, "code_hashes": code}, True)
        except FileExistsError:
            raise SystemExit("Refusing: an attempt already exists, including an interrupted run.")
    models, fit_report = frozen_models(run, freeze, cfg)
    out["frozen_model_reproduction"] = fit_report
    cap = capture_ledger(SOURCE, WORK, freeze)
    if phase == "test" and cap["sha256"] != ver["capture"]["sha256"]:
        raise SystemExit("Refusing: capture differs from the one verify recorded.")
    out["capture"] = cap
    df, rejects = load_fresh(WORK / "board_episodes.sqlite", fresh_config(cfg), freeze, run)
    out["rejections"], out["coverage"] = rejects, coverage(df)
    if phase == "verify":
        out["outcome_values_summarized"] = False
        write_once(WORK, "results_verify_fresh_replication.json", out, False)
        write_once(OUT, "results_verify_fresh_replication.json", out, False)
        print(json.dumps({"capture_rows": cap.get("rows"), "rejections": rejects,
                          **{p: {k: v for k, v in c.items() if k != "rows_by_stratum_and_day"}
                             for p, c in out["coverage"].items()}}, indent=1))
        return 0
    costs = cfg["cost_scenarios_pct_round_trip"]
    out["windows"] = {}
    for window in PHASES:
        out["windows"][window] = {}
        for sname in run.STRATA:
            rows = df[(df["phase"] == window) & (df["stratum"] == sname)]
            out["windows"][window][sname] = {
                hname: score_cell(rows, label, models[(sname, hname, "B2")], models[(sname, hname, "M1")], costs, run)
                for hname, label in run.LABELS.items()}
    cell = out["windows"]["test"][PRIMARY[0]][PRIMARY[1]]
    record = cell["paired"].get("B2-B1") or {"n_days": 0, "mean": None, "iid_daily": {"lo": None, "hi": None},
                                             "moving_block_3d": {"lo": None, "hi": None}}
    out["primary"] = {"window": "test", "stratum": PRIMARY[0], "label": run.LABELS[PRIMARY[1]],
                      "statistic": "mean daily IC(B2)-IC(B1)", **record,
                      "b2_mean_daily_ic": cell["ic"].get("B2", {}).get("mean"),
                      "verdict": decide(record, cell["ic"].get("B2", {"mean": None}))}
    write_once(WORK, "results_test_fresh_replication.json", out, True)
    write_once(OUT, "results_test_fresh_replication.json", out, True)
    p = out["primary"]
    print("primary B2-B1", {"mean": p["mean"], "iid": p["iid_daily"], "block": p["moving_block_3d"],
                            "n_days": p["n_days"], "B2": p["b2_mean_daily_ic"]}, "->", p["verdict"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
