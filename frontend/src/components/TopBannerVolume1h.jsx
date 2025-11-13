import React, { useEffect, useRef } from "react";
import { useData } from "../context/useData";
import { fmt } from "../utils/formatters";

export default function TopBannerVolume1h({ items: propItems = [] }) {
  const { data } = useData();
  const items = propItems.length ? propItems : data?.volume_banner_1h ?? [];
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || items.length === 0) return;
    const anim = el.animate(
      [{ transform: "translateX(0)" }, { transform: "translateX(-50%)" }],
      { duration: 30000, iterations: Infinity, easing: "linear" }
    );
    return () => anim.cancel();
  }, [items?.length]);

  if (!Array.isArray(items) || items.length === 0) {
    return (
      <div className="bh-top-banner">
        <span className="banner-empty">No 1h activity yet.</span>
      </div>
    );
  }

  const normalize = (t) => ({
    symbol: t.symbol || t.ticker || "--",
    volume_now: t.volume_1h ?? t.volume_60m ?? t.volume_last_1h ?? t.volume_1h_usd ?? null,
    volume_pct: t.volume_change_pct_1h ?? t.volume_pct ?? t.volume_change_1h ?? 0,
  });

  return (
    <div className="ticker">
      <div className="track" ref={ref}>
        {[...items, ...items].map((t, i) => {
          const it = normalize(t);
          return (
            <span key={`${it.symbol}-${i}`} className={it.volume_pct >= 0 ? "is-gain" : "is-loss"} style={{ marginRight: 24 }}>
              <b>{it.symbol}</b>&nbsp;
              <span>Vol {fmt.vol(it.volume_now)}</span>&nbsp;
              <span>{fmt.pct(it.volume_pct)}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
