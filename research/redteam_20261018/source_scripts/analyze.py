import os, sqlite3
import numpy as np

c = sqlite3.connect(os.path.expanduser("~/.moonwalking/analysis/recon.sqlite"))
cols = [r[1] for r in c.execute("pragma table_info(recon)")]
rows = c.execute("select * from recon").fetchall()
A = {k: np.array([r[i] for r in rows], dtype=object if k in ("kind", "product_id", "label", "direction") else float)
     for i, k in enumerate(cols)}
kind = A["kind"]; N = len(rows)

# de-duplicate signals: one per (product, direction, label, 4h block)
seen, keep = set(), np.zeros(N, bool)
for i in range(N):
    if kind[i] == "base": keep[i] = True; continue
    k = (A["product_id"][i], A["direction"][i], A["label"][i], int(A["ts"][i]) // 14400)
    if k not in seen: seen.add(k); keep[i] = True
sig = (kind == "sig"); base = (kind == "base")
print(f"signals usable {int(sig.sum()):,} -> de-duplicated {int((sig & keep).sum()):,} | baseline {int(base.sum()):,}")
print(f"ambiguous candles (target and stop in same hour, scored as stop): 1:1 {A['amb11'][sig].mean():.1%} | 2:1 {A['amb21'][sig].mean():.1%}\n")

def stats(m):
    n = int(m.sum())
    if n == 0: return None
    r = A["netR21"][m]; r11 = A["netR11"][m]
    return dict(n=n, t21=(A["res21"][m] == 1).mean(), s21=(A["res21"][m] == -1).mean(),
                R21=r.mean(), se=r.std() / np.sqrt(n), R11=r11.mean(),
                mfe=np.median(A["mfe"][m]), mae=np.median(A["mae"][m]), r24=A["r24"][m].mean(),
                atr=np.median(A["atr_pct"][m]) * 100)

def line(name, st, ref=None):
    if st is None: print(f"{name:34} (none)"); return
    d = ""
    if ref is not None:
        diff = st["R21"] - ref["R21"]; se = np.hypot(st["se"], ref["se"])
        d = f" vsBase {diff:+.3f}R (z={diff/se:+.1f})"
    print(f"{name:34}{st['n']:>8,} tgt2:1 {st['t21']:5.1%} stop {st['s21']:5.1%} netR(2:1) {st['R21']:+.3f}±{st['se']:.3f} "
          f"netR(1:1) {st['R11']:+.3f} MFE {st['mfe']:.2f} MAE {st['mae']:.2f} r24 {st['r24']:+.2f}ATR{d}")

print("== BASELINE: any coin, any hour (entry at hour boundary), net of 0.2% cost. R = 1 ATR stop. ==")
bs = {}
for dr in ("up", "down"):
    bs[dr] = stats(base & (A["direction"] == dr)); line(f"baseline {dr}", bs[dr])
print("\n== SIGNALS by label x direction (de-duplicated, n>=400), vs baseline of the same direction ==")
combos = {}
for lab, dr in set(zip(A["label"][sig & keep], A["direction"][sig & keep])):
    m = sig & keep & (A["label"] == lab) & (A["direction"] == dr)
    if m.sum() >= 400: combos[(lab, dr)] = m
for (lab, dr), m in sorted(combos.items(), key=lambda kv: -kv[1].sum()):
    line(f"{str(lab)[:26]} {dr}", stats(m), bs[dr])
print()
line("ALL signals up", stats(sig & keep & (A["direction"] == "up")), bs["up"])
line("ALL signals down", stats(sig & keep & (A["direction"] == "down")), bs["down"])

print("\n== EXTENSION: how far price already ran from its 14h base, in ATR, in the trade direction ==")
edges = [(-99, 0), (0, 1), (1, 2), (2, 3), (3, 99)]
for name, sel in (("signals", sig & keep), ("baseline", base)):
    for lo, hi in edges:
        m = sel & (A["ext"] >= lo) & (A["ext"] < hi)
        line(f"{name} ext [{lo if lo>-99 else '<0'},{hi if hi<99 else '+'})", stats(m))
print("\n== MARKET CONTEXT: BTC 4h move in the trade's direction ==")
for name, sel in (("signals", sig & keep), ("baseline", base)):
    for lab, lo, hi in (("BTC against (<-0.5%)", -9, -0.005), ("BTC flat", -0.005, 0.005), ("BTC with (>+0.5%)", 0.005, 9)):
        m = sel & (A["btc4h"] >= lo) & (A["btc4h"] < hi)
        line(f"{name} {lab}", stats(m))

print("\n== STABILITY: first 60% of time vs last 40% (de-duplicated signals, net R at 2:1) ==")
tcut = np.quantile(A["ts"][sig], 0.6)
for name, m0 in (("ALL up", sig & keep & (A["direction"] == "up")), ("ALL down", sig & keep & (A["direction"] == "down")),
                 ("baseline up", base & (A["direction"] == "up")), ("baseline down", base & (A["direction"] == "down"))):
    a = stats(m0 & (A["ts"] < tcut)); b = stats(m0 & (A["ts"] >= tcut))
    print(f"{name:16} first60%: R {a['R21']:+.3f} (n={a['n']:,})   last40%: R {b['R21']:+.3f} (n={b['n']:,})")
for (lab, dr), m in sorted(combos.items(), key=lambda kv: -kv[1].sum())[:6]:
    a = stats(m & (A["ts"] < tcut)); b = stats(m & (A["ts"] >= tcut))
    if a and b: print(f"{str(lab)[:22]+' '+dr:26} first60%: R {a['R21']:+.3f} (n={a['n']:,})   last40%: R {b['R21']:+.3f} (n={b['n']:,})")
