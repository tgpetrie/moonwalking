import React, { useEffect } from "react";
// local copy of formatSymbol to avoid build-time resolution issues
function formatSymbol(raw) {
  if (!raw) return "";
  try {
    return String(raw).replace(/-USD$/i, "");
  } catch (e) {
    return String(raw || "");
  }
}
import { formatPercentage } from "../utils/formatters.js";

export default function TokenRow(props) {
  const {
    rank,
    symbol,
    // prefer canonical adapter fields when present (camelCase)
    currentPrice,
    previousPrice,
    priceChange1min,
    priceChange3min,
    // legacy snake_case (back-compat)
    current_price,
    previous_price, // optional, gray
    price_change_percentage_1min,
    price_change_percentage_3min,
    isGainer = true,
    onInfo,
    // optional override: when true, prefer showing volume (abbreviated)
    volume,
    displayVolumeAsPrice = false,
  } = props;

  // Defensive: ticker-only symbol (trim "-USD") via shared util
  const ticker = formatSymbol(symbol) || symbol || "--";

  // debug so we know we're on the right build
  // compute effective values preferring canonical fields from adapters
  const effectiveCurrent = typeof currentPrice === 'number' ? currentPrice : current_price;
  const effectivePrevious = typeof previousPrice === 'number' ? previousPrice : previous_price;
  const effectivePct1 = typeof priceChange1min === 'number' ? priceChange1min : price_change_percentage_1min;
  const effectivePct3 = typeof priceChange3min === 'number' ? priceChange3min : price_change_percentage_3min;

  useEffect(() => {
    console.log("[TokenRow FINAL v-rightControls+priceColor]", {
      symbol: ticker,
      rank,
      isGainer,
      pct1: effectivePct1,
      pct3: effectivePct3,
    });
  }, [ticker, rank, isGainer, effectivePct1, effectivePct3]);

  //
  // % CHANGE
  //
  const pctRaw = effectivePct1 ?? effectivePct3 ?? 0;

  const pctStr = (() => {
    const val = Number(pctRaw);
    if (Number.isNaN(val)) return "0.00%";
    // Backend historically returns percent as a raw percentage (e.g. 0.23 -> 0.23%)
    // formatPercentage expects fraction=false to treat the number as percent value.
    return formatPercentage(val, { sign: true, fraction: false });
  })();

  // orange for gainers, purple for losers
  // prefer utility classes defined in index.css
  const pctColorClass = isGainer ? "gain-text" : "loss-text";

  //
  // PRICE COLORS
  // teal/green glow for live price (this is your 'current price' color)
  //
  const livePriceClass =
    "text-[#00f5b5] drop-shadow-[0_0_6px_rgba(0,245,181,.6)] font-semibold leading-none text-[12px]";

  const prevPriceClass = "text-white/40 text-[10px] leading-none";

  const fmtPrice = (n) => {
    const num = Number(n);
    if (!Number.isFinite(num)) return "--";
    if (num >= 1) return `$${num.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
    return `$${num.toPrecision(4)}`;
  };

  const fmtVolume = (v) => {
    const n = Number(v || 0);
    if (!Number.isFinite(n) || n === 0) return '--';
    const abs = Math.abs(n);
    const sign = n < 0 ? '-' : '';
    if (abs >= 1e12) return sign + (abs / 1e12).toFixed(2).replace(/\.0+$/,'') + 'T';
    if (abs >= 1e9)  return sign + (abs / 1e9).toFixed(2).replace(/\.0+$/,'') + 'B';
    if (abs >= 1e6)  return sign + (abs / 1e6).toFixed(2).replace(/\.0+$/,'') + 'M';
    if (abs >= 1e3)  return sign + (abs / 1e3).toFixed(1).replace(/\.0+$/,'') + 'k';
    return sign + String(abs.toFixed(0));
  };

  //
  // ROW HOVER BG (we assume you already defined --row-hover-gain / --row-hover-lose in index.css)
  //
  // hover handled by .row-hover-line in CSS

  //
  // CLICK ANYWHERE BUT STAR/INFO -> open Coinbase advanced trade for that pair
  //
  const handleRowClick = (e) => {
    if (e.target.closest("[data-stop]")) return;
    const pair = (symbol || "").toUpperCase(); // e.g. TAO-USD
    const url = `https://www.coinbase.com/advanced-trade/${pair}`;
    globalThis.open(url, "_blank", "noopener");
  };

  return (
    <tr
      dir="ltr"
      className={`cursor-pointer text-[12px] font-mono text-white/80 leading-tight bg-black/0 border-b border-white/[0.05] align-top`}
      onClick={handleRowClick}
    >
      {/* LEFT: rank bubble */}
      <td className="align-top py-2 pr-3 w-[28px] shrink-0 text-center">
        <div
          className="flex flex-col items-center text-[10px] font-bold text-white/90 select-none"
          data-stop
        >
          <div
            className={
              isGainer
                ? "w-[20px] h-[20px] rounded-full flex items-center justify-center text-[10px] bg-black border border-[#f9c86b66] text-[#f9c86b] shadow-[0_0_12px_rgba(249,200,107,.4)]"
                : "w-[20px] h-[20px] rounded-full flex items-center justify-center text-[10px] bg-black border border-[#a24bff66] text-[#a24bff] shadow-[0_0_12px_rgba(162,75,255,.4)]"
            }
          >
            {rank ?? "•"}
          </div>
        </div>
      </td>

      {/* MID: symbol / prices / % change */}
  <td className="py-2 px-2 text-left align-top w-full relative">
        {/* top line: SYMBOL + (current/prev price block) */}
        <div className="flex flex-row flex-wrap items-baseline gap-2 leading-tight">
          <div className="text-white text-[12px] font-semibold tracking-wide leading-none">
            {ticker || "--"}
          </div>

          <div className="flex flex-col leading-tight">
            <div className={livePriceClass}>{displayVolumeAsPrice ? fmtVolume(volume) : fmtPrice(effectiveCurrent)}</div>
            {effectivePrevious != null && (
              <div className={prevPriceClass}>{fmtPrice(effectivePrevious)}</div>
            )}
          </div>
        </div>

        {/* BIG % line below */}
        <div className={`mt-1 text-[12px] font-bold leading-none ${pctColorClass}`}>
          {pctStr}
        </div>

        {/* faint gradient line, appears on row hover (styled in index.css) */}
        <div className="row-hover-line absolute inset-x-0 bottom-0 h-px opacity-0 transition-opacity duration-150 pointer-events-none" aria-hidden />
      </td>

      {/* RIGHT: ★ / ⓘ vertical stack */}
      <td className="align-top py-2 pl-3 w-[28px] shrink-0 text-center">
        <div
          className="flex flex-col items-center gap-1 text-[10px] text-white/60"
          data-stop
        >
          {/* star */}
          <button
            className="leading-none hover:text-[#f9c86b]"
            onClick={(e) => {
              e.stopPropagation();
              console.log("watch clicked", ticker);
            }}
          >
            ★
          </button>

          {/* info */}
          <button
            type="button"
            aria-label="Symbol info"
            className="leading-none hover:text-[#a24bff]"
            onClick={(e) => {
              e.stopPropagation();
              onInfo?.(ticker);
            }}
          >
            ⓘ
          </button>

          {/* sentiment badge disabled until pipeline returns */}
          {false && (
            <span className="ml-1 sentiment-badge neutral">NEUTRAL</span>
          )}
        </div>
      </td>
    </tr>
  );
}
