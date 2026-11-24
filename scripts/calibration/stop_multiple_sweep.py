"""Stop-multiple sweep + does the entry classifier separate anything?"""
import numpy as np, json
d = np.load("/home/claude/calib/decisions.npz", allow_pickle=True)
D = {k: d[k] for k in d.files}
hours = D["ts"].astype(np.int64)
rng = np.random.default_rng(11)

def boot_ci(v, h, stat=np.mean, n_boot=1500, block=72):
    uh = np.unique(h); idx = {x: np.where(h == x)[0] for x in uh}
    nb = max(1, int(np.ceil(len(uh)/block))); out = np.empty(n_boot)
    for b in range(n_boot):
        take = []
        for s in rng.integers(0, len(uh), nb):
            for j in range(block):
                take.append(idx[uh[(s+j) % len(uh)]])
        out[b] = stat(np.concatenate(take))
    return float(np.percentile(out,2.5)), float(np.percentile(out,97.5))

print("="*92)
print("6. WHY THE FLOOR BINDS LESS THAN A RANDOM WALK PREDICTS")
print("="*92)
ratio = (D["resistance"] - D["support"]) / D["atr"]
for q in (10,50,90):
    print(f"  real (49h range)/ATR  q{q:<3}                            {np.percentile(ratio,q):>8.2f}")
print("  random-walk null said                             q10 5.29  median 7.66  q90 11.48")
print("  -> real crypto ATR is large relative to the range it spans (fat hourly tails),")
print("     so price sits closer to the 49h low in ATR units than a random walk implies.")

print("\n" + "="*92)
print("7. STOP-MULTIPLE SWEEP   stop = support - k*ATR   (floor removed, structural only)")
print("="*92)
print(f"{'k':>5} {'risk% med':>10} {'P(stopped 24h)':>15} {'P(dip absorbed)':>16} {'P(up@24h|stopped)':>19}")
dip = D["dipped"] == 1
for k in (0.20, 0.50, 0.75, 1.00, 1.50, 2.00, 3.00):
    trig = D["support"] - k*D["atr"]
    risk = (D["price"] - trig)/D["price"]*100
    valid = trig > 0
    stopped = (D["price"] + D["mae"]/100*D["price"]) <= trig    # MAE low vs trigger
    absorbed = (D["pen_depth"][dip] <= k).mean()
    up = (D["fwd"][stopped & valid] > 0).mean() if (stopped & valid).sum() > 50 else np.nan
    print(f"{k:>5.2f} {np.median(risk[valid]):>10.2f} {stopped[valid].mean():>15.3f} "
          f"{absorbed:>16.3f} {up:>19.3f}")
base_up = (D["fwd"] > 0).mean()
print(f"\n  baseline P(price above entry at 24h, unconditional) = {base_up:.3f}"
      f"   95% CI {boot_ci((D['fwd']>0).astype(float), hours)}")
print("  read: 'P(up@24h|stopped)' below the baseline means the stop exited ahead of")
print("        further weakness rather than cutting a recovery short.")

print("\n" + "="*92)
print("8. DOES THE ENTRY CLASSIFIER SEPARATE FORWARD OUTCOMES?  (labels replicated)")
print("="*92)
rp, mom, vr = D["rpos"], D["mom"], D["vratio"]
price, support, resistance = D["price"], D["support"], D["resistance"]
atr = D["atr"]
struct = np.where(support < price, support, np.maximum(0, price - atr))
risk_amt = price - struct
rr = np.where((resistance > price) & (risk_amt > 0), (resistance - price)/np.maximum(risk_amt,1e-12), np.nan)
volok = np.isfinite(vr) & (vr >= 1.5)
mom_up, mom_dn = np.isfinite(mom) & (mom > 0), np.isfinite(mom) & (mom < 0)
at_res, near_res, near_sup = price >= resistance, rp >= 85, rp <= 15
broken = price <= struct

label = np.full(len(rp), "No entry signal", dtype=object)
label[(~broken) & ((at_res|near_res) & volok & mom_up)] = "Breakout watch"
m = (~broken) & (near_sup & mom_up) & (label == "No entry signal")
label[m] = "Support reclaim"
m = (~broken) & (mom_dn & (rp < 60)) & (label == "No entry signal")
label[m] = "Pullback watch (no signal ctx)"
m = (~broken) & ((at_res|near_res) | (np.isfinite(rr) & (rr < 1.0))) & (label == "No entry signal")
label[m] = "Too extended / poor reward"
label[broken] = "Invalidated (structure)"

print(f"{'label':<32} {'share':>7} {'n':>8} {'mean fwd%':>10} {'P(up)':>7} {'95% CI on P(up)':>22}")
for lab in ["Breakout watch","Support reclaim","Pullback watch (no signal ctx)",
            "Too extended / poor reward","No entry signal","Invalidated (structure)"]:
    s = label == lab
    if s.sum() < 200:
        print(f"{lab:<32} {s.mean()*100:>6.2f}% {s.sum():>8} (too few)"); continue
    up = (D["fwd"][s] > 0).astype(float)
    lo, hi = boot_ci(up, hours[s])
    print(f"{lab:<32} {s.mean()*100:>6.2f}% {s.sum():>8} {D['fwd'][s].mean():>10.3f} "
          f"{up.mean():>7.3f} {'['+format(lo,'.3f')+', '+format(hi,'.3f')+']':>22}")
print(f"\n  {'BASELINE (all decision points)':<32} {'100.0%':>7} {len(rp):>8} "
      f"{D['fwd'].mean():>10.3f} {base_up:>7.3f}")
print("\n  CIs are time-blocked (72h stationary blocks spanning all 40 coins at once),")
print("  because coins in the same hour are ~one observation, not 40.")
