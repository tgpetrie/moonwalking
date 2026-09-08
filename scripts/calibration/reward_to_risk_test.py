import numpy as np
d = np.load("/home/claude/calib/decisions.npz", allow_pickle=True)
D = {k: d[k] for k in d.files}
hours = D["ts"].astype(np.int64); rng = np.random.default_rng(13)
def boot(v, h, n_boot=1200, block=72):
    uh=np.unique(h); idx={x:np.where(h==x)[0] for x in uh}
    nb=max(1,int(np.ceil(len(uh)/block))); out=np.empty(n_boot)
    for b in range(n_boot):
        take=[]
        for s in rng.integers(0,len(uh),nb):
            for j in range(block): take.append(idx[uh[(s+j)%len(uh)]])
        out[b]=v[np.concatenate(take)].mean()
    return out

rp,mom,vr = D["rpos"],D["mom"],D["vratio"]
price,support,resistance,atr = D["price"],D["support"],D["resistance"],D["atr"]
struct=np.where(support<price,support,np.maximum(0,price-atr))
rr=np.where((resistance>price)&((price-struct)>0),(resistance-price)/np.maximum(price-struct,1e-12),np.nan)
volok=np.isfinite(vr)&(vr>=1.5); mom_up=np.isfinite(mom)&(mom>0); mom_dn=np.isfinite(mom)&(mom<0)
at_res,near_res,near_sup = price>=resistance, rp>=85, rp<=15
label=np.full(len(rp),"No entry signal",dtype=object)
label[(at_res|near_res)&volok&mom_up]="Breakout watch"
label[(near_sup&mom_up)&(label=="No entry signal")]="Support reclaim"
label[(mom_dn&(rp<60))&(label=="No entry signal")]="Pullback watch"
label[((at_res|near_res)|(np.isfinite(rr)&(rr<1.0)))&(label=="No entry signal")]="Too extended / poor reward"

# The tool's implicit claim is about REALIZED reward vs risk, not direction.
edge = D["mfe"] / np.maximum(-D["mae"], 1e-9)     # realized MFE:MAE over 24h
edge = np.clip(edge, 0, 50)
be = boot(edge, hours); bm = boot(-D["mae"], hours)
print("="*94)
print("FAIR TEST: REALIZED REWARD-TO-RISK (MFE/|MAE| over 24h), NOT DIRECTION")
print("="*94)
print(f"{'label':<28}{'share':>7}{'MFE/|MAE|':>11}{'vs base':>10}{'95% CI on diff':>22}{'|MAE|%':>9}{'vs base':>10}")
for lab in ["Breakout watch","Support reclaim","Pullback watch","Too extended / poor reward","No entry signal"]:
    s=label==lab
    if s.sum()<500: continue
    e=boot(edge[s],hours[s]); m=boot(-D["mae"][s],hours[s])
    de, dm = e-be, m-bm
    ci=(np.percentile(de,2.5),np.percentile(de,97.5))
    star="  *" if (ci[0]>0 or ci[1]<0) else ""
    print(f"{lab:<28}{s.mean()*100:>6.1f}%{edge[s].mean():>11.3f}{de.mean():>+10.4f}"
          f"{'['+format(ci[0],'+.3f')+', '+format(ci[1],'+.3f')+']':>22}"
          f"{-D['mae'][s].mean():>9.3f}{dm.mean():>+10.3f}{star}")
print(f"{'BASELINE':<28}{'100.0%':>7}{edge.mean():>11.3f}{'':>10}{'':>22}{-D['mae'].mean():>9.3f}")
print("\n  |MAE|% = average worst drawdown over the next 24h. A label that genuinely marks")
print("  a low-risk entry area should show a LOWER |MAE| than baseline even if direction is a coin flip.")
