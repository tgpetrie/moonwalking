import React, { useEffect, useState } from "react";

function cleanSymbol(sym = "") {
  return sym.replace(/-(USD|USDT)$/i, "").toUpperCase();
}

export default function TopBannerScroll({ items }) {
  const [data, setData] = useState(items || []);

  useEffect(() => {
    if (items && items.length) return;
    fetch("/api/component/top-banner-scroll")
      .then((r) => r.json())
      .then((j) => setData(j.items || j || []))
      .catch(() => {});
  }, [items]);

  const list = items && items.length ? items : data;
  if (!list.length) return null;

  return (
    <div className="overflow-hidden w-full py-2 px-4">
      <div className="banner-scroll flex gap-4">
        {list.map((it, idx) => {
          const symbol = cleanSymbol ? cleanSymbol(it.symbol) : it.symbol;
          const pct = it.price_change_1h ?? it.change_pct ?? 0;
          const up = pct >= 0;
          return (
            <span
              key={idx}
              className={`banner-chip ${up ? "banner-chip-gain" : "banner-chip-loss"}`}
            >
              <span>{symbol}</span>
              {typeof it.current_price === "number" && (
                <span>${it.current_price}</span>
              )}
              <span>{pct.toFixed(2)}%</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
