"""Fundamentals comparison driver (protocol docs/research/FUNDAMENTALS_EXPERIMENT_PROTOCOL.md, sections 4-6).

    python scripts/scoring_experiment/fundamentals_run.py readiness    # outcome-blind: matched rows and first-fit months only
    python scripts/scoring_experiment/fundamentals_run.py discovery
    python scripts/scoring_experiment/fundamentals_run.py test         # refuses without a matching discovery result; runs once

S0 = within-day rank-normal of the out-of-sample full-universe baseline prediction on the matched rows; S1 = S0 + fee_trend,
fitted by the same purged walk-forward. Both are scored on exactly the same rows. M0/M1-matched (11 inputs, +fee_trend, trained
on matched rows only) are reported separately. The cohort, its fee-file hashes and both configs are hashed into every output.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evaluate as ev  # noqa: E402
import fundamentals as fd  # noqa: E402
import fundamentals_gate as gate  # noqa: E402
import panel  # noqa: E402
from model import EMBARGO, MIN_TRAIN_ROWS, daily_ic, walk_forward  # noqa: E402

REPO = HERE.parents[1]
OUT = REPO / "docs" / "research" / "results" / "fundamentals_comparison"
WORK = Path.home() / ".moonwalking" / "analysis" / "scoring_baseline"
FEE = "fee"


def fcfg_load() -> dict:
    return json.loads((HERE / "fundamentals_config.json").read_text(encoding="utf-8"))


def eval_cfg(cfg: dict, fcfg: dict) -> dict:
    """Baseline config with the frozen fundamentals interval level; nothing else changes."""
    e = copy.deepcopy(cfg)
    e["bootstrap"]["level"] = fcfg["bootstrap"]["level"]
    return e


def provenance(
    cfg: dict,
    fcfg: dict,
    cohort_path: Path,
    cohort: list[dict],
    captures: Path,
    baseline_files=None,
) -> dict:
    """Hashes of every input that defines the experiment. Verifies each approved fee file against the cohort."""
    files = {}
    for e in cohort:
        if e.get("status") != "approved":
            continue
        name = e["series_files"]["fees"]
        got = fd.sha256(captures / name)
        if got != e["series_sha256"]["fees"]:
            raise SystemExit(
                f"Refusing: {e['product_id']} fee file {name} hash differs from the cohort."
            )
        files[e["product_id"]] = got
    p = {
        "cohort_file": (
            str(cohort_path.relative_to(REPO))
            if cohort_path.is_relative_to(REPO)
            else str(cohort_path)
        ),
        "cohort_sha256": fd.sha256(cohort_path),
        "fee_file_sha256": files,
        "approved": sorted(files),
        "held": sorted(
            e["product_id"] for e in cohort if e.get("status") != "approved"
        ),
        "baseline_config_hash": panel.config_hash(cfg),
        "fundamentals_config_hash": panel.config_hash(fcfg),
    }
    p["baseline_input_sha256"] = {
        name: fd.sha256(path) for name, path in (baseline_files or {}).items()
    }
    p["combined_hash"] = panel.config_hash(p)
    return p


def experiment_identity() -> dict:
    names = [
        "fundamentals_run.py",
        "fundamentals.py",
        "fundamentals_gate.py",
        "model.py",
        "panel.py",
        "evaluate.py",
        "run.py",
    ]
    paths = [HERE / name for name in names] + [
        REPO / "scripts/scoring_data/freeze_daily_panel.py",
        REPO / "docs/research/FUNDAMENTALS_EXPERIMENT_PROTOCOL.md",
    ]
    identity = {
        "source_sha256": {
            str(p.relative_to(REPO))
            .replace("\\", "/"): hashlib.sha256(
                p.read_text(encoding="utf-8").encode("utf-8")
            )
            .hexdigest()
            for p in paths
        },
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
    }
    return {**identity, "combined_hash": panel.config_hash(identity)}


def prediction_availability(base, h, start, end):
    """No fitting or label magnitudes: mirror walk_forward's row-count gate."""
    dates = pd.DatetimeIndex(base.index.get_level_values("date"))
    present = base[f"y{h}"].notna().to_numpy()
    available = np.zeros(len(base), dtype=bool)
    for month in pd.date_range(start, end, freq="MS"):
        if ((dates < month - EMBARGO) & present).sum() >= MIN_TRAIN_ROWS:
            available |= (dates >= month) & (dates < month + pd.offsets.MonthBegin(1))
    # A constant placeholder communicates presence only, never a model score.
    return pd.Series(np.where(available, 0.0, np.nan), index=base.index)


def assert_phase_unused(phase):
    names = [f"results_{phase}_fundamentals.json"]
    if phase == "test":
        names.append("test_attempt_fundamentals.json")
    if any((root / name).exists() for root in (WORK, OUT) for name in names):
        raise SystemExit(
            f"Refusing: {phase} result or attempt already exists locally or in the repository."
        )


def reserve_test(provenance_hash, experiment_hash):
    """Fail closed on concurrent/repeated attempts; retain failures as attempts."""
    assert_phase_unused("test")
    marker = {
        "phase": "test",
        "provenance_hash": provenance_hash,
        "experiment_hash": experiment_hash,
    }
    for root in (WORK, OUT):
        root.mkdir(parents=True, exist_ok=True)
        try:
            with (root / "test_attempt_fundamentals.json").open(
                "x", encoding="utf-8"
            ) as stream:
                json.dump(marker, stream, indent=2)
                stream.write("\n")
        except FileExistsError:
            raise SystemExit("Refusing: a concurrent or previous test attempt exists.")


def rank_normal(values: pd.Series) -> pd.Series:
    """Within-day rank-normal score among the non-missing rows (baseline convention)."""
    day = values.index.get_level_values("date")
    g = values.groupby(day)
    n, r = g.transform("count"), g.rank(method="average")
    ok = values.notna() & (n > 1)
    out = pd.Series(np.nan, index=values.index)
    out[ok] = panel.norm_ppf(((r[ok] - 0.5) / n[ok]).to_numpy())
    return out


def build_matched(
    base: pd.DataFrame, cohort: list[dict], captures: Path, lag: int, min_n: int
) -> tuple[pd.DataFrame, dict]:
    """Baseline-eligible rows of approved products with fee_trend defined (data dated <= d - lag), >= min_n such coins a day."""
    prods = base.index.get_level_values("product")
    pieces, per_product = [], {}
    for e in cohort:
        pid = e["product_id"]
        if e.get("status") != "approved" or pid == "BTC-USD":
            continue
        series, sinfo = fd.parse_series(captures / e["series_files"]["fees"])
        feat, reasons = fd.trend(series)
        dec = fd.to_decision_dates(feat, lag)
        sub = base[prods == pid]
        vals = dec.reindex(sub.index.get_level_values("date")).to_numpy()
        sub = sub.assign(fee_raw=vals, scope=e.get("scope"))
        sub = sub[sub["fee_raw"].notna()]
        per_product[pid] = {
            "scope": e.get("scope"),
            "series": sinfo,
            "feature": reasons,
            "eligible_rows": int((prods == pid).sum()),
            "matched_rows_before_day_rule": int(len(sub)),
        }
        if len(sub):
            pieces.append(sub)
    dm = (
        pd.concat(pieces).sort_index()
        if pieces
        else base.iloc[:0].assign(fee_raw=[], scope=[])
    )
    if dm.index.has_duplicates:
        raise ValueError("matched (date, product) pairs are not unique")
    return apply_day_rule(dm, min_n), per_product


def apply_day_rule(dm: pd.DataFrame, min_n: int) -> pd.DataFrame:
    dm = dm[dm.groupby(level="date")["fee_raw"].transform("size") >= min_n].copy()
    dm["n_matched_day"] = dm.groupby(level="date")["fee_raw"].transform("size")
    dm["z_" + FEE] = rank_normal(dm["fee_raw"])
    return dm


def horizon_rows(
    dm: pd.DataFrame, s0_raw: pd.Series, h: int, min_n: int
) -> pd.DataFrame:
    """Matched rows that also have an out-of-sample S0 prediction, re-ranked; walk_forward would otherwise fill a missing
    S0 with zero, so rows without S0 never enter S0 or S1."""
    d = dm.assign(s0_raw=s0_raw.reindex(dm.index).to_numpy())
    d = d[d["s0_raw"].notna()]
    d = apply_day_rule(d, min_n)
    d[f"z_s0_{h}"] = rank_normal(d["s0_raw"])
    return d


def first_fit_readiness(
    d: pd.DataFrame, h: int, start: str, end: str, inputs: list[str]
) -> dict:
    """First month whose fit would have >= MIN_TRAIN_ROWS rows dated before month start minus the embargo with every input
    and the label *present*. Availability only: label and return values are never read.
    """
    ok = d["y%d" % h].notna().to_numpy().copy()
    for c in inputs:
        ok &= d["z_" + c].notna().to_numpy()
    dates = pd.DatetimeIndex(d.index.get_level_values("date"))
    months = []
    for m in pd.date_range(start, end, freq="MS"):
        n = int((ok & (dates < m - EMBARGO)).sum())
        months.append({"month": str(m.date()), "available_training_rows": n})
        if n >= MIN_TRAIN_ROWS:
            return {
                "first_fit_month": str(m.date()),
                "available_training_rows": n,
                "required": MIN_TRAIN_ROWS,
            }
    return {
        "first_fit_month": None,
        "required": MIN_TRAIN_ROWS,
        "last_checked": months[-1] if months else None,
    }


def inwin(df, period):
    d = df.index.get_level_values("date")
    return (d >= pd.Timestamp(period[0])) & (d <= pd.Timestamp(period[1]))


def paired(ic1: pd.Series, ic0: pd.Series, ecfg: dict, seed: int) -> dict:
    both = pd.concat([ic1, ic0], axis=1, keys=["s1", "s0"]).dropna()
    out = ev.ic_summary(both["s1"] - both["s0"], ecfg, seed, moving=True)
    out["moving_block"] = calendar_moving(
        ev.weekly(both["s1"] - both["s0"]), ecfg, seed
    )
    out["mean_ic_s1"] = float(both["s1"].mean()) if len(both) else None
    out["mean_ic_s0"] = float(both["s0"].mean()) if len(both) else None
    out["paired_daily_ic"] = {
        str(day.date()): {k: float(v) for k, v in row.items()}
        for day, row in both.iterrows()
    }
    out["weekday_phases"] = {
        n: ev.boot(
            (both["s1"] - both["s0"])[both.index.dayofweek == w].reset_index(drop=True),
            ecfg,
            seed + 50 + w,
        )
        for w, n in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    }
    return out


def calendar_moving(weeks, cfg, seed):
    """Sample only windows of L actually consecutive observed ISO weeks."""
    weeks = weeks.dropna().sort_index()
    values = weeks.to_numpy(float)
    n, L = len(values), int(cfg["bootstrap"]["moving_block_weeks"])
    dates = [
        pd.Timestamp.fromisocalendar(int(k) // 100, int(k) % 100, 1)
        for k in weeks.index
    ]
    starts = [
        i
        for i in range(max(0, n - L + 1))
        if all(
            dates[j + 1] - dates[j] == pd.Timedelta(days=7) for j in range(i, i + L - 1)
        )
    ]
    blocks = [values[i : i + L] for i in starts]
    covered = {j for i in starts for j in range(i, i + L)}
    out = {
        "mean": float(values.mean()) if n else None,
        "lo": None,
        "hi": None,
        "n_blocks": n,
        "block_weeks": L,
        "valid_calendar_windows": len(blocks),
        "weeks_outside_valid_windows": n - len(covered),
    }
    if n < 3 * L or not blocks or len(covered) != n:
        return out
    rng = np.random.default_rng(cfg["bootstrap"]["seed"] + 5000 + seed)
    selected = rng.integers(
        0, len(blocks), size=(cfg["bootstrap"]["resamples"], int(np.ceil(n / L)))
    )
    means = np.asarray(blocks)[selected].reshape(len(selected), -1)[:, :n].mean(axis=1)
    alpha = (1 - cfg["bootstrap"]["level"]) / 2 * 100
    out["lo"], out["hi"] = [
        float(x) for x in np.percentile(means, [alpha, 100 - alpha])
    ]
    return out


def coef_summary(log: list[dict], feat: str, period) -> dict:
    lo, hi = pd.Timestamp(period[0]), pd.Timestamp(period[1])
    c = [f["coef"][feat] for f in log if lo <= pd.Timestamp(f["month"]) <= hi]
    return {
        "months": len(c),
        "mean_coef": float(np.mean(c)) if c else None,
        "share_negative": float(np.mean([x < 0 for x in c])) if c else None,
    }


def verdict(est: dict, disc_mean: float | None, mei: float, coef_ok: bool) -> str:
    """Protocol section 6: supportive needs the threshold, both intervals above zero, a positive discovery difference and a
    stable coefficient sign; ruled out when the week-block upper bound is below the threshold.
    """
    if est.get("lo") is None:
        return "inconclusive"
    if est["hi"] < mei:
        return "ruled out"
    mov = est.get("moving_block") or {}
    if (
        est["mean"] >= mei
        and est["lo"] > 0
        and mov.get("lo") is not None
        and mov["lo"] > 0
        and disc_mean is not None
        and disc_mean > 0
        and coef_ok
    ):
        return "supportive"
    return "inconclusive"


def require_discovery(dpath: Path, combined_hash: str, experiment_hash: str) -> dict:
    if not dpath.exists():
        raise SystemExit(
            "Refusing to run the test phase: no fundamentals discovery result exists."
        )
    disc = json.loads(dpath.read_text(encoding="utf-8"))
    if (
        disc.get("phase") != "discovery"
        or disc.get("provenance", {}).get("combined_hash") != combined_hash
    ):
        raise SystemExit(
            "Refusing to run the test phase: cohort, captures or configuration differ from the discovery run."
        )
    if disc.get("experiment_fingerprint") != experiment_hash:
        raise SystemExit(
            "Refusing to run the test phase: experiment code, protocol or runtime changed since discovery."
        )
    frozen = disc.get("frozen", {})
    thresholds = frozen.get("btc30_tercile_thresholds")
    if (
        disc.get("ready") is not True
        or not isinstance(thresholds, list)
        or len(thresholds) != 2
        or not all(isinstance(v, (int, float)) and np.isfinite(v) for v in thresholds)
        or thresholds[0] >= thresholds[1]
        or frozen.get("fee_coefficient_sign") not in (-1, 0, 1)
        or frozen.get("discovery_difference_mean") is None
        or not np.isfinite(frozen["discovery_difference_mean"])
    ):
        raise SystemExit(
            "Refusing: discovery is incomplete or its frozen decisions are invalid."
        )
    return disc


def require_committed_discovery(disc):
    relative = (
        (OUT / "results_discovery_fundamentals.json").relative_to(REPO).as_posix()
    )
    result = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        raise SystemExit(
            "Refusing: commit the frozen discovery artifact before running test."
        )
    if json.loads(result.stdout) != disc:
        raise SystemExit("Refusing: local discovery differs from the committed freeze.")


def run_lag(
    base,
    full_preds,
    cohort,
    captures,
    cfg,
    ecfg,
    fcfg,
    lag,
    period,
    start,
    end,
    thresholds,
    primary: bool,
) -> dict:
    min_n = cfg["min_cross_section"]
    dm, per_product = build_matched(base, cohort, captures, lag, min_n)
    res = {"per_product": per_product, "horizons": {}}
    for h in cfg["horizons_days"]:
        d = horizon_rows(dm, full_preds[h], h, min_n)
        s0 = f"s0_{h}"
        calibration, _, _ = walk_forward(d, h, cfg, start, end, [s0])
        p1, _, l1 = walk_forward(d, h, cfg, start, end, [s0, FEE])
        y = d[f"y{h}"]
        predicted = inwin(d, period) & p1.notna().to_numpy()
        m = predicted & y.notna().to_numpy()
        ic0, ic1 = daily_ic(d["z_" + s0][m], y[m], min_n), daily_ic(p1[m], y[m], min_n)
        paired_days = ic0.index.intersection(ic1.index)
        m &= d.index.get_level_values("date").isin(paired_days)
        ic0, ic1 = ic0.reindex(paired_days), ic1.reindex(paired_days)
        r = {
            "rows": {
                "matched_with_s0": int(len(d)),
                "prediction_rows_in_period": int(predicted.sum()),
                "scored_in_period": int(m.sum()),
                "products": int(d[m].index.get_level_values("product").nunique()),
                "coins_per_day_min": (
                    int(d[m].groupby(level="date").size().min()) if m.any() else 0
                ),
                "coins_per_day_median": (
                    float(d[m].groupby(level="date").size().median())
                    if m.any()
                    else 0.0
                ),
            },
            "first_fit_s1": l1[0]["month"] if l1 else None,
            "incremental_ic_s1_minus_s0": paired(ic1, ic0, ecfg, h * 7),
            "s0": ev.ic_summary(ic0, ecfg, h + 1),
            "s1": ev.ic_summary(ic1, ecfg, h + 2),
            "fee_coefficient_in_s1": coef_summary(l1, FEE, period),
        }
        control = m & calibration.notna().to_numpy()
        r["calibration_only_attribution_control"] = paired(
            daily_ic(p1[control], y[control], min_n),
            daily_ic(calibration[control], y[control], min_n),
            ecfg,
            h * 7 + 41,
        )
        r["calibration_control_interpretation"] = (
            "descriptive attribution control; the frozen primary remains S1 versus raw full-universe S0"
        )
        if primary:
            nochain = m & (d["scope"] != "chain").to_numpy()
            r["excluding_chain_scope"] = paired(
                daily_ic(p1[nochain], y[nochain], min_n),
                daily_ic(d["z_" + s0][nochain], y[nochain], min_n),
                ecfg,
                h * 7 + 3,
            )
            r["excluding_chain_scope_interpretation"] = (
                "grading-only scope cut; S1 is not refitted without chains"
            )
            r["fee_trend_alone"] = ev.ic_summary(
                daily_ic(d["z_" + FEE][m], y[m], min_n), ecfg, h + 4
            )
            pm0, _, _ = walk_forward(d, h, cfg, start, end)
            pm1, _, lm1 = walk_forward(d, h, cfg, start, end, panel.FEATURES + [FEE])
            mm = m & pm0.notna().to_numpy() & pm1.notna().to_numpy()
            r["matched_trained_secondary"] = {
                "m1_minus_m0_matched": paired(
                    daily_ic(pm1[mm], y[mm], min_n),
                    daily_ic(pm0[mm], y[mm], min_n),
                    ecfg,
                    h * 7 + 5,
                ),
                "fee_coefficient_in_m1": coef_summary(lm1, FEE, period),
            }
            dd = (ic1 - ic0).dropna()
            reg = pd.cut(
                d["btc30"],
                [-np.inf, thresholds[0], thresholds[1], np.inf],
                labels=["down", "flat", "up"],
            )
            days_by = {
                k: set(reg[reg == k].index.get_level_values("date"))
                for k in ("down", "flat", "up")
            }
            r["by_btc_30d_regime"] = {}
            for k, days in days_by.items():
                s = ev.ic_summary(dd[[x in days for x in dd.index]], ecfg, h + 10)
                r["by_btc_30d_regime"][k] = {
                    **s,
                    "interpretable": s["n_blocks"] >= cfg["min_blocks_for_regime"],
                }
            r["by_calendar_year"] = {
                str(yr): ev.ic_summary(dd[dd.index.year == yr], ecfg, h + 20)
                for yr in sorted(set(dd.index.year))
            }
            r["fit_log_s1"] = l1
        res["horizons"][f"h{h}"] = r
    return res


def git_state() -> tuple[str, bool]:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            [
                "git",
                "status",
                "--porcelain",
                "--",
                "scripts",
                "docs/research/FUNDAMENTALS_EXPERIMENT_PROTOCOL.md",
                "docs/research/results/fundamentals_cohort_acceptance_20261026",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return head, dirty


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=("readiness", "discovery", "test"))
    ap.add_argument(
        "--readiness-report",
        type=Path,
        help="write readiness only to this file; preserve existing shared artifacts",
    )
    args = ap.parse_args(argv)
    phase = args.phase
    if args.readiness_report and phase != "readiness":
        ap.error("--readiness-report applies only to readiness")
    import run as base_run

    cfg, fcfg = panel.load_config(), fcfg_load()
    ecfg = eval_cfg(cfg, fcfg)
    cohort_path, captures = REPO / fcfg["cohort"], panel.expand(fcfg["captures"])
    cohort = json.loads(cohort_path.read_text(encoding="utf-8"))
    baseline_files = {
        name: WORK / name for name in ("long_base.pkl", "build_base.json")
    }
    baseline_files["panel_MANIFEST.json"] = (
        panel.expand(cfg["panel_root"]) / "MANIFEST.json"
    )
    prov = provenance(cfg, fcfg, cohort_path, cohort, captures, baseline_files)
    identity = experiment_identity()
    head, dirty = git_state()
    if dirty and phase != "readiness":
        raise SystemExit(
            "Refusing: uncommitted changes to the experiment code or cohort; commit first so the result names its code."
        )
    dpath = WORK / "results_discovery_fundamentals.json"
    disc = None
    if phase in ("discovery", "test"):
        assert_phase_unused(phase)
    if phase == "test":
        disc = require_discovery(
            dpath, prov["combined_hash"], identity["combined_hash"]
        )
        require_committed_discovery(disc)
    base, build_info = base_run.load_long(cfg, "base")
    if (
        build_info["provenance"]["manifest_sha256"]
        != prov["baseline_input_sha256"]["panel_MANIFEST.json"]
    ):
        raise SystemExit(
            "Refusing: panel manifest differs from the baseline build provenance."
        )
    cov = gate.coverage(cohort, captures, base.index, lag=fcfg["primary_lag_days"])
    g = gate.evaluate_gate(cov["per_day_counts"], cov["problems"])
    if not g["gate_passed"]:
        raise SystemExit(
            f"Refusing: coverage gate does not pass on this cohort ({ {k: g[k]['pass'] for k in ('G1','G2','G3','G4','G5')} })."
        )
    start = cfg["discovery"][0]
    period = cfg["test" if phase == "test" else "discovery"]
    end = str(pd.Timestamp(period[1]).to_period("M").start_time.date())
    out = {
        "phase": phase,
        "protocol": fcfg["protocol"],
        "code_commit": head,
        "provenance": prov,
        "experiment_fingerprint": identity["combined_hash"],
        "experiment_identity": identity,
        "interval_level": ecfg["bootstrap"]["level"],
        "gate": {k: g[k]["pass"] for k in ("G1", "G2", "G3", "G4", "G5")},
        "labels": "retrospective backfilled DeFiLlama series; not point-in-time",
        "not_run": [
            "revenue_trend and usd_tvl_change: the reviewed cohort has fee series only",
            "extreme-trend events and residualized fee IC",
            "child-only/ecosystem scope exclusions and non-chain refits",
        ],
    }
    # out-of-sample full-universe baseline (the strong comparator); its fit never sees fundamentals
    availability = {
        h: prediction_availability(base, h, start, end) for h in cfg["horizons_days"]
    }
    dm, _ = build_matched(
        base, cohort, captures, fcfg["primary_lag_days"], cfg["min_cross_section"]
    )
    ready = {}
    for h in cfg["horizons_days"]:
        d = horizon_rows(dm, availability[h], h, cfg["min_cross_section"])
        ready[f"h{h}"] = first_fit_readiness(d, h, start, end, [f"s0_{h}", FEE])
    out["first_fit_readiness"] = ready
    latest = pd.Timestamp(fcfg["latest_first_fit"])
    ph = f"h{fcfg['primary_horizon_days']}"
    if (
        ready[ph]["first_fit_month"] is None
        or pd.Timestamp(ready[ph]["first_fit_month"]) > latest
    ):
        out["ready"] = False
        _write(out, phase, args.readiness_report)
        raise SystemExit(
            f"Refusing: primary-horizon first fit {ready[ph]['first_fit_month']} is after {latest.date()}."
        )
    out["ready"] = True
    if phase == "readiness":
        out["model_fits_run"] = False
        out["readiness_basis"] = (
            "label presence and purged training-row counts only; no model predictions or outcome magnitudes"
        )
        _write(out, phase, args.readiness_report)
        print(json.dumps(ready, indent=1))
        return 0
    if phase == "test":
        reserve_test(prov["combined_hash"], identity["combined_hash"])
        thresholds = disc["frozen"]["btc30_tercile_thresholds"]
    else:
        d_in = dm[inwin(dm, period)]
        thresholds = [
            float(x)
            for x in d_in["btc30"]
            .groupby(level="date")
            .first()
            .quantile([1 / 3, 2 / 3])
        ]
        out["btc30_tercile_thresholds"] = thresholds
    full_preds = {
        h: walk_forward(base, h, cfg, start, end)[0] for h in cfg["horizons_days"]
    }
    out["primary_lag"] = run_lag(
        base,
        full_preds,
        cohort,
        captures,
        cfg,
        ecfg,
        fcfg,
        fcfg["primary_lag_days"],
        period,
        start,
        end,
        thresholds,
        primary=True,
    )
    out["sensitivity_lag"] = run_lag(
        base,
        full_preds,
        cohort,
        captures,
        cfg,
        ecfg,
        fcfg,
        fcfg["sensitivity_lag_days"],
        period,
        start,
        end,
        thresholds,
        primary=False,
    )
    prim = out["primary_lag"]["horizons"][ph]
    if phase == "discovery":
        out["frozen"] = {
            "discovery_difference_mean": prim["incremental_ic_s1_minus_s0"]["mean"],
            "fee_coefficient_sign": (
                None
                if prim["fee_coefficient_in_s1"]["mean_coef"] is None
                else int(np.sign(prim["fee_coefficient_in_s1"]["mean_coef"]))
            ),
            "btc30_tercile_thresholds": thresholds,
        }
    else:
        fz = disc["frozen"]
        ct = prim["fee_coefficient_in_s1"]["mean_coef"]
        coef_ok = (
            ct is not None
            and fz["fee_coefficient_sign"] is not None
            and int(np.sign(ct)) == fz["fee_coefficient_sign"]
        )
        out["primary_verdict"] = {
            "interpretation": "joint S1 stack versus raw S0; fee-specific attribution also requires the descriptive calibration-only control",
            "horizon_days": fcfg["primary_horizon_days"],
            "verdict": verdict(
                prim["incremental_ic_s1_minus_s0"],
                fz["discovery_difference_mean"],
                fcfg["min_effect_of_interest_ic"],
                coef_ok,
            ),
            "discovery_difference_mean": fz["discovery_difference_mean"],
            "coefficient_sign_same_in_discovery_and_test": bool(coef_ok),
        }
    _write(out, phase)
    e = prim["incremental_ic_s1_minus_s0"]
    print(
        phase,
        ph,
        "S1-S0",
        {k: None if e[k] is None else round(e[k], 4) for k in ("mean", "lo", "hi")},
        out.get("primary_verdict", {}).get("verdict"),
    )
    return 0


def _write(out: dict, phase: str, readiness_report=None) -> None:
    if readiness_report is not None:
        paths = [Path(readiness_report)]
    else:
        paths = [root / f"results_{phase}_fundamentals.json" for root in (WORK, OUT)]
    text = json.dumps(out, indent=2, default=float, allow_nan=False) + "\n"
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)


if __name__ == "__main__":
    sys.exit(main())
