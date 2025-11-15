// frontend/src/components/TopBannerVolume1h.jsx — cleaned single export
import React, { useEffect, useRef } from "react";
import { formatCompact, formatPct, tickerFromSymbol } from "../utils/format";

export default function TopBannerVolume1h({ rows = [], items: propItems = [] }) {
  const items = Array.isArray(propItems) && propItems.length ? propItems : (Array.isArray(rows) ? rows : []);
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || items.length === 0) return;
    const anim = el.animate(
      [{ transform: "translateX(0)" }, { transform: "translateX(-50%)" }],
      { duration: 32000, iterations: Infinity, easing: "linear" }
    );
    return () => anim.cancel();
  }, [items.length]);

  if (!items.length) {
    return (
      <div className="bh-top-banner bh-banner--volume">
        <div className="bh-banner-wrap"><span className="banner-empty">No 1h volume activity yet.</span></div>
      </div>
    );
  }

  const normalize = (t) => ({
    symbol: tickerFromSymbol(t?.symbol ?? t?.ticker ?? ""),
    volume_now: Number(t?.volume_1h ?? t?.volume ?? 0),
    volume_prev: Number(t?.volume_1h_prev ?? t?.volume_prev ?? 0),
    pct: Number(t?.volume_change_percentage_1h ?? t?.volume_change_pct_1h ?? 0),
  });

  return (
    <div className="ticker bh-banner bh-banner--volume">
      <div className="bh-banner-track" ref={ref}>
        {[...items, ...items].map((t, i) => {
          const it = normalize(t);
          const cls = it.pct >= 0 ? "is-gain" : "is-loss";
          return (
            <span key={`${it.symbol}-${i}`} className={`bh-banner-item ${cls}`}>
              <b className="bh-banner-symbol">{it.symbol || "--"}</b>
              <span className="bh-banner-price">{it.volume_now ? formatCompact(it.volume_now) : "--"}</span>
              <span className="bh-banner-pct">{Number.isFinite(it.pct) ? formatPct(it.pct / 100) : "--"}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
