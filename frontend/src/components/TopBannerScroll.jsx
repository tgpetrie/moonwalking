import React, { useEffect, useRef } from "react";
import { map1hPriceBannerItem, formatPrice, formatPct, colorForDelta } from "../utils/format";

export default function TopBannerScroll({ rows = [], onRefresh }) {
  const items = Array.isArray(rows) ? rows : [];
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

  if (!items || items.length === 0) return null;

  const normalize = (t) => map1hPriceBannerItem(t);

  return (
    <div className="ticker">
      <div className="track" ref={ref}>
        {[...items, ...items].map((t, i) => {
          const it = normalize(t);
          const cls = colorForDelta(it.pct) === "gain" ? "is-gain" : colorForDelta(it.pct) === "loss" ? "is-loss" : "is-neutral";
          return (
            <span key={`${it.symbol}-${i}`} className={cls} style={{ marginRight: 24 }}>
              <b>{it.symbol}</b>&nbsp;
              <span className="price">{formatPrice(it.price)}</span>&nbsp;
              <span>{formatPct(it.pct)}</span>
            </span>
          );
        })}
      </div>
      {onRefresh && (
        <button className="bh-banner-refresh" onClick={onRefresh} style={{ marginLeft: 12 }}>
          Refresh
        </button>
      )}
    </div>
  );
}

