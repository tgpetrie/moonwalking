import React from "react";
import { useWatchlist } from "../context/WatchlistContext.jsx";

function cleanSymbol(sym) {
  if (!sym) return "";
  return sym.replace(/-(USD|USDT)$/i, "");
}

export default function TokenRow({
  index,
  symbol,
  price,
  prevPrice,
  changePct,
  side = "gain", // "gain" | "loss"
  onInfo,
}) {
  // safe watchlist access
  const wl = (typeof useWatchlist === "function" ? useWatchlist() : null) || {};
  const isWatched = wl.isWatched ? wl.isWatched : () => false;
  const toggle = wl.toggle ? wl.toggle : () => {};

  const s = cleanSymbol(symbol);
  const watched = isWatched(s);

  const hasPrice = typeof price === "number" && !Number.isNaN(price);
  const hasPrev = typeof prevPrice === "number" && !Number.isNaN(prevPrice);
  const hasPct = typeof changePct === "number" && !Number.isNaN(changePct);

  const pctClass = side === "loss" ? "loss-text" : "gain-text";
  const rankClasses =
    side === "loss"
      ? "bg-[rgba(162,75,255,.22)] border border-[#a24bff55]"
      : "bg-[rgba(249,200,107,.22)] border border-[#f9c86b55]";

  const handleRowClick = (e) => {
    if (e.target.closest("[data-stop]")) return;
    if (!s) return;
    window.open(
      `https://www.coinbase.com/advanced-trade/spot/${s.toLowerCase()}-usd`,
      "_blank",
      "noopener,noreferrer"
    );
  };

  return (
    <div
      className="table-row flex items-center gap-4 py-2 pl-1 pr-3 relative"
      onClick={handleRowClick}
    >
      {/* 1) rank + symbol */}
      <div className="flex items-center gap-3 shrink-0 w-[155px]">
        {typeof index === "number" && (
          <span
            className={
              "w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold " +
              rankClasses
            }
          >
            {index + 1}
          </span>
        )}
        <span className="text-sm font-semibold tracking-wide uppercase">
          {s || "—"}
        </span>
      </div>

      {/* 2) price stack */}
      <div className="flex flex-col items-end shrink-0 w-[120px] text-right">
        <span className="text-sm font-semibold text-teal leading-tight">
          {hasPrice ? `$${price.toLocaleString()}` : "—"}
        </span>
        <span className="text-[10px] text-white/40 leading-tight">
          {hasPrev ? `$${prevPrice.toLocaleString()}` : ""}
        </span>
      </div>

      {/* 3) percent */}
      <div className="shrink-0 w-[70px] text-right">
        <span className={`text-sm font-semibold ${pctClass}`}>
          {hasPct ? `${changePct.toFixed(3)}%` : "—"}
        </span>
      </div>

      {/* 4) star / info (vertical) */}
      <div className="flex flex-col items-center gap-1 shrink-0 w-[30px]">
        <button
          data-stop
          onClick={() => toggle(s)}
          className={`text-xs ${
            watched ? "gain-text" : "text-white/35"
          } hover:gain-text`}
        >
          ★
        </button>
        <button
          data-stop
          onClick={() => onInfo?.(s)}
          className="text-white/35 hover:text-white/80 text-[10px]"
        >
          ⓘ
        </button>
      </div>

      {/* bottom glow (full row, not just center) */}
      <div
        className={
          "row-hover-glow " +
          (side === "loss" ? "row-hover-glow-loss" : "row-hover-glow-gain")
        }
      />
    </div>
  );
}
