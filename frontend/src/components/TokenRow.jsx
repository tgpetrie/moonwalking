import React from "react";

// One row in any table. Handles:
// - hover gradient (gold for gainers, purple for losers)
// - ★ / ⓘ buttons that don't trigger navigation
// - clicking the row opens Coinbase Advanced Trade for SYMBOL-USD
export default function TokenRow({
  symbol,
  current_price,
  price_change_percentage_3min,
  price_change_percentage_1min,
  trend_direction,
  trend_streak,
  rank,
  isGainer = true,
}) {
  const pct3 =
    price_change_percentage_3min ?? price_change_percentage_1min ?? 0;

  const pctStr = (() => {
    const val = Number(pct3);
    if (Number.isNaN(val)) return "0.00%";
    const sign = val >= 0 ? "+" : "";
    return `${sign}${val.toFixed(2)}%`;
  })();

  // tailwind classes for the hover background using the CSS vars we defined in index.css
  const gainHover = "hover:[background-image:var(--row-hover-gain)]";
  const loseHover = "hover:[background-image:var(--row-hover-lose)]";
  const hoverClass = isGainer ? gainHover : loseHover;

  // pick text color for % change
  const pctColor =
    pct3 >= 0 ? "text-[#f9c86b] drop-shadow-[0_0_6px_rgba(249,200,107,.6)]" :
    "text-[#a24bff] drop-shadow-[0_0_6px_rgba(162,75,255,.6)]";

  return (
    <tr
      className={`cursor-pointer text-[12px] font-mono text-white/80 leading-tight bg-black/0 ${hoverClass}`}
      onClick={(e) => {
        // if click hit a child with data-stop, don't navigate
        if (e.target.closest("[data-stop]")) return;

        const base = "https://www.coinbase.com/advanced-trade";
        // incoming symbols are like "TAO-USD", "SOL-USD", etc.
        // Coinbase Advanced expects SYMBOL-USD
        const pair = (symbol || "").toUpperCase();
        window.open(`${base}/${pair}`, "_blank", "noopener");
      }}
    >
      {/* left cell: star + info stacked */}
      <td className="align-top py-2 pr-3">
        <div
          className="flex flex-col items-center gap-1 text-[10px] text-white/60"
          data-stop
        >
          <button
            className="leading-none hover:text-yellow-300"
            onClick={(e) => {
              e.stopPropagation();
              console.log("watch clicked", symbol);
            }}
          >
            ★
          </button>
          <button
            className="leading-none hover:text-purple-300"
            onClick={(e) => {
              e.stopPropagation();
              console.log("info clicked", symbol);
            }}
          >
            ⓘ
          </button>
        </div>
      </td>

      {/* symbol / price / pct */}
      <td className="py-2 pr-4 text-left">
        <div className="flex items-baseline gap-2">
          <div className="text-white text-[12px] font-semibold tracking-wide">
            {symbol?.replace("-USD", "") || "--"}
          </div>
          <div className="text-white/50 text-[10px]">${Number(current_price).toFixed(2)}</div>
        </div>

        <div className={`text-[11px] font-medium ${pctColor}`}>{pctStr}</div>

        <div className="text-[10px] text-white/30">
          {trend_direction || "flat"} • streak {trend_streak ?? 0} • #{rank ?? "--"}
        </div>
      </td>
    </tr>
  );
}
