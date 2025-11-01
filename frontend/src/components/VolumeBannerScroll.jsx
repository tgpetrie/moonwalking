import React, { useMemo } from "react";
import { useBannerStream } from "../hooks/useBannerStream";

function formatVolume(v) {
  const num = Number(v);
  if (!Number.isFinite(num) || num <= 0) return null;

  if (num >= 1000000000) {
    return (num / 1000000000).toFixed(2).replace(/\.00$/, "") + "B";
  }
  if (num >= 1000000) {
    return (num / 1000000).toFixed(2).replace(/\.00$/, "") + "M";
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(2).replace(/\.00$/, "") + "K";
  }
  return num.toFixed(0);
}

export default function VolumeBannerScroll() {
  const { volBanner } = useBannerStream();

  const items = useMemo(() => {
    return (volBanner || []).map((row, idx) => {
      const rawSymbol = row.symbol || row.ticker || row.asset || "";
      const cleanSymbol = rawSymbol.replace("-USD", "");
      const pair = rawSymbol.toUpperCase();

      const price =
        row.current_price ??
        row.price ??
        row.last_price ??
        null;

      const volAbs =
        row.volume_1h ??
        row.volume_usd_1h ??
        row.volume_usd ??
        row.volume ??
        row.notional_volume ??
        null;

      const volAbsFormatted = formatVolume(volAbs);

      const volRaw =
        row.volume_change_1h ??
        row.volume_change_pct ??
        row.volume_pct ??
        row.volume_delta ??
        0;

      const volNum = Number(volRaw) || 0;
      const volSign = volNum >= 0 ? "+" : "";
      const volPctStr = `${volSign}${volNum.toFixed(2)}% vol`;

      return {
        key: pair || `vol-${idx}`,
        symbol: cleanSymbol,
        pair,
        price,
        volAbsFormatted,
        volNum,
        volPctStr,
      };
    });
  }, [volBanner]);

  if (!items.length) {
    return null;
  }

  return (
    <div className="w-full overflow-hidden py-2 text-[11px] font-mono text-white/80 select-none">
      <div className="banner-scroll flex gap-8 whitespace-nowrap">
        {items.map((item) => {
          const volColorClass =
            item.volNum >= 0
              ? "text-[#f9c86b] drop-shadow-[0_0_6px_rgba(249,200,107,.6)]"
              : "text-[#a24bff] drop-shadow-[0_0_6px_rgba(162,75,255,.6)]";

          return (
            <button
              key={item.key}
              type="button"
              className="flex items-baseline gap-2 bg-transparent border-0 p-0 text-white/80 hover:opacity-90 focus:outline-none"
              onClick={() => {
                if (!item.pair) return;
                globalThis.open(
                  `https://www.coinbase.com/advanced-trade/${item.pair}`,
                  "_blank",
                  "noopener"
                );
              }}
            >
              <span className="text-white text-[12px] font-semibold tracking-wide leading-none">
                {item.symbol || "--"}
              </span>

              {item.price != null && (
                <span className="text-[#00f5b5] drop-shadow-[0_0_6px_rgba(0,245,181,.6)] font-semibold leading-none text-[12px]">
                  ${Number(item.price).toFixed(2)}
                </span>
              )}

              {item.volAbsFormatted && (
                <span className="text-white/50 text-[11px] leading-none">
                  Vol {item.volAbsFormatted}
                </span>
              )}

              <span
                className={`text-[12px] font-bold leading-none ${volColorClass}`}
              >
                {item.volPctStr}
              </span>
            </button>
          );
        })}

        {items.map((item, cloneIdx) => {
          const volColorClass =
            item.volNum >= 0
              ? "text-[#f9c86b] drop-shadow-[0_0_6px_rgba(249,200,107,.6)]"
              : "text-[#a24bff] drop-shadow-[0_0_6px_rgba(162,75,255,.6)]";

          return (
            <button
              key={item.key + "-clone-" + cloneIdx}
              type="button"
              className="flex items-baseline gap-2 bg-transparent border-0 p-0 text-white/80 hover:opacity-90 focus:outline-none"
              onClick={() => {
                if (!item.pair) return;
                globalThis.open(
                  `https://www.coinbase.com/advanced-trade/${item.pair}`,
                  "_blank",
                  "noopener"
                );
              }}
            >
              <span className="text-white text-[12px] font-semibold tracking-wide leading-none">
                {item.symbol || "--"}
              </span>

              {item.price != null && (
                <span className="text-[#00f5b5] drop-shadow-[0_0_6px_rgba(0,245,181,.6)] font-semibold leading-none text-[12px]">
                  ${Number(item.price).toFixed(2)}
                </span>
              )}

              {item.volAbsFormatted && (
                <span className="text-white/50 text-[11px] leading-none">
                  Vol {item.volAbsFormatted}
                </span>
              )}

              <span
                className={`text-[12px] font-bold leading-none ${volColorClass}`}
              >
                {item.volPctStr}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
