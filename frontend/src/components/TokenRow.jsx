import React, { useEffect } from "react";

export default function TokenRow(props) {
  const {
    rank,
    symbol,
    current_price,
    previous_price, // optional, gray
    price_change_percentage_1min,
    price_change_percentage_3min,
    isGainer = true,
    onInfo,
  } = props;

  // Defensive: ticker-only symbol (trim "-USD")
  const ticker = (symbol || "").replace(/-USD$/i, "") || symbol;

  // debug so we know we're on the right build
  useEffect(() => {
    console.log("[TokenRow FINAL v-rightControls+priceColor]", {
      symbol: ticker,
      rank,
      isGainer,
      pct1: price_change_percentage_1min,
      pct3: price_change_percentage_3min,
    });
  }, [
    ticker,
    rank,
    isGainer,
    price_change_percentage_1min,
    price_change_percentage_3min,
  ]);

  //
  // % CHANGE
  //
  const pctRaw =
    price_change_percentage_1min ??
    price_change_percentage_3min ??
    0;

  const pctStr = (() => {
    const val = Number(pctRaw);
    if (Number.isNaN(val)) return "0.00%";
    const sign = val >= 0 ? "+" : "";
    return `${sign}${val.toFixed(2)}%`;
  })();

  // orange for gainers, purple for losers
  const pctColorClass = isGainer
    ? "text-[#f9c86b] drop-shadow-[0_0_6px_rgba(249,200,107,.6)]"
    : "text-[#a24bff] drop-shadow-[0_0_6px_rgba(162,75,255,.6)]";

  //
  // PRICE COLORS
  // teal/green glow for live price (this is your 'current price' color)
  //
  const livePriceClass =
    "text-[#00f5b5] drop-shadow-[0_0_6px_rgba(0,245,181,.6)] font-semibold leading-none text-[12px]";

  const prevPriceClass =
    "text-white/40 text-[10px] leading-none";

  //
  // ROW HOVER BG (we assume you already defined --row-hover-gain / --row-hover-lose in index.css)
  //
  const hoverBg = isGainer
    ? "hover:[background-image:var(--row-hover-gain)]"
    : "hover:[background-image:var(--row-hover-lose)]";

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
      className={`cursor-pointer text-[12px] font-mono text-white/80 leading-tight bg-black/0 ${hoverBg} border-b border-white/[0.05] align-top`}
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
      <td className="py-2 px-2 text-left align-top w-full">
        {/* top line: SYMBOL + (current/prev price block) */}
        <div className="flex flex-row flex-wrap items-baseline gap-2 leading-tight">
          <div className="text-white text-[12px] font-semibold tracking-wide leading-none">
            {ticker || "--"}
          </div>

          <div className="flex flex-col leading-tight">
            <div className={livePriceClass}>
              ${Number(current_price ?? 0).toFixed(2)}
            </div>
            {previous_price != null && (
              <div className={prevPriceClass}>
                ${Number(previous_price).toFixed(2)}
              </div>
            )}
          </div>
        </div>

        {/* BIG % line below */}
        <div
          className={`mt-1 text-[12px] font-bold leading-none ${pctColorClass}`}
        >
          {pctStr}
        </div>
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
