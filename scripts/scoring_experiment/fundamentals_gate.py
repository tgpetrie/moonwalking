"""Measured coverage gate for the fundamentals experiment (protocol section 3). Outcome-blind.

Uses only the baseline's ELIGIBLE (date, product) index; labels and returns are dropped before anything is joined.

    python scripts/scoring_experiment/fundamentals_gate.py --cohort <fundamentals_cohort.json> --captures <folder> --out <GATE_REPORT.json>
    python scripts/scoring_experiment/fundamentals_gate.py --pilot-cohort <capture folder> --write <cohort.json>   # build a cohort file from
                                                                                                                  # Codex's pilot capture (unreviewed)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fundamentals as fd  # noqa: E402
import panel  # noqa: E402

PRIMARY_LAG = 2
GATES = {"G1_min_coins": 20, "G1_share_of_test_days": 0.90, "G2_min_test_weeks": 80, "G3_min_rows_before": ("2024-06-01", 5000), "embargo_days": 8,
         "G4_min_discovery_weeks": 20, "discovery_window": ("2024-06-01", "2024-12-23"), "test_window": ("2025-01-01", "2026-10-10")}


def eligible_index(cfg: dict) -> pd.MultiIndex:
    """Baseline-eligible (date, product) pairs only; every label/return column is discarded."""
    import run as base_run
    df, _ = base_run.load_long(cfg, "base")
    return df.index


REVIEW_FIELDS = ("identity_evidence", "reviewer", "reviewed_at", "source_family")
FEE_METRIC = "dailyFees"


def _names(doc) -> set[str]:
    """Every protocol/parent/child name a captured DeFiLlama response claims; used for the overlap policy."""
    if not isinstance(doc, dict):
        return set()
    out = {str(doc[k]).lower() for k in ("id", "slug", "name", "defillamaId", "parentProtocol") if doc.get(k)}
    for k in ("linkedProtocols", "childProtocols"):
        for c in doc.get(k) or []:
            out.add(str(c.get("name") if isinstance(c, dict) else c).lower())
    return out


def validate_entry(e: dict, doc) -> list[str]:
    """Schema and provenance for an approved entry. A hash checks bytes, not meaning, so the metric and source are checked
    against the captured response itself."""
    pid, bad = e.get("product_id"), []
    for f in REVIEW_FIELDS:
        v = e.get(f)
        if not isinstance(v, str) or not v.strip():
            bad.append(f"{pid}: approved without nonempty {f}")
    if e.get("reviewed_at"):
        try:
            pd.Timestamp(e["reviewed_at"])
        except (ValueError, TypeError):
            bad.append(f"{pid}: reviewed_at {e['reviewed_at']!r} is not a date")
    if (e.get("source_metrics") or {}).get("fees") != FEE_METRIC:
        bad.append(f"{pid}: source_metrics.fees must be {FEE_METRIC!r}")
    url = (e.get("source_urls") or {}).get("fees") or ""
    if f"dataType={FEE_METRIC}" not in url:
        bad.append(f"{pid}: fee source URL does not request {FEE_METRIC}")
    src = (e.get("source_ids") or {}).get("fees")
    if not src:
        bad.append(f"{pid}: no fee source id")
    elif not isinstance(doc, dict) or src not in (doc.get("slug"), doc.get("id"), doc.get("defillamaId")):
        bad.append(f"{pid}: fee source id {src!r} does not match the captured response's slug/id")
    elif e.get("scope") and doc.get("id") and str(doc["id"]).startswith(("parent#", "chain#")) and             e["scope"] != str(doc["id"]).split("#")[0]:
        bad.append(f"{pid}: scope {e['scope']!r} disagrees with captured id {doc['id']!r}")
    return bad


def coverage(cohort: list[dict], captures: Path, eligible: pd.MultiIndex, lag: int = PRIMARY_LAG,
             allow_unreviewed: bool = False) -> dict:
    ids = [e.get("product_id") for e in cohort]
    dupes = sorted({p for p in ids if ids.count(p) > 1})
    if dupes:
        raise ValueError(f"cohort repeats product ids {dupes}; one entry per product")
    if eligible.has_duplicates:
        raise ValueError("baseline eligible index has duplicate (date, product) pairs")
    per_product, rows = {}, []
    problems = []
    families = {}  # name -> product, for the source-family/parent-child overlap policy
    for e in cohort:
        pid = e["product_id"]
        st = e.get("status")
        info = {"status": st, "scope": e.get("scope"), "counting_rows": 0}
        if pid == "BTC-USD":
            problems.append(f"{pid}: benchmark, excluded")
            per_product[pid] = {**info, "excluded": "benchmark"}
            continue
        if st != "approved" and not allow_unreviewed:
            per_product[pid] = {**info, "excluded": "not approved"}
            continue
        if st != "approved":
            problems.append(f"{pid}: counted although status is {st!r} (allow_unreviewed)")
        fee_file = (e.get("series_files") or {}).get("fees")
        if not fee_file or not (captures / fee_file).exists():
            per_product[pid] = {**info, "excluded": "no captured fee series"}
            continue
        path = captures / fee_file
        want = (e.get("series_sha256") or {}).get("fees")
        got = fd.sha256(path)
        info["fees_sha256"] = got
        if want != got:
            problems.append(f"{pid}: fee series hash {'missing' if not want else 'mismatch'}")
        doc = json.loads(path.read_text(encoding="utf-8"))
        if st == "approved":
            problems.extend(validate_entry(e, doc))
        names = _names(doc) | ({str(e["source_family"]).lower()} if e.get("source_family") else set())
        src = (e.get("source_ids") or {}).get("fees")
        if src:
            names.add(str(src).lower())
        clash = sorted({families[n] for n in names if n in families})
        if clash:
            problems.append(f"{pid}: fee source family overlaps {clash}")
        for n in names:
            families.setdefault(n, pid)
        series, sinfo = fd.parse_series(path)
        feat, reasons = fd.trend(series)
        dec = fd.to_decision_dates(feat, lag).dropna()
        prods = eligible.get_level_values("product")
        dates = eligible.get_level_values("date")[prods == pid]
        hit = dates[dates.isin(dec.index)]
        info.update(series=sinfo, feature=reasons, eligible_rows=int(len(dates)), counting_rows=int(len(hit)),
                    first_counting=str(hit.min().date()) if len(hit) else None, last_counting=str(hit.max().date()) if len(hit) else None)
        per_product[pid] = info
        rows.extend((d, pid) for d in hit)
    idx = pd.MultiIndex.from_tuples(rows, names=["date", "product"]) if rows else None
    if idx is not None and idx.has_duplicates:
        raise ValueError("matched (date, product) pairs are not unique")
    counts = idx.to_frame(index=False).groupby("date")["product"].nunique() if rows else pd.Series(dtype=int)
    return {"per_product": per_product, "per_day_counts": counts, "problems": problems}


def evaluate_gate(counts: pd.Series, problems: list[str]) -> dict:
    g = GATES
    t0, t1 = (pd.Timestamp(x) for x in g["test_window"])
    test_days = pd.date_range(t0, t1, freq="D")
    c = counts.reindex(test_days).fillna(0)
    ok_days = c >= g["G1_min_coins"]
    iso = test_days.isocalendar()
    wk = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()
    weeks_ok = len(set(wk[ok_days.to_numpy()]))
    before, need = g["G3_min_rows_before"]
    allc = counts
    # the first June fit only sees decision dates before June 1 minus the purge/embargo (labels must have resolved)
    cutoff = pd.Timestamp(before) - pd.Timedelta(days=g["embargo_days"])
    rows_before = int(allc[(allc.index < cutoff) & (allc >= g["G1_min_coins"])].sum())
    d0, d1 = (pd.Timestamp(x) for x in g["discovery_window"])
    disc = allc[(allc.index >= d0) & (allc.index <= d1) & (allc >= g["G1_min_coins"])]
    diso = disc.index.isocalendar() if len(disc) else None
    disc_weeks = len(set((diso["year"].astype(int) * 100 + diso["week"].astype(int)).tolist())) if len(disc) else 0
    res = {
        "G1": {"share_of_test_days_with_20": float(ok_days.mean()), "required": g["G1_share_of_test_days"],
               "pass": bool(ok_days.mean() >= g["G1_share_of_test_days"])},
        "G2": {"test_weeks_with_a_20_coin_day": weeks_ok, "required": g["G2_min_test_weeks"], "pass": weeks_ok >= g["G2_min_test_weeks"]},
        "G3": {"counting_rows_before_first_fit_cutoff_on_20_coin_days": rows_before, "first_fit_cutoff": str(cutoff.date()),
               "required": need, "pass": rows_before >= need,
               "note": "coverage screen: labels missing at fit time can still reduce fitting rows; certify first-fit readiness before discovery"},
        "G4": {"discovery_weeks_with_a_20_coin_day": disc_weeks, "required": g["G4_min_discovery_weeks"], "pass": disc_weeks >= g["G4_min_discovery_weeks"]},
        "G5": {"problems": problems, "pass": not problems},
        "test_period_coins_per_day": {"max": int(c.max()) if len(c) else 0, "median": float(c.median()) if len(c) else 0.0,
                                      "mean": float(c.mean()) if len(c) else 0.0},
    }
    res["gate_passed"] = all(res[k]["pass"] for k in ("G1", "G2", "G3", "G4", "G5"))
    return res


def pilot_cohort(captures: Path) -> list[dict]:
    """Cohort file from Codex's pilot capture, every entry marked unreviewed (status 'held')."""
    manifest = {r["name"]: r for r in json.loads((captures / "MANIFEST.json").read_text(encoding="utf-8"))}
    pilot = json.loads((captures / "DEFILLAMA_PILOT_MEASUREMENTS.json").read_text(encoding="utf-8"))
    out = []
    for row in pilot["rows"]:
        pid = row["product_id"]
        stem = pid.split("-")[0]
        names = {m: n for m in ("dailyFees", "dailyRevenue", "tvl") for n in (f"{stem}_{m}", f"{stem}_child_{m}") if n in manifest and manifest[n].get("sha256") and manifest[n].get("http_status") == 200}
        key = {"dailyFees": "fees", "dailyRevenue": "revenue", "tvl": "tvl"}
        out.append({"product_id": pid, "status": "held", "pilot_scope_label": row.get("scope"), "scope": row.get("scope"),
                    "source_urls": {key[m]: manifest[n]["url"] for m, n in names.items()},
                    "source_ids": {key[m]: manifest[n]["url"] for m, n in names.items()},
                    "series_files": {key[m]: f"{n}.json" for m, n in names.items()},
                    "series_sha256": {key[m]: manifest[n]["sha256"] for m, n in names.items()},
                    "identity_evidence": "not reviewed: Codex pilot capture of Gemini's cohort", "reviewer": None})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", type=Path)
    ap.add_argument("--captures", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--allow-unreviewed", action="store_true", help="count held entries (for reproducing a pilot only; G5 then fails)")
    ap.add_argument("--pilot-cohort", type=Path)
    ap.add_argument("--write", type=Path)
    a = ap.parse_args()
    if a.pilot_cohort:
        a.write.write_text(json.dumps(pilot_cohort(a.pilot_cohort), indent=1), encoding="utf-8")
        return 0
    cfg = panel.load_config()
    cohort = json.loads(a.cohort.read_text(encoding="utf-8"))
    cov = coverage(cohort, a.captures, eligible_index(cfg), allow_unreviewed=a.allow_unreviewed)
    gate = evaluate_gate(cov["per_day_counts"], cov["problems"])
    counts = cov["per_day_counts"]
    report = {"protocol": "docs/research/FUNDAMENTALS_EXPERIMENT_PROTOCOL.md", "primary_lag_days": PRIMARY_LAG,
              "allow_unreviewed": a.allow_unreviewed, "cohort_entries": len(cohort), "gate": gate,
              "max_coins_on_any_day": int(counts.max()) if len(counts) else 0,
              "days_with_20_or_more_any_period": int((counts >= 20).sum()) if len(counts) else 0,
              "per_product": cov["per_product"],
              "per_day_counts": {str(k.date()): int(v) for k, v in counts.items()}}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=1, default=float), encoding="utf-8")
    print(json.dumps({k: v for k, v in gate.items() if k != "G5"} | {"G5_problems": len(gate["G5"]["problems"]),
                     "max_coins_on_any_day": report["max_coins_on_any_day"]}, indent=1))
    return 0 if gate["gate_passed"] else 3


if __name__ == "__main__":
    sys.exit(main())
