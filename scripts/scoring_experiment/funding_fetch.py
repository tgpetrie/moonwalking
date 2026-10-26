"""Collect Hyperliquid hourly funding history for the approved map into an isolated research folder.

Public keyless endpoint: POST https://api.hyperliquid.xyz/info {"type":"fundingHistory","coin":...,"startTime":ms,"endTime":ms}
(500 rows per response, pages forward). Original responses are stored byte-for-byte with request body, capture time and
SHA-256, one file per request, so the collection is resumable and auditable. Nothing is written to Git by this script,
to the frozen panel, or to any application store. One request per 1.1 seconds, with back-off on 429/5xx.

    python scripts/scoring_experiment/funding_fetch.py --map <APPROVED_FUNDING_MAP.json> --out <new folder> [--only AAVE-USD]
    python scripts/scoring_experiment/funding_fetch.py --summarize --out <folder>      # coverage + hashes, no network
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://api.hyperliquid.xyz/info"
PAGE = 500
PACE_SECONDS = 1.1
# Frozen panel's last complete UTC day is 2026-10-18, so history is requested up to 2026-10-19 00:00:00 UTC inclusive.
END_MS = int(datetime(2026, 10, 19, tzinfo=timezone.utc).timestamp() * 1000)
HOUR_MS = 3_600_000


def post(body: dict) -> tuple[bytes, int]:
    data = json.dumps(body, separators=(",", ":")).encode()
    req = urllib.request.Request(URL, data=data, headers={"Content-Type": "application/json"})
    delay = 5.0
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read(), r.status
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(delay)
                delay = min(delay * 2, 120)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(delay)
            delay = min(delay * 2, 120)
    raise RuntimeError("too many retries")


def pages_for(folder: Path) -> list[Path]:
    return sorted(folder.glob("page_*.json"))


def last_time(folder: Path) -> int | None:
    pages = pages_for(folder)
    if not pages:
        return None
    rec = json.loads(pages[-1].read_text(encoding="utf-8"))
    rows = json.loads(rec["response_text"])
    return rows[-1]["time"] if rows else None


def fetch_coin(name: str, folder: Path, log) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    done = folder / "COMPLETE"
    if done.exists():
        return
    start = 0
    lt = last_time(folder)
    if lt is not None:
        start = lt + 1
    n = len(pages_for(folder))
    while True:
        body = {"type": "fundingHistory", "coin": name, "startTime": start, "endTime": END_MS}
        text, status = post(body)
        n += 1
        rows = json.loads(text)
        rec = {"request": body, "captured_utc": datetime.now(timezone.utc).isoformat(), "http_status": status,
               "sha256_of_response": hashlib.sha256(text).hexdigest(), "rows": len(rows),
               "response_text": text.decode("utf-8")}
        (folder / f"page_{n:04d}.json").write_text(json.dumps(rec), encoding="utf-8")
        time.sleep(PACE_SECONDS)
        if len(rows) < PAGE:
            break
        start = rows[-1]["time"] + 1
    done.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    log(f"{name}: {n} pages")


def load_rows(folder: Path) -> list[dict]:
    out = []
    for p in pages_for(folder):
        out.extend(json.loads(json.loads(p.read_text(encoding="utf-8"))["response_text"]))
    return out


def summarize(out: Path) -> dict:
    products = {}
    for d in sorted(x for x in (out / "raw").iterdir() if x.is_dir()):
        pages = pages_for(d)
        rows = load_rows(d)
        times = [r["time"] for r in rows]
        gaps = [(b - a) for a, b in zip(times, times[1:])]
        products[d.name] = {
            "complete": (d / "COMPLETE").exists(), "pages": len(pages), "rows": len(rows),
            "first_time_ms": times[0] if times else None, "last_time_ms": times[-1] if times else None,
            "first_utc": datetime.fromtimestamp(times[0] / 1000, timezone.utc).isoformat() if times else None,
            "last_utc": datetime.fromtimestamp(times[-1] / 1000, timezone.utc).isoformat() if times else None,
            "duplicate_timestamps": len(times) - len(set(times)),
            "out_of_order": int(sum(1 for g in gaps if g <= 0)),
            "gaps_over_90_minutes": int(sum(1 for g in gaps if g > 1.5 * HOUR_MS)),
            "missing_hours_estimate": int(sum(round(g / HOUR_MS) - 1 for g in gaps if g > 1.5 * HOUR_MS)),
            "response_sha256": [json.loads(p.read_text(encoding="utf-8"))["sha256_of_response"] for p in pages],
        }
    return products


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only")
    ap.add_argument("--summarize", action="store_true")
    a = ap.parse_args()
    if a.summarize:
        s = summarize(a.out)
        (a.out / "FUNDING_SUMMARY.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
        print(json.dumps({k: v["rows"] for k, v in s.items()}, indent=0)[:500])
        return 0
    amap = json.loads(a.map.read_text(encoding="utf-8"))
    (a.out / "raw").mkdir(parents=True, exist_ok=True)
    (a.out / "APPROVED_FUNDING_MAP.json").write_text(a.map.read_text(encoding="utf-8"), encoding="utf-8")
    items = [(k, v["hyperliquid_name"]) for k, v in sorted(amap.items()) if not a.only or k == a.only]
    for i, (pid, name) in enumerate(items, 1):
        fetch_coin(name, a.out / "raw" / pid, lambda m: print(f"[{i}/{len(items)}] {m}", flush=True))
    print("collection finished", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
