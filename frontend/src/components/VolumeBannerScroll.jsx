import React, { useEffect, useState } from "react";
import { formatCompact, formatPct } from "../utils/format";

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
  if (!list.length) {
    return (
      <div className="bh-banner-wrap">
        <div className="ticker bh-banner bh-banner--volume">
          <div className="bh-banner-track">
            <span className="banner-empty">No 1h volume activity yet.</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bh-banner-wrap">
      <div className="ticker bh-banner bh-banner--volume">
        <div className="bh-banner-track">
          {list.map((it, idx) => {
            const symbol = cleanSymbol(it.symbol);
            const volumeNow =
              typeof it.volume_1h === "number" ? it.volume_1h : it.volume;
            const rawPct =
              it.volume_change_pct ??
              it.volume_pct ??
              it.change_pct ??
              it.volume_change_percentage_1h ??
              0;
            const pct = Number(rawPct) || 0;
            const pctClass =
              pct > 0
                ? "bh-banner-chip__pct bh-banner-chip__pct--gain"
                : pct < 0
                ? "bh-banner-chip__pct bh-banner-chip__pct--loss"
                : "bh-banner-chip__pct";

            return (
              <span key={idx} className="bh-banner-chip">
                <span className="bh-banner-chip__symbol">{symbol}</span>
                <span className="bh-banner-chip__price">
                  {volumeNow != null ? `Vol ${formatCompact(volumeNow)}` : "Vol —"}
                </span>
                <span className={pctClass}>
                  {pct === 0
                    ? "0.0%"
                    : formatPct(pct, { sign: true })}
                </span>
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
