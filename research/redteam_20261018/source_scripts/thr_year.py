"""Replay the sell-side engine over the full hourly archive (about a year) and record
what a long holder saw over the next ~24h, plus BTC's 30-day trend at each point.
Read-only on the candle archive. Writes ~/.moonwalking/analysis/replay_year.sqlite."""
import os, sqlite3, sys, time
import numpy as np
sys.path.insert(0, r"C:\Users\tgpet\Projects\Moonwalking-WeakReads\backend")
from position_levels import compute_levels
from sell_side_intelligence import _top_signal

H, WIN, FWD, STRIDE = 3600, 49, 23, 3
HOME = os.path.expanduser("~/.moonwalking")
cand = sqlite3.connect(f"file:{HOME}/data/candle_archive.sqlite?mode=ro", uri=True)
data, last, buf = {}, None, []
def flush(p, rows): data[p] = np.array(rows, dtype=np.float64)
for p, ts, o, h, l, c, v in cand.execute("select product_id, ts, open, high, low, close, volume from candles "
                                         "where granularity=3600 order by product_id, ts"):
    if p != last and buf: flush(last, buf); buf = []
    last = p; buf.append((ts, o, h, l, c, v))
if buf: flush(last, buf)
print(f"{len(data)} products, {sum(len(a) for a in data.values()):,} hourly candles", flush=True)
btc = {int(t): float(c) for t, c in zip(data["BTC-USD"][:, 0], data["BTC-USD"][:, 4])}

out, t0 = [], time.time()
for prod, a in data.items():
    ts, o, h, l, c, v = a.T
    for i in range(WIN - 1, len(ts) - FWD - 1, STRIDE):
        if ts[i] - ts[i - WIN + 1] != (WIN - 1) * H or ts[i + FWD] - ts[i + 1] != (FWD - 1) * H or ts[i + 1] - ts[i] != H:
            continue
        w = slice(i - WIN + 1, i + 1)
        entry = float(c[i])
        lv = compute_levels(np.column_stack((ts[w], l[w], h[w], o[w], c[w], v[w])).tolist(), entry)
        if not lv or not lv.get("atr"): continue
        top = _top_signal(current_price=entry, support=lv["support"], resistance=lv["resistance"], levels=lv, signal_context={})
        atr = lv["atr"]
        fl, fh, fc = l[i + 1:i + 1 + FWD], h[i + 1:i + 1 + FWD], c[i + 1:i + 1 + FWD]
        t_ = int(ts[i]); b_now, b_then = btc.get(t_), btc.get(t_ - 720 * H)
        out.append((prod, t_, lv["range_position_pct"], lv["momentum_1h_pct"], lv["volume_ratio"], top["status"], top["score"],
                    atr / entry, (fc[-1] - entry) / atr, (entry - fl.min()) / atr, (fh.max() - entry) / atr,
                    1 if entry <= lv["support"] else 0, (b_now / b_then - 1.0) if b_now and b_then else None))
print(f"{len(out):,} coin-hour observations in {time.time()-t0:.0f}s", flush=True)
dst = sqlite3.connect(f"{HOME}/analysis/replay_year.sqlite")
dst.execute("drop table if exists replay")
dst.execute("create table replay (product_id text, ts integer, range_pos real, momentum real, vol_ratio real, status text, score integer, "
            "atr_pct real, ret24 real, mae real, mfe real, at_support integer, btc30 real)")
dst.executemany("insert into replay values (?,?,?,?,?,?,?,?,?,?,?,?,?)", out); dst.commit()
print("saved replay_year.sqlite")
