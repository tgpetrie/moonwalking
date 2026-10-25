"""Freeze and verify the existing daily research inputs without fetching data.

Raw source files are copied byte-for-byte into raw/. The uppercase checkpoint
MANIFEST.json stays outside raw/ because the source contains manifest.json and
Windows filenames are case-insensitive. No runtime modules are imported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

DAY = 86400


def utc_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()


def timestamp(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def daily_rows(path: Path, floor: int, end: int) -> tuple[dict, dict]:
    """Read Coinbase [time, low, high, open, close, volume] response rows.

    Window boundaries can repeat candles. Conflicting repeats are reported and
    removed from usable data; no arbitrary version wins. Bounds exclude partial
    days at the collection end. Missing days are reported, never filled.
    """
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("product_id") != path.stem or doc.get("granularity") != DAY:
        raise ValueError(f"Identity/granularity mismatch: {path.name}")
    rows, conflicts = {}, set()
    repeats = invalid = failed_windows = raw_count = outside = 0
    for window in doc.get("windows", []):
        if window.get("http_status") != 200:
            failed_windows += 1
            continue
        response = window.get("response")
        if not isinstance(response, list):
            raise ValueError(f"Non-list candle response: {path.name}")
        for row in response:
            raw_count += 1
            try:
                if len(row) != 6:
                    raise ValueError("Expected six candle fields")
                values = tuple(float(v) for v in row)
                t, low, high, op, close, volume = values
                if (not all(math.isfinite(v) for v in values) or t != int(t)
                        or int(t) % DAY or low <= 0 or high < low
                        or not low <= op <= high or not low <= close <= high
                        or volume < 0):
                    raise ValueError("Invalid candle")
                t = int(t)
            except (TypeError, ValueError, OverflowError):
                invalid += 1
                continue
            if t < floor or t + DAY > end:
                outside += 1
                continue
            if t in rows:
                repeats += 1
                if rows[t] != values:
                    conflicts.add(t)
            else:
                rows[t] = values
    for t in conflicts:
        rows.pop(t, None)
    times = sorted(rows)
    expected = (times[-1] - times[0]) // DAY + 1 if times else 0
    return rows, {
        "product_id": path.stem, "status_at_collection": doc.get("status"),
        "raw_candles": raw_count, "usable_candles": len(rows),
        "first_date": utc_date(times[0]) if times else None,
        "last_date": utc_date(times[-1]) if times else None,
        "missing_days_inside_span": expected - len(rows),
        "duplicate_rows": repeats, "conflicting_days_excluded": len(conflicts),
        "invalid_rows": invalid, "failed_windows": failed_windows,
        "out_of_bounds_rows_excluded": outside,
    }


def inspect_panel(raw: Path) -> tuple[dict, list[dict]]:
    metadata = json.loads((raw / "manifest.json").read_text(encoding="utf-8"))
    floor, end = timestamp(metadata["floor"]), timestamp(metadata["end"])
    products, summaries = {}, []
    for path in sorted(raw.glob("*-USD.json")):
        rows, summary = daily_rows(path, floor, end)
        products[path.stem] = rows
        summaries.append(summary)
    listed = json.loads((raw / "products.json").read_text(encoding="utf-8"))
    ids = [p["id"] for p in listed]
    if len(ids) != len(set(ids)) or set(ids) != set(products):
        raise ValueError("products.json and per-product files do not match exactly")
    return products, summaries


def compare_hourly(products: dict, archive: Path, tolerance: float) -> dict:
    """Compare native daily closes with complete UTC days of hourly candles.

    Sparse/incomplete hourly days are counted separately. They cannot establish
    a daily close mismatch. The archive is opened read-only, without migrations.
    """
    connection = sqlite3.connect(archive.resolve().as_uri() + "?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    compared = matched = partial = absent = 0
    by_product, examples = [], []
    try:
        for product, daily in sorted(products.items()):
            if not daily:
                continue
            days = {}
            for ts, close in connection.execute(
                "SELECT ts, close FROM candles WHERE product_id=? AND granularity=3600 ORDER BY ts",
                (product,),
            ):
                day = ts - ts % DAY
                entry = days.setdefault(day, {"hours": set(), "last_ts": -1, "close": None})
                if ts % 3600 == 0:
                    entry["hours"].add(ts)
                if ts > entry["last_ts"]:
                    entry.update(last_ts=ts, close=close)
            count = ok = 0
            for day, entry in days.items():
                if day not in daily:
                    absent += 1
                    continue
                if len(entry["hours"]) != 24 or entry["last_ts"] != day + 23 * 3600:
                    partial += 1
                    continue
                count += 1
                native = daily[day][4]
                error = abs(entry["close"] - native) / native
                if error <= tolerance:
                    ok += 1
                elif len(examples) < 25:
                    examples.append({"product_id": product, "date": utc_date(day),
                                     "daily_close": native, "hourly_close": entry["close"],
                                     "relative_error": error})
            if count:
                by_product.append({"product_id": product, "compared_days": count,
                                   "matched_days": ok, "mismatched_days": count - ok})
            compared += count
            matched += ok
    finally:
        connection.close()
    return {
        "archive": str(archive.resolve()), "relative_close_tolerance": tolerance,
        "compared_complete_days": compared, "matched_days": matched,
        "match_fraction": matched / compared if compared else None,
        "partial_hourly_days_not_compared": partial,
        "hourly_days_without_usable_daily_row": absent,
        "per_product": by_product, "mismatch_examples": examples,
    }


def funding_candidates(raw: Path, panel: dict) -> dict:
    candidates = json.loads(raw.read_text(encoding="utf-8"))
    present, missing, empty = [], [], []
    for symbol, meta in sorted(candidates.items()):
        product = symbol + "-USD"
        if product not in panel:
            missing.append(product)
        elif not panel[product]:
            empty.append(product)
        else:
            times = sorted(panel[product])
            present.append({"product_id": product, "provider_name": meta["hl_name"],
                            "daily_first_date": utc_date(times[0]),
                            "daily_last_date": utc_date(times[-1]),
                            "funding_first_date": utc_date(meta["first_ts"] // 1000)})
    return {"identity_status": "ticker_candidates_only_not_identity_verified",
            "candidate_count": len(candidates), "with_daily_candles": present,
            "missing_daily_file": missing, "empty_daily_file": empty}


def copy_exclusive(source: Path, target: Path) -> dict:
    data = source.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    with target.open("xb") as stream:
        stream.write(data)
    if digest(source) != sha or digest(target) != sha:
        raise ValueError(f"Source changed during copy or copy differs: {source.name}")
    return {"sha256": sha, "bytes": len(data)}


def freeze(source: Path, destination: Path, archive: Path, candidate_map: Path) -> dict:
    source, destination = source.resolve(), destination.resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("Source and destination must be separate trees")
    sources = sorted(source.glob("*.json"))
    if not sources or not (source / "products.json").is_file() or not (source / "manifest.json").is_file():
        raise ValueError("Source must be the existing fetch_daily_all output directory")
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "raw").mkdir()
    (destination / "metadata").mkdir()
    records = []
    for path in sources:
        relative = "raw/" + path.name
        records.append({"path": relative, **copy_exclusive(path, destination / relative)})
    relative = "metadata/funding_candidates.json"
    records.append({"path": relative, **copy_exclusive(candidate_map, destination / relative)})
    panel, summaries = inspect_panel(destination / "raw")
    report = {
        "product_files": len(panel), "products_with_candles": sum(bool(v) for v in panel.values()),
        "total_usable_daily_candles": sum(len(v) for v in panel.values()),
        "products": summaries,
        "funding_candidates": funding_candidates(destination / relative, panel),
        "hourly_crosscheck": compare_hourly(panel, archive, 0.001),
        "limitations": [
            "Missing bars are not filled; the cause of a missing bar is not established here.",
            "The daily panel includes inactive products but was fetched from a 2026 product list; historical listing completeness is not proven.",
            "Provider ticker matches are candidates, not verified identities; RNDR and RENDER are never joined.",
            "Backfilled data is not a historical point-in-time record of availability or revisions.",
        ],
    }
    passed = report["hourly_crosscheck"]["match_fraction"]
    report["crosscheck_acceptance"] = "pass" if passed is not None and passed >= 0.99 else "needs_review"
    report_path = destination / "QUALITY_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    records.append({"path": report_path.name, "sha256": digest(report_path), "bytes": report_path.stat().st_size})
    manifest = {
        "schema_version": 1, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_directory": str(source), "raw_file_count": len(sources),
        "files": records, "products": summaries,
    }
    (destination / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return verify(destination)


def verify(destination: Path) -> dict:
    destination = destination.resolve()
    manifest = json.loads((destination / "MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported manifest version")
    records = manifest["files"]
    expected = {record["path"] for record in records}
    if len(expected) != len(records):
        raise ValueError("Duplicate manifest paths")
    for record in records:
        path = (destination / record["path"]).resolve()
        if destination not in path.parents:
            raise ValueError("Manifest path escapes the checkpoint")
        if path.stat().st_size != record["bytes"] or digest(path) != record["sha256"]:
            raise ValueError(f"Hash or size differs: {record['path']}")
    actual = {str(p.relative_to(destination)).replace("\\", "/")
              for p in destination.rglob("*") if p.is_file() and p != destination / "MANIFEST.json"}
    if actual != expected:
        raise ValueError("Unexpected or missing checkpoint files")
    _, summaries = inspect_panel(destination / "raw")
    if summaries != manifest["products"]:
        raise ValueError("Parsed candle metadata differs from the manifest")
    report = json.loads((destination / "QUALITY_REPORT.json").read_text(encoding="utf-8"))
    return {"checkpoint": str(destination), "raw_files_verified": manifest["raw_file_count"],
            "all_hashed_files_verified": len(records), "product_files": len(summaries),
            "products_with_candles": report["products_with_candles"],
            "total_usable_daily_candles": report["total_usable_daily_candles"],
            "hourly_crosscheck": report["hourly_crosscheck"]["match_fraction"],
            "crosscheck_acceptance": report["crosscheck_acceptance"],
            "provider_identity_status": report["funding_candidates"]["identity_status"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "verify"))
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--candidate-map", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "freeze":
            if not all((args.source, args.archive, args.candidate_map)):
                parser.error("freeze requires --source, --archive and --candidate-map")
            result = freeze(args.source, args.destination, args.archive, args.candidate_map)
        else:
            result = verify(args.destination)
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        parser.exit(1, f"Checkpoint failed: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0 if result["crosscheck_acceptance"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
