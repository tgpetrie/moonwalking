"""Measure the shipped level constants against real Coinbase hourly history.

Replicates backend/position_levels.py and backend/sell_side_intelligence.py
exactly, including their simple-mean ATR (NOT Wilder smoothing) and their
volume_ratio definition. No look-ahead: the "live quote" at decision time t is
the OPEN of the first not-yet-completed candle.
"""
import json, glob, os, numpy as np

W = 49            # completed candles in the window (50 fetched, last one incomplete)
ATR_N = 14
H = 24            # forward horizon, hours
rng = np.random.default_rng(7)

def load():
    out = {}
    for p in sorted(glob.glob("/home/claude/calib/candles/*.json")):
        pid = os.path.basename(p)[:-5]
        c = json.load(open(p))
        a = np.array([r for r in c if len(r) >= 6], dtype=float)
        if len(a) < W + H + 50:
            continue
        # [ts, low, high, open, close, volume] ascending
        a = a[np.argsort(a[:, 0])]
        ok = (a[:, 1] > 0) & (a[:, 5] >= 0) & (a[:, 1] <= np.minimum(a[:, 3], a[:, 4])) \
             & (np.maximum(a[:, 3], a[:, 4]) <= a[:, 2])
        out[pid] = a[ok]
    return out

def atr_simple(low, high, close):
    """backend/position_levels.py _atr: simple mean of the last ATR_N true ranges."""
    pc = close[:-1]
    tr = np.maximum.reduce([high[1:] - low[1:], np.abs(high[1:] - pc), np.abs(low[1:] - pc)])
    return tr[-ATR_N:].mean() if len(tr) else np.nan

def run(sym, a):
    ts, low, high, op, close, vol = (a[:, i] for i in range(6))
    n = len(a)
    recs = []
    for t in range(W, n - H):
        wl, wh, wc, wv = low[t-W:t], high[t-W:t], close[t-W:t], vol[t-W:t]
        support, resistance = wl.min(), wh.max()
        atr = atr_simple(wl, wh, wc)
        if not np.isfinite(atr) or atr <= 0 or support <= 0:
            continue
        price = op[t]                       # live quote proxy, no look-ahead
        if price <= 0:
            continue
        span = resistance - support
        rpos = float(np.clip(((price - support) / span) * 100.0, 0, 100)) if span > 0 else 50.0
        band_low = max(0.0, price - atr)
        mom = ((wc[-1] - wc[-2]) / wc[-2] * 100.0) if wc[-2] > 0 else np.nan
        base = np.median(wv[:-1])
        vratio = (wv[-1] / base) if base > 0 else np.nan

        # ---- build_sell_plan, verbatim ----
        structure_support = support if support < price else band_low
        if structure_support is None or structure_support <= 0:
            structure_support = max(price - atr, price * 0.5)
        buf = max(atr * 0.20, price * 0.0015)
        cand_struct, cand_floor = structure_support - buf, price - atr
        trigger = max(min(cand_struct, cand_floor), price * 0.01)
        floor_binds = bool(cand_floor < cand_struct)
        risk_pct = (price - trigger) / price * 100.0

        # ---- forward window ----
        fl, fh, fc = low[t:t+H], high[t:t+H], close[t:t+H]
        fwd_min, fwd_max, fwd_end = fl.min(), fh.max(), fc[-1]
        recs.append((
            ts[t], price, support, resistance, atr, rpos, mom, vratio,
            trigger, float(floor_binds), risk_pct,
            (support - fwd_min) / atr,            # penetration depth below support, ATR units
            float(fwd_min <= support),            # dipped below support
            float(fwd_min <= trigger),            # stop touched
            (fwd_max - price) / price * 100.0,    # MFE %
            (fwd_min - price) / price * 100.0,    # MAE %
            (fwd_end - price) / price * 100.0,    # forward return %
        ))
    if not recs:
        return None
    cols = ("ts price support resistance atr rpos mom vratio trigger floor_binds risk_pct "
            "pen_depth dipped stopped mfe mae fwd").split()
    arr = np.array(recs, dtype=float)
    d = {c: arr[:, i] for i, c in enumerate(cols)}
    d["sym"] = np.array([sym] * len(arr))
    return d

def block_boot_ci(values, hours, stat=np.mean, n_boot=2000, block=72):
    """Stationary block bootstrap over TIME (blocks contain all coins at time t),
    per Politis & Romano; crypto coins in the same hour are ~one observation."""
    uh = np.unique(hours)
    idx_by_hour = {h: np.where(hours == h)[0] for h in uh}
    nb = max(1, int(np.ceil(len(uh) / block)))
    out = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, len(uh), nb)
        take = []
        for s in starts:
            hs = uh[[(s + j) % len(uh) for j in range(block)]]
            for h in hs:
                take.append(idx_by_hour[h])
        sel = np.concatenate(take)
        out[b] = stat(values[sel])
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))

def pct(x, q):
    return float(np.percentile(x, q))

if __name__ == "__main__":
    data = load()
    print(f"symbols loaded: {len(data)}")
    parts = [r for s, a in data.items() if (r := run(s, a)) is not None]
    keys = [k for k in parts[0] if k != "sym"]
    D = {k: np.concatenate([p[k] for p in parts]) for k in keys}
    D["sym"] = np.concatenate([p["sym"] for p in parts])
    hours = D["ts"].astype(np.int64)
    n = len(D["ts"])
    span_days = (D["ts"].max() - D["ts"].min()) / 86400
    print(f"decision points: {n:,} across {len(parts)} symbols, {span_days:.0f} days\n")

    def line(label, val, ci=None, suffix=""):
        c = f"   95% CI [{ci[0]:.3f}, {ci[1]:.3f}]" if ci else ""
        print(f"{label:<52} {val:>9.3f}{suffix}{c}")

    print("=" * 88)
    print("1. DOES THE 'STRUCTURAL' STOP ACTUALLY USE THE STRUCTURE?")
    print("=" * 88)
    fb = D["floor_binds"]
    line("P(price-1*ATR floor binds, overall)", fb.mean(), block_boot_ci(fb, hours))
    near = D["rpos"] <= 15
    if near.sum() > 50:
        line("P(floor binds | range_position <= 15)", fb[near].mean(),
             block_boot_ci(fb[near], hours[near]))
    print(f"{'near-support states':<52} {near.mean()*100:>9.2f}% of all")

    print("\n" + "=" * 88)
    print("2. IS THE 0.20*ATR BUFFER A BUFFER?  (real penetrations below the 49h low)")
    print("=" * 88)
    dip = D["dipped"] == 1
    line("P(price dips below 49h support within 24h)", dip.mean(), block_boot_ci(D["dipped"], hours))
    pd_ = D["pen_depth"][dip]
    for q in (25, 50, 75, 90, 95):
        line(f"  penetration depth q{q} (ATR units)", pct(pd_, q))
    for thr in (0.10, 0.20, 0.50, 1.00, 2.00):
        mark = "   <-- shipped buffer" if abs(thr - 0.20) < 1e-9 else ""
        line(f"  P(depth <= {thr:.2f} ATR | dipped)", (pd_ <= thr).mean(), suffix=mark)

    print("\n" + "=" * 88)
    print("3. ARE THE 15 / 85 RANGE FLAGS SELECTIVE?")
    print("=" * 88)
    lo, hi = (D["rpos"] <= 15), (D["rpos"] >= 85)
    line("P(range_position <= 15)  'near support'", lo.mean(), block_boot_ci(lo.astype(float), hours))
    line("P(range_position >= 85)  'near resistance'", hi.mean(), block_boot_ci(hi.astype(float), hours))
    line("P(either flag fires)", (lo | hi).mean())
    print(f"{'  empirical 5th pctile of range_position':<52} {pct(D['rpos'],5):>9.2f}")
    print(f"{'  empirical 95th pctile of range_position':<52} {pct(D['rpos'],95):>9.2f}")

    print("\n" + "=" * 88)
    print("4. THE 1.5x VOLUME GATE")
    print("=" * 88)
    v = D["vratio"]; ok = np.isfinite(v)
    line("P(volume_ratio >= 1.5)", (v[ok] >= 1.5).mean(), block_boot_ci((v[ok]>=1.5).astype(float), hours[ok]))
    print(f"{'  volume_ratio percentile of the 1.5 cut':<52} "
          f"{(v[ok] < 1.5).mean()*100:>9.2f}")
    for q in (50, 75, 90, 95, 99):
        line(f"  volume_ratio q{q}", pct(v[ok], q))

    print("\n" + "=" * 88)
    print("5. STOP OUTCOMES OVER 24h")
    print("=" * 88)
    st = D["stopped"]
    line("P(suggested stop trigger touched within 24h)", st.mean(), block_boot_ci(st, hours))
    hit = st == 1
    if hit.sum() > 50:
        recov = (D["fwd"][hit] > 0).mean()
        line("  P(price back above entry at 24h | stopped)", recov,
             block_boot_ci((D["fwd"][hit] > 0).astype(float), hours[hit]))
    line("median risk to trigger (%)", pct(D["risk_pct"], 50))
    line("  q90 risk to trigger (%)", pct(D["risk_pct"], 90))

    np.savez_compressed("/home/claude/calib/decisions.npz", **{k: D[k] for k in keys},
                        sym=D["sym"])
    print("\nsaved /home/claude/calib/decisions.npz")
