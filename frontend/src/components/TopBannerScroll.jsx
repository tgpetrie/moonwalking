import React, { useMemo } from "react";
import { useBannerStream } from "../hooks/useBannerStream";
import { formatSymbol } from "../lib/format";
import { normalizeBannerRow } from "../lib/adapters";

export default function TopBannerScroll({ items: incoming }) {
  const { priceBanner } = useBannerStream();

  const items = useMemo(() => {
    const source = Array.isArray(incoming) && incoming.length ? incoming : (priceBanner || []);
    return source.map((row, idx) => {
      const n = normalizeBannerRow(row);
      const symbol = n.symbol || row.symbol || row.ticker || row.asset || "";
      const cleanSymbol = formatSymbol(symbol) || symbol || "--";
      const price = n.currentPrice ?? row.current_price ?? row.price ?? row.last_price ?? null;
      const pctNum = Number(n.priceChange1h ?? 0) || 0;
      const pctSign = pctNum >= 0 ? "+" : "";
      const pctStr = `${pctSign}${pctNum.toFixed(2)}%`;

      return {
        key: symbol || `row-${idx}`,
        symbol: cleanSymbol,
        pair: (symbol || "").toUpperCase(),
        price,
        pctNum,
        pctStr,
      };
    });
  }, [priceBanner, incoming]);

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
