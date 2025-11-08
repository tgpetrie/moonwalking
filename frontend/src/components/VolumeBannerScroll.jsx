import React, { useEffect, useState } from "react";

function cleanSymbol(sym = "") {
  return sym.replace(/-(USD|USDT)$/i, "");
}

export default function VolumeBannerScroll({ items }) {
  const [data, setData] = useState(items || []);

  useEffect(() => {
    if (items && items.length) return;
    fetch("/api/component/bottom-banner-scroll")
      .then((r) => r.json())
      .then((json) => {
        const arr = json?.items || json || [];
        setData(arr);
      })
      .catch(() => {});
  }, [items]);

  const list = items && items.length ? items : data;
  if (!list.length) return null;

  return (
    <div className="overflow-hidden w-full py-2">
      <div className="banner-scroll flex gap-4">
        {list.map((it, idx) => {
          const volPct =
            it.volume_change_pct ?? it.volume_pct ?? it.change_pct ?? 0;
          const up = volPct >= 0;
          return (
            <span
              key={idx}
              className={`banner-chip ${up ? "banner-chip-gain" : "banner-chip-loss"}`}
            >
              <span>{cleanSymbol(it.symbol)}</span>
              {typeof it.volume_1h === "number" && (
                <span>Vol {Number(it.volume_1h).toLocaleString()}</span>
              )}
              <span>{volPct.toFixed(2)}%</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
