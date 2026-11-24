"""Live-movers short-horizon comparison (COMPARISON_SPEC.json, contract live-movers-contract-v1-production-amendment-1).

    python scripts/scoring_experiment/live_movers_run.py verify      # hashes, eligible-row identity, readiness; no outcomes
    python scripts/scoring_experiment/live_movers_run.py discovery   # alpha selection on discovery; freezes the choices
    python scripts/scoring_experiment/live_movers_run.py test        # once; refuses without a matching discovery artifact

B0 = |start_change_pct|; B1 = stored live_score (100 - score on the down board); B2 = ridge on direction-aligned pct_1m, pct_3m and
volume_change_1h_pct; M1 = B2 plus squares and interactions. Every model is scored on identical eligible episodes and identical
daily groups. Historical pilot on last-trade labels: not executable fills, not an untouched holdout, no live-weight change.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = ROOT / "docs/research/results/live_movers_contract_20261027"
OUT = ROOT / "docs/research/results/live_movers_comparison"
CAPTURE = Path.home() / ".moonwalking/analysis/live_movers_contract_20261027_production"
WORK = Path.home() / ".moonwalking/analysis/live_movers_comparison"
STRATA = {"ignition_1m/up": ("ignition_1m", "up"), "confirmation_3m_up/up": ("confirmation_3m_up", "up"),
          "confirmation_3m_down/down": ("confirmation_3m_down", "down")}
LABELS = {"h5": "gross_return_5m", "h15": "gross_return_15m"}
MODELS = ("B0", "B1", "B2", "M1")
MIN_DAY_ROWS = 20


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_freeze():
    spec = importlib.util.spec_from_file_location("freeze_live", ROOT / "scripts/scoring_experiment/freeze_live_contract.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------- inputs and identity ----------

def verify_inputs(capture: Path = CAPTURE) -> dict:
    """Refuse unless every frozen file, the contract and the spec are exactly the committed ones."""
    contract_p, spec_p = SPEC_DIR / "CONTRACT_PRODUCTION.json", SPEC_DIR / "COMPARISON_SPEC.json"
    manifest = json.loads((SPEC_DIR / "PRODUCTION_CAPTURE_MANIFEST.json").read_text(encoding="utf-8"))
    for name, rec in manifest["files"].items():
        got = digest(capture / name)
        if got != rec["sha256"]:
            raise SystemExit(f"Refusing: frozen capture file {name} hash differs from the committed manifest.")
    if digest(contract_p) != manifest["contract_sha256"] or digest(capture / "CONTRACT.json") != manifest["contract_sha256"]:
        raise SystemExit("Refusing: contract differs from the one the capture was frozen with.")
    if digest(ROOT / "scripts/scoring_experiment/freeze_live_contract.py") != manifest["freeze_script_sha256"]:
        raise SystemExit("Refusing: eligibility code differs from the frozen freeze script.")
    spec = json.loads(spec_p.read_text(encoding="utf-8"))
    if spec.get("data_contract") != "CONTRACT_PRODUCTION.json":
        raise SystemExit("Refusing: comparison spec names a different data contract.")
    return {"capture_files": {k: v["sha256"] for k, v in manifest["files"].items()},
            "contract_sha256": manifest["contract_sha256"], "spec_sha256": digest(spec_p),
            "manifest_sha256": digest(SPEC_DIR / "PRODUCTION_CAPTURE_MANIFEST.json")}


def num(x):
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and np.isfinite(x) else np.nan


def load_episodes(capture: Path, cfg: dict, freeze) -> pd.DataFrame:
    """Re-derive eligibility and require every frozen identity, timestamp and phase in order."""
    con = sqlite3.connect((capture / "board_episodes.sqlite").as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cooldown, recs = {}, []
    for row in con.execute("select * from episodes order by entered_ts,id"):
        phase, why, snap = freeze.classify(row, cfg, cooldown)
        if why:
            continue
        raw = snap["raw_inputs"]
        recs.append((row["id"], row["board"], row["product_id"], row["direction"], row["entered_ts"], phase,
                     num(raw["pct_1m"]), num(raw["pct_3m"]), num(raw["volume_change_1h_pct"]), num(snap["live_score"]),
                     num(row["start_change_pct"]), num(row["gross_return_5m"]), num(row["gross_return_15m"])))
    con.close()
    df = pd.DataFrame(recs, columns=["id", "board", "product_id", "direction", "entered_ts", "phase", "pct_1m", "pct_3m",
                                     "vol", "live_score", "start_change_pct", "gross_return_5m", "gross_return_15m"])
    with (capture / "eligible_episodes.csv").open(encoding="utf-8", newline="") as f:
        frozen = [(int(r["id"]), r["board"], r["product_id"], r["direction"], int(r["entered_ts"]), r["phase"])
                  for r in csv.DictReader(f)]
    if list(df[["id", "board", "product_id", "direction", "entered_ts", "phase"]].itertuples(index=False, name=None)) != frozen:
        raise SystemExit("Refusing: re-derived eligible episodes differ from the frozen eligible list.")
    if df["id"].duplicated().any():
        raise SystemExit("Refusing: duplicate episode ids.")
    df["stratum"] = df["board"] + "/" + df["direction"]
    df["day"] = pd.to_datetime(df["entered_ts"], unit="s", utc=True).dt.strftime("%Y-%m-%d")
    return df


def readiness(df: pd.DataFrame, cfg: dict) -> dict:
    out = {}
    for ph, req in cfg["readiness"].items():
        s = df[df["phase"] == ph]
        r = {"rows": int(len(s)), "days": int(s["day"].nunique()), "products": int(s["product_id"].nunique())}
        r["pass"] = r["days"] >= req["min_days"] and r["rows"] >= req["min_episodes"] and r["products"] >= req["min_products"]
        out[ph] = r
    return out


# ---------- models ----------

def aligned(df: pd.DataFrame) -> pd.DataFrame:
    sign = np.where(df["direction"] == "down", -1.0, 1.0)
    return pd.DataFrame({"a1": sign * df["pct_1m"], "a3": sign * df["pct_3m"], "v": df["vol"]}, index=df.index)


class Design:
    """1/99 winsor limits and standardization fitted on fitting rows only; transforms from clipped raw inputs."""

    def __init__(self, nonlinear: bool):
        self.nonlinear = nonlinear

    def _cols(self, r: pd.DataFrame) -> pd.DataFrame:
        c = r.clip(self.lo, self.hi, axis=1)
        X = c.copy()
        if self.nonlinear:
            X["a1_sq"], X["a3_sq"] = c["a1"] ** 2, c["a3"] ** 2
            X["a1_a3"], X["a1_v"], X["a3_v"] = c["a1"] * c["a3"], c["a1"] * c["v"], c["a3"] * c["v"]
        return X

    def fit(self, r: pd.DataFrame) -> "Design":
        self.lo, self.hi = r.quantile(0.01), r.quantile(0.99)
        X = self._cols(r)
        self.mu, self.sd = X.mean(), X.std(ddof=0).replace(0, 1.0)
        return self

    def transform(self, r: pd.DataFrame) -> np.ndarray:
        return ((self._cols(r) - self.mu) / self.sd).to_numpy()


def fit_ridge(df: pd.DataFrame, label: str, alpha: float, nonlinear: bool):
    d = Design(nonlinear).fit(aligned(df))
    X, y = d.transform(aligned(df)), df[label].to_numpy()
    beta = np.linalg.solve(X.T @ X + alpha * np.eye(X.shape[1]), X.T @ (y - y.mean()))
    return {"design": d, "beta": beta, "intercept": float(y.mean()), "alpha": alpha, "nonlinear": nonlinear}


def predict(model: dict, df: pd.DataFrame) -> np.ndarray:
    return model["design"].transform(aligned(df)) @ model["beta"] + model["intercept"]


def baselines(df: pd.DataFrame) -> dict:
    b1 = np.where(df["direction"] == "down", 100.0 - df["live_score"], df["live_score"])
    return {"B0": df["start_change_pct"].abs().to_numpy(), "B1": b1}


# ---------- statistics ----------

def daily_ics(df: pd.DataFrame, preds: dict, label: str) -> pd.DataFrame:
    """Within-day Spearman IC per model on identical day groups: >=20 rows, nonconstant target and every prediction."""
    frame = pd.DataFrame({k: v for k, v in preds.items()}, index=df.index)
    frame["_y"], frame["_day"] = df[label].to_numpy(), df["day"].to_numpy()
    rows = {}
    for day, g in frame.groupby("_day"):
        if len(g) < MIN_DAY_ROWS or g["_y"].nunique() < 2 or any(g[k].nunique() < 2 for k in preds):
            continue
        ry = g["_y"].rank()
        rows[day] = {k: float(np.corrcoef(g[k].rank(), ry)[0, 1]) for k in preds}
    return pd.DataFrame.from_dict(rows, orient="index").sort_index()


def boot_iid(v: np.ndarray, reps: int, seed: int, level: float = 0.95) -> dict:
    n = len(v)
    out = {"n_days": n, "mean": float(v.mean()) if n else None, "lo": None, "hi": None}
    if n < 3:
        return out
    m = v[np.random.default_rng(seed).integers(0, n, (reps, n))].mean(axis=1)
    a = (1 - level) / 2 * 100
    out["lo"], out["hi"] = (float(x) for x in np.percentile(m, [a, 100 - a]))
    return out


def boot_moving(s: pd.Series, reps: int, seed: int, block: int = 3, level: float = 0.95) -> dict:
    """Blocks of `block` consecutive UTC calendar days; missing days stay missing (contribute nothing), gaps are not bridged."""
    s = s.dropna()
    out = {"n_days": int(len(s)), "block_days": block, "mean": float(s.mean()) if len(s) else None, "lo": None, "hi": None}
    if len(s) < 3 * block:
        return out
    cal = pd.date_range(s.index.min(), s.index.max(), freq="D").strftime("%Y-%m-%d")
    vals = s.reindex(cal).to_numpy()
    k = int(np.ceil(len(cal) / block))
    rng = np.random.default_rng(seed)
    means = np.empty(reps)
    starts = rng.integers(0, len(cal) - block + 1, (reps, k))
    for i in range(reps):
        w = vals[(starts[i][:, None] + np.arange(block)).ravel()]
        means[i] = np.nanmean(w)
    a = (1 - level) / 2 * 100
    out["lo"], out["hi"] = (float(x) for x in np.percentile(means, [a, 100 - a]))
    return out


def paired(ics: pd.DataFrame, a: str, b: str, spec: dict, offset: int = 0) -> dict:
    d = (ics[a] - ics[b]).dropna()
    # The frozen specification fixes the seed for every reported interval.
    # Keep offset in the call signature for compatibility; it must not alter it.
    reps, seed = 5000, 20261027
    return {"difference": f"{a}-{b}", "bootstrap_replicates": reps, "bootstrap_seed": seed,
            "iid_daily": boot_iid(d.to_numpy(), reps, seed),
            "moving_block_3d": boot_moving(d, reps, seed)}


def verdict(primary: dict, discovery_mean: float | None, mei: float) -> str:
    iid, mov = primary["iid_daily"], primary["moving_block_3d"]
    if iid["lo"] is None:
        return "inconclusive"
    if iid["hi"] < mei:
        return "below the minimum effect"
    if (iid["mean"] >= mei and iid["lo"] > 0 and mov["lo"] is not None and mov["lo"] > 0
            and discovery_mean is not None and discovery_mean > 0):
        return "historically supportive"
    return "inconclusive"


def to_score(pred: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """0-100 percentile against the fixed train+discovery prediction distribution. Ordinal; not a probability."""
    ref = np.sort(reference)
    return 100.0 * np.searchsorted(ref, pred, side="right") / len(ref)


def quintiles(df: pd.DataFrame, score: np.ndarray, label: str, costs: list[float]) -> list[dict]:
    # Average-rank percentile bands keep identical scores together. Empty bands
    # are omitted; a constant score has one band, never an arbitrary time split.
    ranks = pd.Series(score, index=df.index).rank(method="average")
    q = np.minimum(4, np.floor(5 * (ranks - 0.5) / len(df))).astype(int) + 1
    out = []
    for k in sorted(q.unique()):
        g = df.loc[q == k, label]
        out.append({"quintile": int(k), "n": int(len(g)), "mean_gross_pct": float(g.mean()),
                    **{f"mean_gross_minus_{c}pct": float(g.mean() - c) for c in costs}})
    return out


# ---------- phases ----------

def select_alphas(train: pd.DataFrame, disc: pd.DataFrame, label: str, alphas: list[float]) -> dict:
    """Fit on train only; choose alpha by discovery mean daily IC; ties -> larger alpha."""
    chosen, trace = {}, {}
    base = baselines(disc)
    for name, nl in (("B2", False), ("M1", True)):
        best, best_ic = None, -np.inf
        trace[name] = {}
        for a in sorted(alphas, reverse=True):
            p = predict(fit_ridge(train, label, a, nl), disc)
            ics = daily_ics(disc, {**base, "B2" if name == "B2" else "M1": p}, label)
            m = float(ics[name].mean()) if len(ics) else -np.inf
            trace[name][str(a)] = m
            if m > best_ic:
                best, best_ic = a, m
        chosen[name] = best
    return {"alpha": chosen, "discovery_ic_by_alpha": trace}


def evaluate(fit_rows: pd.DataFrame, eval_rows: pd.DataFrame, label: str, alpha: dict, costs: list[float], spec: dict,
             offset: int) -> dict:
    models = {"B2": fit_ridge(fit_rows, label, alpha["B2"], False), "M1": fit_ridge(fit_rows, label, alpha["M1"], True)}
    preds = {**baselines(eval_rows), **{k: predict(m, eval_rows) for k, m in models.items()}}
    ics = daily_ics(eval_rows, preds, label)
    res = {"rows": int(len(eval_rows)), "days_scored": int(len(ics)), "products": int(eval_rows["product_id"].nunique()),
           "rows_per_day": eval_rows.groupby("day").size().astype(int).to_dict(),
           "daily_ic": ics.to_dict(orient="index"),
           "rows_on_scored_days": int(eval_rows["day"].isin(ics.index).sum()),
           "excluded_day_groups": {day: {"rows": int(len(g)), "below_minimum_rows": len(g) < MIN_DAY_ROWS,
                                         "constant_target": g[label].nunique() < 2,
                                         "constant_predictions": [k for k, p in preds.items()
                                                                  if pd.Series(p, index=eval_rows.index).loc[g.index].nunique() < 2]}
                                   for day, g in eval_rows.groupby("day") if day not in ics.index},
           "quintile_policy": "Average-rank percentile bands; equal scores stay together; empty bands omitted.",
           "mean_daily_ic": {k: float(ics[k].mean()) if len(ics) else None for k in MODELS},
           "paired": {f"{a}-{b}": paired(ics, a, b, spec, offset + i) for i, (a, b) in
                      enumerate((("M1", "B2"), ("M1", "B1"), ("B2", "B1"), ("B2", "B0"), ("M1", "B0")))},
           "coefficients": {k: dict(zip(["a1", "a3", "v"] + (["a1_sq", "a3_sq", "a1_a3", "a1_v", "a3_v"] if m["nonlinear"] else []),
                                        [round(float(b), 6) for b in m["beta"]])) for k, m in models.items()}}
    ref = {k: predict(m, fit_rows) for k, m in models.items()}
    res["display_score"] = {}
    for k in ("B2", "M1"):
        sc = to_score(preds[k], ref[k])
        res["display_score"][k] = {"share_at_0": float((sc == 0).mean()), "share_at_100": float((sc == 100).mean()),
                                   "quintiles_by_score": quintiles(eval_rows, sc, label, costs)}
    for k in ("B0", "B1"):
        res["display_score"][k] = {"quintiles_by_score": quintiles(eval_rows, preds[k], label, costs)}
    return res


def git_state() -> tuple[str, bool]:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "scripts", "docs/research/results/live_movers_contract_20261027"],
                                cwd=ROOT, capture_output=True, text=True).stdout.strip())
    return head, dirty


def code_fingerprint() -> dict:
    return {name: digest(ROOT / name) for name in
            ("scripts/scoring_experiment/live_movers_run.py", "scripts/scoring_experiment/freeze_live_contract.py")}


def require_discovery(path: Path, hashes: dict, head: str, code_hashes: dict) -> dict:
    if not path.exists():
        raise SystemExit("Refusing to run the test: no discovery artifact.")
    disc = json.loads(path.read_text(encoding="utf-8"))
    if disc.get("phase") != "discovery" or disc.get("inputs") != hashes:
        raise SystemExit("Refusing to run the test: inputs differ from the discovery run.")
    if disc.get("code_hashes") != code_hashes:
        raise SystemExit("Refusing to run the test: code hashes changed or are missing since the discovery run.")
    return disc


def reserve_test(work: Path, out: Path, metadata: dict) -> None:
    """Refuse portable/local results and atomically reserve even an interrupted attempt."""
    if any((folder / "results_test_live_movers.json").exists() for folder in (work, out)):
        raise SystemExit("Refusing: the historical validation has already been run once.")
    work.mkdir(parents=True, exist_ok=True)
    try:
        with (work / "test_attempt_live_movers.json").open("x", encoding="utf-8") as stream:
            json.dump(metadata, stream, indent=2, allow_nan=False)
    except FileExistsError:
        raise SystemExit("Refusing: a historical validation attempt already exists, including an interrupted run.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=("verify", "discovery", "test"))
    phase = ap.parse_args().phase
    cfg = json.loads((SPEC_DIR / "CONTRACT_PRODUCTION.json").read_text(encoding="utf-8"))
    spec = json.loads((SPEC_DIR / "COMPARISON_SPEC.json").read_text(encoding="utf-8"))
    hashes = verify_inputs()
    code_hashes = code_fingerprint()
    head, dirty = git_state()
    if dirty and phase != "verify":
        raise SystemExit("Refusing: uncommitted driver or contract changes; commit first so the result names its code.")
    df = load_episodes(CAPTURE, cfg, load_freeze())
    ready = readiness(df, cfg)
    out = {"phase": phase, "spec_version": spec["version"], "contract_version": cfg["version"], "code_commit": head,
           "code_hashes": code_hashes, "code_dirty": dirty, "runtime_versions": {"numpy": np.__version__, "pandas": pd.__version__},
           "inputs": hashes, "readiness": ready, "eligible_rows": int(len(df)),
           "limits": [cfg["retrospective_scope"], cfg["historical_holdout_limit"], spec["live_release"],
                      "Scores are ordinal 0-100 percentiles, direction- and horizon-labelled; not probabilities.",
                      "pct_1h/trend_streak complete-case secondary not run."]}
    if not all(r["pass"] for r in ready.values()):
        raise SystemExit(f"Refusing: readiness fails {ready}")
    if phase == "verify":
        _write(out, phase)
        print(json.dumps(ready, indent=1))
        return 0
    dpath = WORK / "results_discovery_live_movers.json"
    costs, mei = cfg["cost_scenarios_pct_round_trip"], spec["minimum_effect_of_interest_ic"]
    out["strata"] = {}
    if phase == "test":
        # A committed discovery artifact is portable; a docs/result-only commit
        # must not require refitting or invalidate unchanged code and inputs.
        if not dpath.exists():
            dpath = OUT / "results_discovery_live_movers.json"
        disc = require_discovery(dpath, hashes, head, code_hashes)
        reserve_test(WORK, OUT, {"code_commit": head, "code_hashes": code_hashes, "inputs": hashes})
    for si, (sname, (board, direction)) in enumerate(STRATA.items()):
        s = df[(df["board"] == board) & (df["direction"] == direction)]
        tr, dc, te = (s[s["phase"] == p] for p in ("train", "discovery", "test"))
        out["strata"][sname] = {}
        for hi, (hname, label) in enumerate(LABELS.items()):
            off = 100 * si + 10 * hi
            if phase == "discovery":
                sel = select_alphas(tr, dc, label, spec["ridge_alphas"])
                r = {"selection": sel, "discovery": evaluate(tr, dc, label, sel["alpha"], costs, spec, off)}
            else:
                dsel = disc["strata"][sname][hname]
                alpha = dsel["selection"]["alpha"]
                r = {"alpha": alpha, "test": evaluate(pd.concat([tr, dc]), te, label, alpha, costs, spec, off)}
                if sname == spec["primary_stratum"] and label == spec["primary_label"]:
                    dmean = dsel["discovery"]["paired"]["M1-B2"]["iid_daily"]["mean"]
                    out["primary"] = {"stratum": sname, "label": label, "statistic": "mean daily IC(M1)-IC(B2)",
                                      **r["test"]["paired"]["M1-B2"], "discovery_difference_mean": dmean,
                                      "minimum_effect_of_interest_ic": mei,
                                      "verdict": verdict(r["test"]["paired"]["M1-B2"], dmean, mei)}
            out["strata"][sname][hname] = r
    _write(out, phase)
    if phase == "test":
        p = out["primary"]["iid_daily"]
        print("test", spec["primary_stratum"], "M1-B2", {k: None if p[k] is None else round(p[k], 4) for k in ("mean", "lo", "hi")},
              out["primary"]["verdict"])
    else:
        print("discovery alphas:", {s: {h: v["selection"]["alpha"] for h, v in hs.items()} for s, hs in out["strata"].items()})
    return 0


def _write(out: dict, phase: str) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    text = json.dumps(out, indent=2, default=float, allow_nan=False)
    for folder in (WORK, OUT):
        with (folder / f"results_{phase}_live_movers.json").open("x" if phase == "test" else "w", encoding="utf-8") as stream:
            stream.write(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
