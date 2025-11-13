import React, { useEffect, useRef } from "react";
import { useData } from "../context/useData";
import { fmt } from "../utils/formatters";

export default function TopBannerScroll({ items: propItems = [], loading: propLoading = false }) {
  const { data } = useData();
  const items = propItems.length ? propItems : data?.top_banner_1h ?? [];
  const loading = propLoading;
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

  const normalize = (t) => ({
    symbol: t.symbol || t.ticker || "--",
    price: t.current_price ?? t.price ?? t.last_price ?? null,
    pct: t.price_change_1h ?? t.price_change_percentage_1h ?? t.pct_change_1h ?? t.pct_change ?? 0,
  });

  return (
    <div className="ticker">
      <div className="track" ref={ref}>
        {[...items, ...items].map((t, i) => {
          const it = normalize(t);
          return (
            <span key={`${it.symbol}-${i}`} className={it.pct >= 0 ? "is-gain" : "is-loss"} style={{ marginRight: 24 }}>
              <b>{it.symbol}</b>&nbsp;
              <span className="price">{fmt.price(it.price)}</span>&nbsp;
              <span>{fmt.pct(it.pct)}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

