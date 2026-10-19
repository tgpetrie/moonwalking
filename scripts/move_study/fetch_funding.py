"""Fetch settled perp funding for Study 3a events (Binance Vision archives, Hyperliquid).

Public, unauthenticated, at most one request per 1.1 s, resumable (cached files
are not fetched again). Raw responses are kept under --out.

  python scripts/move_study/fetch_funding.py --daily-dir <daily_all> --out <funding dir> --plan
  python scripts/move_study/fetch_funding.py --daily-dir <daily_all> --out <funding dir>
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import continuation_vs_reversal as cs  # noqa: E402

DAY = cs.DAY
UA = "moonwalking-research/1.0 (read-only public data)"
VISION = "https://data.binance.vision"
S3_LIST = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
HL = "https://api.hyperliquid.xyz/info"
_last = 0.0
COUNT = 0


def throttle():
    global _last, COUNT
    wait = 1.1 - (time.monotonic() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.monotonic()
    COUNT += 1


def get(url: str) -> requests.Response:
    throttle()
    return requests.get(url, headers={"User-Agent": UA}, timeout=30)


def post(body: dict) -> requests.Response:
    throttle()
    return requests.post(HL, json=body, headers={"User-Agent": UA}, timeout=30)


def binance_symbols(out: Path) -> set[str]:
    cache = out / "binance_symbols.json"
    if cache.exists():
        return set(json.loads(cache.read_text()))
    syms, marker = set(), ""
    while True:
        r = get(f"{S3_LIST}?delimiter=/&prefix=data/futures/um/monthly/fundingRate/&marker={marker}")
        r.raise_for_status()
        found = re.findall(r"<Prefix>data/futures/um/monthly/fundingRate/([^/<]+)/</Prefix>", r.text)
        syms.update(found)
        if "<IsTruncated>true</IsTruncated>" not in r.text or not found:
            break
        marker = f"data/futures/um/monthly/fundingRate/{found[-1]}/"
    cache.write_text(json.dumps(sorted(syms)))
    return syms


def hl_universe(out: Path) -> set[str]:
    cache = out / "hl_universe.json"
    if cache.exists():
        return set(json.loads(cache.read_text()))
    r = post({"type": "meta"})
    r.raise_for_status()
    names = [a["name"] for a in r.json()["universe"]]
    cache.write_text(json.dumps(names))
    return set(names)


def candidates(base: str, pool: set[str], venue: str) -> list[str]:
    if venue == "binance":
        opts = [f"{base}USDT", f"1000{base}USDT", f"1000000{base}USDT"]
    else:
        opts = [base, f"k{base}"]
    return [o for o in opts if o in pool]


def month(day: int) -> str:
    return pd.Timestamp(day * DAY, unit="s").strftime("%Y-%m")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--daily-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--plan", action="store_true", help="count requests and stop")
    args = ap.parse_args()
    out = Path(args.out)
    (out / "binance").mkdir(parents=True, exist_ok=True)
    (out / "hl").mkdir(parents=True, exist_ok=True)

    d = cs.load_daily_dir(Path(args.daily_dir), "2022-01-03", "2026-10-17")
    ev, _, _ = cs.build_panel(d)
    ev = ev[["day", "product", "direction"]].copy()
    ev["base"] = ev["product"].str.replace("-USD", "", regex=False)
    ev.to_csv(out / "events.csv", index=False)

    bsyms, hsyms = binance_symbols(out), hl_universe(out)
    bmap = {b: candidates(b, bsyms, "binance") for b in ev.base.unique()}
    hmap = {b: candidates(b, hsyms, "hl") for b in ev.base.unique()}
    bmap = {k: v[0] for k, v in bmap.items() if v}
    hmap = {k: v[0] for k, v in hmap.items() if v}

    b_jobs = sorted({(bmap[b], month(dy)) for b, dy in zip(ev.base, ev.day) if b in bmap})
    k_jobs = {}
    for b, g in ev.groupby("base"):
        if b in bmap:
            k_jobs[bmap[b]] = month(int(g.day.median()))
    h_events = sorted({(hmap[b], int(dy)) for b, dy in zip(ev.base, ev.day) if b in hmap and int(dy) >= int(pd.Timestamp("2023-05-01", tz="UTC").timestamp() // DAY)})
    h_check = {}
    for b, g in ev.groupby("base"):
        if b in hmap:
            late = g[g.day >= int(pd.Timestamp("2023-05-01", tz="UTC").timestamp() // DAY)]
            if len(late):
                h_check[hmap[b]] = int(late.day.median())
    todo_b = [j for j in b_jobs if not (out / "binance" / f"{j[0]}-{j[1]}.csv").exists() and not (out / "binance" / f"{j[0]}-{j[1]}.missing").exists()]
    todo_k = [s for s in k_jobs if not (out / "binance" / f"klines-{s}.csv").exists() and not (out / "binance" / f"klines-{s}.missing").exists()]
    todo_h = [e for e in h_events if not (out / "hl" / f"{e[0]}-{e[1]}.json").exists()]
    todo_hc = [s for s in h_check if not (out / "hl" / f"candles-{s}.json").exists()]
    plan = {"events": int(len(ev)), "binance_mapped_bases": len(bmap), "hl_mapped_bases": len(hmap),
            "binance_month_files": len(b_jobs), "binance_klines_checks": len(k_jobs),
            "hl_event_windows": len(h_events), "hl_candle_checks": len(h_check),
            "requests_remaining": len(todo_b) + len(todo_k) + len(todo_h) + len(todo_hc)}
    plan["hours_at_1_1s"] = round(plan["requests_remaining"] * 1.1 / 3600, 2)
    (out / "plan.json").write_text(json.dumps({**plan, "bmap": bmap, "hmap": hmap, "klines_months": k_jobs, "hl_check_days": h_check}, indent=1))
    print(json.dumps(plan), flush=True)
    if args.plan:
        return 0

    def save_zip_csv(url: str, dest: Path) -> None:
        r = get(url)
        if r.status_code == 404:
            dest.with_suffix(".missing").write_text("404")
            return
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            dest.write_bytes(z.read(z.namelist()[0]))

    done = 0
    for sym, mo in todo_b:
        save_zip_csv(f"{VISION}/data/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{mo}.zip", out / "binance" / f"{sym}-{mo}.csv")
        done += 1
        if done % 200 == 0:
            print(f"binance funding {done}/{len(todo_b)} requests={COUNT}", flush=True)
    for sym in todo_k:
        save_zip_csv(f"{VISION}/data/futures/um/monthly/klines/{sym}/1d/{sym}-1d-{k_jobs[sym]}.zip", out / "binance" / f"klines-{sym}.csv")
    print(f"binance klines done requests={COUNT}", flush=True)
    for i, (coin, dy) in enumerate(todo_h, 1):
        r = post({"type": "fundingHistory", "coin": coin, "startTime": dy * DAY * 1000 + 1, "endTime": (dy + 1) * DAY * 1000})
        (out / "hl" / f"{coin}-{dy}.json").write_text(r.text if r.status_code == 200 else json.dumps({"http_status": r.status_code}))
        if i % 200 == 0:
            print(f"hl funding {i}/{len(todo_h)} requests={COUNT}", flush=True)
    for coin in todo_hc:
        dy = h_check[coin]
        r = post({"type": "candleSnapshot", "req": {"coin": coin, "interval": "1d", "startTime": (dy - 15) * DAY * 1000, "endTime": (dy + 15) * DAY * 1000}})
        (out / "hl" / f"candles-{coin}.json").write_text(r.text if r.status_code == 200 else json.dumps({"http_status": r.status_code}))
    print(f"done requests={COUNT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
