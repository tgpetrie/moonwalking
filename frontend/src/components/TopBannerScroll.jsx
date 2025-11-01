import React, { useMemo } from "react";
import { useBannerStream } from "../hooks/useBannerStream";

export default function TopBannerScroll() {
  const { priceBanner } = useBannerStream();

  const items = useMemo(() => {
    return (priceBanner || []).map((row, idx) => {
      const symbol = row.symbol || row.ticker || row.asset || "";
      const cleanSymbol = symbol.replace("-USD", "");

      const price =
        row.current_price ??
        row.price ??
        row.last_price ??
        null;

      const pctRaw =
        row.price_change_percentage_1h ??
        row.pct_change_1h ??
        row.percent_change ??
        row.change_pct ??
        0;

      const pctNum = Number(pctRaw) || 0;
      const pctSign = pctNum >= 0 ? "+" : "";
      const pctStr = `${pctSign}${pctNum.toFixed(2)}%`;

      return {
        key: symbol || `row-${idx}`,
        symbol: cleanSymbol,
        pair: symbol.toUpperCase(),
        price,
        pctNum,
        pctStr,
      };
    });
  }, [priceBanner]);

  if (!items.length) return null;

  return (
    <div className="w-full overflow-hidden py-2 text-[11px] font-mono text-white/80 select-none">
      <div className="banner-scroll flex gap-8 whitespace-nowrap">
        {items.map((item) => {
          const pctColorClass =
            item.pctNum >= 0
              ? "text-[#f9c86b] drop-shadow-[0_0_6px_rgba(249,200,107,.6)]"
              : "text-[#a24bff] drop-shadow-[0_0_6px_rgba(162,75,255,.6)]";

          return (
            <div
              key={item.key}
              className="flex items-baseline gap-2 cursor-pointer hover:opacity-90"
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

              <span
                className={`text-[12px] font-bold leading-none ${pctColorClass}`}
              >
                {item.pctStr}
              </span>
            </div>
          );
        })}

        {/* clone for seamless loop */}
        {items.map((item, cloneIdx) => {
          const pctColorClass =
            item.pctNum >= 0
              ? "text-[#f9c86b] drop-shadow-[0_0_6px_rgba(249,200,107,.6)]"
              : "text-[#a24bff] drop-shadow-[0_0_6px_rgba(162,75,255,.6)]";

          return (
            <div
              key={item.key + "-clone-" + cloneIdx}
              className="flex items-baseline gap-2 cursor-pointer hover:opacity-90"
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
              <span
                className={`text-[12px] font-bold leading-none ${pctColorClass}`}
              >
                {item.pctStr}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
