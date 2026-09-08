import numpy as np
d = np.load("/home/claude/calib/decisions.npz", allow_pickle=True)
D = {k: d[k] for k in d.files}
hours = D["ts"].astype(np.int64)
rng = np.random.default_rng(11)

def boot(v, h, n_boot=1500, block=72):
    """Stationary block bootstrap over time; a block holds all coins at those hours."""
    uh = np.unique(h); idx = {x: np.where(h == x)[0] for x in uh}
    nb = max(1, int(np.ceil(len(uh)/block))); out = np.empty(n_boot)
    for b in range(n_boot):
        take = []
        for s in rng.integers(0, len(uh), nb):
            for j in range(block):
                take.append(idx[uh[(s+j) % len(uh)]])
        sel = np.concatenate(take)
        out[b] = v[sel].mean()
    return out

rp, mom, vr = D["rpos"], D["mom"], D["vratio"]
price, support, resistance, atr = D["price"], D["support"], D["resistance"], D["atr"]
struct = np.where(support < price, support, np.maximum(0, price - atr))
risk_amt = price - struct
rr = np.where((resistance > price) & (risk_amt > 0), (resistance - price)/np.maximum(risk_amt,1e-12), np.nan)
volok = np.isfinite(vr) & (vr >= 1.5)
mom_up, mom_dn = np.isfinite(mom) & (mom > 0), np.isfinite(mom) & (mom < 0)
at_res, near_res, near_sup = price >= resistance, rp >= 85, rp <= 15

print("="*94)
print("DEAD BRANCH CHECK")
print("="*94)
print(f"  P(price <= structure_support)  [the shipped 'structure broken' test] : "
      f"{(price <= struct).mean():.6f}")
print(f"  P(price <= support)            [the honest test]                      : "
      f"{(price <= support).mean():.6f}")
print("  structure_support is defined as `support if support < price else band_low`,")
print("  so it is below price by construction and the test can never be true.")

label = np.full(len(rp), "No entry signal", dtype=object)
label[(at_res|near_res) & volok & mom_up] = "Breakout watch"
label[(near_sup & mom_up) & (label=="No entry signal")] = "Support reclaim"
label[(mom_dn & (rp<60)) & (label=="No entry signal")] = "Pullback watch"
label[((at_res|near_res)|(np.isfinite(rr)&(rr<1.0))) & (label=="No entry signal")] = "Too extended / poor reward"

base_up = (D["fwd"]>0).astype(float); base_ret = D["fwd"]
bu, br = boot(base_up, hours), boot(base_ret, hours)
print("\n" + "="*94)
print("DO THE ENTRY LABELS SEPARATE 24h OUTCOMES?  (time-blocked bootstrap, 40 coins)")
print("="*94)
print(f"{'label':<28}{'share':>7}{'P(up)':>8}{'vs base':>9}{'95% CI on diff':>22}{'mean fwd%':>11}{'95% CI':>20}")
for lab in ["Breakout watch","Support reclaim","Pullback watch","Too extended / poor reward","No entry signal"]:
    s = label == lab
    if s.sum() < 500: continue
    u, r = boot((D["fwd"][s]>0).astype(float), hours[s]), boot(D["fwd"][s], hours[s])
    du, dr = u - bu, r - br
    ciu = (np.percentile(du,2.5), np.percentile(du,97.5))
    cir = (np.percentile(dr,2.5), np.percentile(dr,97.5))
    star = "  *" if (ciu[0] > 0 or ciu[1] < 0) else ""
    print(f"{lab:<28}{s.mean()*100:>6.1f}%{(D['fwd'][s]>0).mean():>8.3f}"
          f"{du.mean():>+9.4f}{'['+format(ciu[0],'+.4f')+', '+format(ciu[1],'+.4f')+']':>22}"
          f"{D['fwd'][s].mean():>+11.3f}"
          f"{'['+format(cir[0],'+.3f')+', '+format(cir[1],'+.3f')+']':>20}{star}")
print(f"{'BASELINE':<28}{'100.0%':>7}{base_up.mean():>8.3f}{'':>9}{'':>22}{base_ret.mean():>+11.3f}")
print("\n  * = 95% CI on the difference from baseline excludes zero.")
print("  'vs base' and its CI are differences in P(price up at 24h) against all decision points.")

print("\n" + "="*94)
print("VOLUME GATE: DOES 1.5x SEPARATE, AND WOULD A PERCENTILE CUT DO BETTER?")
print("="*94)
ok = np.isfinite(vr)
print(f"{'gate':<26}{'fires':>8}{'P(up)':>8}{'diff vs base':>14}{'95% CI on diff':>24}")
for name, mask in [("volume_ratio >= 1.5", ok & (vr>=1.5)),
                   ("top 30% of window", ok & (vr>=np.nanpercentile(vr,70))),
                   ("top 10% of window", ok & (vr>=np.nanpercentile(vr,90))),
                   ("top 5% of window",  ok & (vr>=np.nanpercentile(vr,95)))]:
    u = boot((D["fwd"][mask]>0).astype(float), hours[mask]); du = u - bu
    ci = (np.percentile(du,2.5), np.percentile(du,97.5))
    star = "  *" if (ci[0] > 0 or ci[1] < 0) else ""
    print(f"{name:<26}{mask.mean()*100:>7.1f}%{(D['fwd'][mask]>0).mean():>8.3f}{du.mean():>+14.4f}"
          f"{'['+format(ci[0],'+.4f')+', '+format(ci[1],'+.4f')+']':>24}{star}")
