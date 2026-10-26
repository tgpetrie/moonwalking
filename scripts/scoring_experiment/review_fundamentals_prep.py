"""Reproduce the 2026-10-26 fundamentals preparation review, without outcomes.

--capture saves first public fee-endpoint responses outside Git. Otherwise uses
those saved responses only. No model fit, label access or source approval occurs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import fundamentals as fd
import fundamentals_gate as gate
import panel

ROOT = Path(__file__).resolve().parents[2]
CAPTURES = Path.home() / ".moonwalking/analysis/fundamentals_review_20261026"
PRIOR = Path.home() / ".moonwalking/analysis/source_review_20261026"
OUT = ROOT / "docs/research/results/fundamentals_review_20261026"
PROPOSED = dict(zip(
    "AAVE UNI LDO CRV COMP SNX DYDX PENDLE RPL BAL SUSHI 1INCH YFI CVX LQTY JTO JUP RAY ORCA AERO ETH SOL AVAX NEAR ARB OP APT SUI SEI INJ STX ADA".split(),
    "aave uniswap lido curve-finance compound-finance synthetix dydx pendle rocket-pool balancer sushi 1inch-network yearn-finance convex-finance liquity jito jupiter raydium orca aerodrome ethereum solana avalanche near arbitrum optimism aptos sui sei injective stacks cardano".split(),
))
ALTERNATIVES = {"1INCH_alternative": "1inch", "OP_alternative": "op-mainnet"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")


def capture():
    """No retries, overwrites or claims of global absence on endpoint failure."""
    CAPTURES.mkdir(parents=True, exist_ok=True)
    # Alternatives are separately named diagnostics, never substitutions in the
    # frozen 32-candidate coverage calculation below.
    for symbol, slug in {**PROPOSED, **ALTERNATIVES}.items():
        meta = CAPTURES / (symbol + "_capture.json")
        if meta.exists():
            continue
        url = "https://api.llama.fi/summary/fees/" + slug + "?dataType=dailyFees"
        record = {"url": url, "captured_at_utc": datetime.now(timezone.utc).isoformat()}
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "MoonwalkingResearch/1.0"})
            with urllib.request.urlopen(request, timeout=35) as response:
                body = response.read()
                record["http_status"] = response.status
            record["bytes"] = len(body)
            record["sha256"] = hashlib.sha256(body).hexdigest()
            (CAPTURES / (symbol + "_fees.json")).write_bytes(body)
        except urllib.error.HTTPError as error:
            record["http_status"] = error.code
            record["error"] = str(error)
        except Exception as error:
            record["error"] = str(error)
        write(meta, record)
        print("CAPTURE", symbol, record.get("http_status"), flush=True)
        time.sleep(1)


def count_summary(counts, start, end):
    c = counts.reindex(pd.date_range(start, end)).fillna(0)
    return {"days": len(c), "min": int(c.min()), "max": int(c.max()),
            "median": float(c.median()), "days_with_20": int((c >= 20).sum())}


def alternative_evidence():
    out = []
    for name, slug in ALTERNATIVES.items():
        path = CAPTURES / (name + "_capture.json")
        if not path.exists():
            continue
        record = {"name": name, "not_used_in_32_candidate_counts": True, **read(path)}
        if record.get("http_status") == 200:
            raw = CAPTURES / (name + "_fees.json")
            assert fd.sha256(raw) == record["sha256"]
            doc = read(raw)
            record["returned_metadata"] = {k: doc.get(k) for k in ["id", "name", "category", "address", "gecko_id", "linkedProtocols"]}
            _, record["fee_profile"] = fd.parse_series(raw)
        out.append(record)
    return out


def reproduce_gate_bypasses():
    """Diagnostic reproductions of the unmodified 5cfbf26 checker, not fixes."""
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        days = pd.date_range("2022-01-01", "2026-10-18")
        file = root / "fees.json"
        write(file, {"totalDataChart": [[int(d.timestamp()), 100 + i] for i, d in enumerate(days)]})
        index = pd.MultiIndex.from_product([days, ["A-USD"]], names=["date", "product"])
        entries = [{"product_id": "A-USD", "status": "approved", "scope": "protocol",
                    "source_ids": {"fees": "claimed-slug-" + str(i)},
                    "series_files": {"fees": file.name}, "series_sha256": {"fees": fd.sha256(file)}} for i in range(20)]
        cov = gate.coverage(entries, root, index)
        result = gate.evaluate_gate(cov["per_day_counts"], cov["problems"])
        one = gate.coverage(entries[:1], root, index)
        boundary = pd.Series(20, index=pd.date_range(pd.Timestamp("2024-06-01") - pd.Timedelta(days=250), "2026-10-10"))
        boundary_gate = gate.evaluate_gate(boundary, [])
        return {"duplicate_product": {"actual_unique_products": 1, "cohort_entries": len(entries),
                                      "reported_max_coins": int(cov["per_day_counts"].max()), "gate": result},
                "missing_identity_review_fields": {"fields_missing": ["identity_evidence", "reviewer", "reviewed_at"],
                                                   "reported_problems": one["problems"],
                                                   "counting_rows": one["per_product"]["A-USD"]["counting_rows"]},
                "training_readiness_boundary": {"G3": boundary_gate["G3"],
                                                "rows_before_2024_05_24_purge_cutoff": int(boundary[boundary.index < "2024-05-24"].sum())}}


def measure(verify_funding=False):
    idx = gate.eligible_index(panel.load_config())
    products = idx.get_level_values("product")
    dates = idx.get_level_values("date")
    funding = read(ROOT / "docs/research/results/funding_identity_audit_20261025/APPROVED_FUNDING_MAP.json")
    rows, feature_rows, source_records, cohort = [], [], [], []
    for symbol, slug in PROPOSED.items():
        pid = symbol + "-USD"
        ds = dates[products == pid]
        row = {"product_id": pid, "proposed_fee_slug": slug, "in_approved_funding_map": pid in funding,
               "baseline_rows": len(ds), "baseline_first": str(ds.min().date()) if len(ds) else None,
               "baseline_last": str(ds.max().date()) if len(ds) else None,
               "baseline_eligible_2023_01_01": pd.Timestamp("2023-01-01") in ds}
        entry = {"product_id": pid, "status": "held", "scope": None,
                 "source_ids": {"fees": slug}, "series_files": {}, "series_sha256": {},
                 "identity_evidence": None, "reviewer": None, "reviewed_at": None,
                 "review_note": "Candidate only: not an approved token-to-source association."}
        meta = CAPTURES / (symbol + "_capture.json")
        if meta.exists():
            record = read(meta)
            source_records.append({"symbol": symbol, **record})
            row["http_status"] = record.get("http_status")
            if record.get("http_status") == 200:
                path = CAPTURES / (symbol + "_fees.json")
                assert fd.sha256(path) == record["sha256"]
                doc = read(path)
                row["returned_metadata"] = {k: doc.get(k) for k in ["name", "id", "category", "parentProtocol", "linkedProtocols", "address", "gecko_id", "chains", "protocolType"]}
                entry.update(series_files={"fees": path.name}, series_sha256={"fees": record["sha256"]},
                             source_urls={"fees": record["url"]}, captured_at_utc=record["captured_at_utc"],
                             returned_metadata=row["returned_metadata"])
                entry["scope"] = ("chain" if doc.get("category") == "Chain" else
                                  "parent" if str(doc.get("id", "")).startswith("parent#") else "protocol")
                try:
                    series, profile = fd.parse_series(path)
                    row["fee_profile"] = profile
                    feature, reasons = fd.trend(series)
                    row["feature_profile"] = reasons
                    hit = ds[ds.isin(fd.to_decision_dates(feature, 2).dropna().index)]
                    feature_rows.extend((d, pid) for d in hit)
                    row["fee_feature_baseline_rows_before_identity_review"] = len(hit)
                except (ValueError, KeyError, TypeError) as error:
                    row["series_error"] = str(error)
        rows.append(row)
        cohort.append(entry)
    selection = products.isin([s + "-USD" for s in PROPOSED])
    price_counts = pd.Series(1, index=idx[selection]).groupby(level="date").size()
    feature_counts = (pd.Series(1, index=pd.MultiIndex.from_tuples(feature_rows, names=["date", "product"]))
                      .groupby(level="date").size()) if feature_rows else pd.Series(dtype=int)
    coinbase = read(PRIOR / "coinbase_currencies.json")
    identity = [c for c in coinbase if c.get("id") in ["JUP", "JUPITER", "DYDX", "PENDLE", "RAY"]]
    result = {"reviewed_commit": "5cfbf26fff4698c13b08447d0237b2d46ea20bec", "outcomes_used": False,
              "provenance": "retrospective_catalog_backfill_subject_to_adapter_revisions",
              "baseline_config_sha256": fd.sha256(Path(__file__).with_name("config.json")),
              "baseline_build_metadata_sha256": fd.sha256(Path.home() / ".moonwalking/analysis/scoring_baseline/build_base.json"),
              "proposed_approved_products": len(PROPOSED), "funding_map_members": sum(r["in_approved_funding_map"] for r in rows),
              "products": rows, "coinbase_identity_records": identity,
              "coinbase_identity_capture_sha256": fd.sha256(PRIOR / "coinbase_currencies.json"),
              "price_only": {}, "fee_intersection_unreviewed": {}, "captures": source_records,
              "separate_alternative_endpoint_diagnostics": alternative_evidence(),
              "gate_bypasses": reproduce_gate_bypasses()}
    for name, start, end in [("discovery", "2023-01-01", "2024-12-23"), ("test", "2025-01-01", "2026-10-10")]:
        result["price_only"][name] = count_summary(price_counts, start, end)
        result["fee_intersection_unreviewed"][name] = count_summary(feature_counts, start, end)
    # This is an upper bound with every proposed identity admitted, never approval.
    result["unreviewed_feature_gate"] = gate.evaluate_gate(feature_counts, ["all proposed identities remain unapproved in this review"])
    if verify_funding:
        raw = Path.home() / ".moonwalking/data/hl_funding_20261025"
        manifest = read(raw / "MANIFEST.json")
        bad, writable = [], []
        for record in manifest["files"]:
            path = raw / record["path"]
            if not path.exists() or path.stat().st_size != record["bytes"] or fd.sha256(path) != record["sha256"]:
                bad.append(record["path"])
            if path.exists() and not path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY:
                writable.append(record["path"])
        result["funding_preservation"] = {"manifest_sha256": fd.sha256(raw / "MANIFEST.json"), "files": len(manifest["files"]),
                                          "hash_or_size_failures": bad, "not_readonly": writable,
                                          "tag_target": subprocess.check_output(["git", "rev-parse", "research/funding-comparison-2026-10-26^{}"], cwd=ROOT, text=True).strip()}
    write(OUT / "MEASUREMENTS.json", result)
    write(OUT / "PROPOSED_COHORT_HELD.json", cohort)
    print(json.dumps({k: result[k] for k in ["funding_map_members", "price_only", "fee_intersection_unreviewed", "unreviewed_feature_gate"]}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--verify-funding", action="store_true")
    args = ap.parse_args()
    if args.capture:
        capture()
    measure(args.verify_funding)
