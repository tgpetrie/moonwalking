"""Freeze one consistent board ledger and outcome-blind eligibility metadata.

Reads the live SQLite database with mode=ro and an explicit read transaction.
Copies episode rows byte-for-byte at the value level to a separate research DB.
Only feature/label presence, never outcome magnitudes, informs the report.
"""
from __future__ import annotations

import collections
import argparse
import csv
import hashlib
import json
import math
import os
import re
import sqlite3
import stat
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/research/results/live_movers_contract_20261027"
RAW = Path.home() / ".moonwalking/analysis/live_movers_contract_20261027"
SOURCE = Path.home() / ".moonwalking/data/signal_outcomes.sqlite"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8", newline="\n")


def stamp(text):
    return int(datetime.fromisoformat(text).timestamp())


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def phase_at(ts, cfg):
    for phase, (start, end) in cfg["phases"].items():
        upper = stamp(end) - (cfg["purge_before_next_phase_seconds"] if phase != "test" else 0)
        if stamp(start) <= ts < upper:
            return phase
    return None


def classify(row, cfg, cooldown):
    pid, board, ts = row["product_id"], row["board"], row["entered_ts"]
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]*-USD", pid or ""):
        return None, "noncanonical_identity", None
    if board not in {"ignition_1m", "confirmation_3m_up", "confirmation_3m_down"} or row["direction"] not in {"up", "down"}:
        return None, "invalid_board_or_direction", None
    key = (board, pid)
    if ts - cooldown.get(key, -10**12) < cfg["rolling_episode_cooldown_seconds"]:
        return None, "rolling_cooldown", None
    # Keep the first episode before inspecting its feature completeness.
    cooldown[key] = ts
    phase = phase_at(ts, cfg)
    if phase is None:
        return None, "outside_phases_or_purged", None
    try:
        snap = json.loads(row["feature_snapshot_json"] or "null")
    except ValueError:
        return None, "invalid_snapshot", None
    if not isinstance(snap, dict):
        return None, "missing_snapshot", None
    if row["feature_schema_version"] != cfg["required_snapshot_version"] or snap.get("model_version") != cfg["required_model_version"]:
        return None, "snapshot_or_model_version", snap
    captured = snap.get("captured_ts")
    if not finite(captured) or not 0 <= ts-captured <= cfg["max_snapshot_age_seconds"]:
        return None, "snapshot_timestamp", snap
    raw = snap.get("raw_inputs") or {}
    if not isinstance(raw, dict) or not all(finite(raw.get(k)) for k in cfg["required_raw_features"]):
        return None, "required_features_missing", snap
    if raw["pct_1m"] <= -100 or raw["pct_3m"] <= -100 or not finite(row["start_price"]) or row["start_price"] <= 0:
        return None, "invalid_price_input", snap
    if not finite(snap.get("live_score")):
        return None, "baseline_score_missing", snap
    if not all(finite(row[k]) for k in cfg["required_labels"]):
        return None, "label_unavailable", snap
    return phase, None, snap


def profile(db, cfg):
    con = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cooldown, rejects = {}, collections.Counter()
    phases = {k: {"rows": 0, "days": set(), "products": set(), "strata": collections.Counter()} for k in cfg["phases"]}
    daily = collections.defaultdict(lambda: {"rows": 0, "with_snapshot": 0, "non_null": collections.Counter()})
    fields = cfg["required_raw_features"] + cfg["optional_primary_features"] + cfg["forward_only_features"]
    with (RAW / "eligible_episodes.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["id", "board", "product_id", "direction", "entered_ts", "phase"])
        for row in con.execute("select * from episodes order by entered_ts,id"):
            day = datetime.fromtimestamp(row["entered_ts"], timezone.utc).date().isoformat()
            d = daily[day]
            d["rows"] += 1
            try:
                s = json.loads(row["feature_snapshot_json"] or "null")
            except ValueError:
                s = None
            if isinstance(s, dict):
                d["with_snapshot"] += 1
                raw = s.get("raw_inputs") or {}
                for k in fields:
                    if finite(raw.get(k)):
                        d["non_null"][k] += 1
            phase, why, _ = classify(row, cfg, cooldown)
            if why:
                rejects[why] += 1
                continue
            p = phases[phase]
            p["rows"] += 1
            p["days"].add(day)
            p["products"].add(row["product_id"])
            p["strata"][row["board"] + "/" + row["direction"]] += 1
            writer.writerow([row[k] for k in ["id", "board", "product_id", "direction", "entered_ts"]] + [phase])
    con.close()
    for name, p in phases.items():
        p["days"] = len(p["days"])
        p["products"] = len(p["products"])
        req = cfg["readiness"][name]
        p["pass"] = p["days"] >= req["min_days"] and p["rows"] >= req["min_episodes"] and p["products"] >= req["min_products"]
    return {"phases": phases, "rejections": dict(rejects), "feature_coverage_by_day": dict(sorted(daily.items())),
            "ready": all(p["pass"] for p in phases.values()), "outcome_values_summarized": False}


def main():
    global RAW, SOURCE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--capture-dir", type=Path, default=RAW)
    parser.add_argument("--contract", type=Path, default=OUT / "CONTRACT.json")
    parser.add_argument("--report-prefix", default="")
    args = parser.parse_args()
    RAW, SOURCE = args.capture_dir.resolve(), args.source.resolve()
    cfg_path = args.contract.resolve()
    if not re.fullmatch(r"[A-Z_]*", args.report_prefix):
        raise SystemExit("Report prefix must contain only uppercase letters and underscores")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    if RAW.exists():
        raise SystemExit("Research capture already exists; do not overwrite the frozen snapshot")
    RAW.mkdir(parents=True)
    source = sqlite3.connect(SOURCE.as_uri() + "?mode=ro", uri=True, timeout=5)
    source.execute("pragma query_only=on")
    source.execute("begin")
    cols = source.execute("pragma table_info(board_outcomes_v2)").fetchall()
    db = RAW / "board_episodes.sqlite"
    dest = sqlite3.connect(db)
    names = [c[1] for c in cols]
    quoted = lambda s: '"' + s.replace('"', '""') + '"'
    definitions = [quoted(c[1]) + " " + (c[2] if c[2] in {"INTEGER", "REAL", "TEXT", "BLOB", "NUMERIC"} else "TEXT") for c in cols]
    dest.execute("create table episodes (" + ",".join(definitions) + ")")
    cur = source.execute("select * from board_outcomes_v2 where entered_ts < ? order by id", (stamp(cfg["decision_cutoff_exclusive_utc"]),))
    rows = 0
    with dest:
        while True:
            batch = cur.fetchmany(1000)
            if not batch:
                break
            dest.executemany("insert into episodes values (" + ",".join("?" for _ in names) + ")", batch)
            rows += len(batch)
    source.rollback()
    source.close()
    dest.execute("create unique index episode_id on episodes(id)")
    dest.execute("create index episode_time on episodes(entered_ts,id)")
    dest.commit()
    assert dest.execute("pragma integrity_check").fetchone()[0] == "ok"
    dest.close()
    result = profile(db, cfg)
    write(RAW / "CONTRACT.json", cfg)
    manifest = {"captured_at_utc": datetime.now(timezone.utc).isoformat(), "source": str(SOURCE),
                "source_access": "mode=ro; explicit consistent read transaction; rows copied without revision",
                "source_table": "board_outcomes_v2", "rows": rows,
                "decision_cutoff_exclusive_utc": cfg["decision_cutoff_exclusive_utc"],
                "contract_sha256": digest(cfg_path), "freeze_script_sha256": digest(Path(__file__)),
                "files": {p.name: {"bytes": p.stat().st_size, "sha256": digest(p)} for p in RAW.iterdir() if p.is_file()}}
    write(RAW / "MANIFEST.json", manifest)
    result.update(rows_captured=rows, manifest_sha256=digest(RAW / "MANIFEST.json"))
    write(OUT / (args.report_prefix + "COVERAGE.json"), result)
    write(OUT / (args.report_prefix + "CAPTURE_MANIFEST.json"), manifest)
    for p in RAW.iterdir():
        if p.is_file():
            os.chmod(p, stat.S_IREAD)
    print(json.dumps({"rows_captured": rows, "phases": result["phases"], "ready": result["ready"]}, indent=2))


if __name__ == "__main__":
    main()
