import React from "react";

/**
 * TokenRow
 *
 * Renders a single token row with:
 * - star + info stack (not clickable for navigation)
 * - symbol / price / %change
 * - row click -> opens Coinbase Advanced Trade for that symbol in a new tab
 *
 * Props:
 *   row: one element from the backend payload.data array
 *   isGainer: boolean, controls gold vs purple hover glow
 */
export default function TokenRow({ row, isGainer }) {
  if (!row) return null;

  const symbolRaw = row.symbol || ""; // e.g. "TAO-USD"
  // We'll show TAO instead of TAO-USD as the main title:
  const baseSymbol = symbolRaw.replace("-USD", "");

  // price
  const price =
    typeof row.current_price === "number"
      ? row.current_price.toFixed(2)
      : row.current_price ?? "-";

  // pick % field: 1-min table gives price_change_percentage_1min,
  // 3-min tables give price_change_percentage_3min
  const pctChangeRaw =
    row.price_change_percentage_1min ??
    row.price_change_percentage_3min ??
    row.price_change_pct ??
    0;

  // format percent with 2 decimals, include sign
  const pctChangeNum = Number(pctChangeRaw) || 0;
  const pctDisplay = pctChangeNum.toFixed(2);

  // hover gradients (literal class strings so Tailwind JIT keeps them)
  const gainHover = "hover:[background-image:var(--row-hover-gain)]";
  const loseHover = "hover:[background-image:var(--row-hover-lose)]";

  const rowHover = isGainer ? gainHover : loseHover;

  const handleRowClick = (e) => {
    // don't navigate if click was on star/info block
    if (e.target.closest("[data-stop]")) return;

    const pair = symbolRaw.toUpperCase(); // already like TAO-USD
    const url = `https://www.coinbase.com/advanced-trade/${pair}`;
    window.open(url, "_blank", "noopener");
  };

  return (
    <tr
      className={`cursor-pointer border-b border-white/5 bg-[rgba(0,0,0,0.2)] bg-no-repeat bg-left-top bg-[length:100%_100%] ${rowHover} transition-colors`}
      onClick={handleRowClick}
    >
      {/* star + info stack */}
      <td className="align-top p-2 pr-3">
        <div
          data-stop
          className="flex flex-col items-center gap-1 text-[10px] leading-none text-white/60"
        >
          <button
            className="px-1 py-[1px] rounded-[3px] bg-white/5 border border-white/20 text-[10px] leading-none"
            onClick={(e) => {
              e.stopPropagation();
              // TODO: add watchlist toggle
              console.log("watch clicked", symbolRaw);
            }}
          >
            ★
          </button>
          <button
            className="px-1 py-[1px] rounded-[3px] bg-white/5 border border-white/20 text-[10px] leading-none"
            onClick={(e) => {
              e.stopPropagation();
              // TODO: open detail panel / modal
              console.log("info clicked", symbolRaw);
            }}
          >
            ⓘ
          </button>
        </div>
      </td>

      {/* symbol / price / pct */}
      <td className="p-2 align-top text-left font-mono text-white text-[12px] leading-tight">
        <div className="flex flex-wrap items-baseline gap-2">
          <div className="text-white font-semibold text-[12px] leading-tight">
            {baseSymbol}
          </div>
          <div className="text-white/40 text-[10px] leading-tight">
            {symbolRaw}
          </div>
        </div>

        <div className="mt-[2px] text-[11px] text-white/70 leading-tight">
          <span className="text-white">${price}</span>{" "}
          <span
            className={
              pctChangeNum >= 0 ? "text-green-400/80" : "text-red-400/80"
            }
          >
            {pctChangeNum >= 0 ? "+" : ""}
            {pctDisplay}%
          </span>
        </div>
      </td>
    </tr>
  );
}
