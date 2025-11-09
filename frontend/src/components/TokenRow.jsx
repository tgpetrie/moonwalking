import React from "react";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import { formatPrice, formatPercent } from "../utils/formatters.js";

function cleanSymbol(sym) {
  if (!sym) return "";
  return String(sym).replace(/-(USD|USDT)$/i, "");
}

// Single, authoritative TokenRow implementation. Supports legacy prop shapes,
// defensive watchlist access, single-formatting helpers, and stops event
// propagation on inner controls.
export default function TokenRow(props) {
  const {
    index: propIndex,
    rank,
    symbol,
    price: propPrice,
    currentPrice,
    current_price,
    prevPrice,
    previousPrice,
    previous_price,
    changePct: propChange,
    priceChange1min,
    priceChange3min,
    price_change_percentage_1min,
    price_change_percentage_3min,
    side: propSide,
    isGainer,
    onInfo,
  } = props;

  const index =
    typeof propIndex === "number" ? propIndex : typeof rank === "number" ? rank - 1 : undefined;

  const price =
    typeof propPrice === "number"
      ? propPrice
      : typeof currentPrice === "number"
      ? currentPrice
      : typeof current_price === "number"
      ? current_price
      : undefined;

  const prev =
    typeof prevPrice === "number"
      ? prevPrice
      : typeof previousPrice === "number"
      ? previousPrice
      : typeof previous_price === "number"
      ? previous_price
      : undefined;

  const changePct =
    typeof propChange === "number"
      ? propChange
      : typeof priceChange1min === "number"
      ? priceChange1min
      : typeof price_change_percentage_1min === "number"
      ? price_change_percentage_1min
      : typeof priceChange3min === "number"
      ? priceChange3min
      : typeof price_change_percentage_3min === "number"
      ? price_change_percentage_3min
      : undefined;

  const side =
    propSide ||
    (typeof isGainer === "boolean"
      ? isGainer
        ? "gain"
        : "loss"
      : typeof changePct === "number"
      ? changePct < 0
        ? "loss"
        : "gain"
      : "gain");

  // defensive watchlist
  let wl = null;
  try {
    wl = useWatchlist();
  } catch {
    wl = null;
  }
  const toggle = wl?.toggle ?? (() => {});
  const isWatched = wl?.isWatched ?? (() => false);

  const s = cleanSymbol(symbol);
  const watched = isWatched(s);

  const pctClass = side === "loss" ? "loss-text" : "gain-text";
  const rankClasses =
    side === "loss"
      ? "bg-[rgba(162,75,255,.22)] border border-[#a24bff55]"
      : "bg-[rgba(249,200,107,.22)] border border-[#f9c86b55]";

  const handleRowClick = (e) => {
    // if an inner control has data-stop, don't trigger the row click
    if (e.target && e.target.closest && e.target.closest("[data-stop]")) return;
    if (!s) return;
    try {
      window.open(
        `https://www.coinbase.com/advanced-trade/spot/${s.toLowerCase()}-usd`,
        "_blank",
        "noopener,noreferrer"
      );
    } catch (err) {}
  };

  const hasPrice = typeof price === "number" && !Number.isNaN(price);
  const hasPrev = typeof prev === "number" && !Number.isNaN(prev);
  const hasPct = typeof changePct === "number" && !Number.isNaN(changePct);

  return (
    <div
      className={`table-row flex items-center gap-4 py-2 pl-1 pr-3 relative ${
        side === "loss" ? "is-loss" : "is-gain"
      }`}
      data-state={side}
      onClick={handleRowClick}
    >
      <div className="flex items-center gap-3 shrink-0">
        {typeof index === "number" && (
          <span className={`rank-badge w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold ${rankClasses}`}>
            {index + 1}
          </span>
        )}
        <span className="symbol text-sm font-semibold tracking-wide uppercase">{s || "—"}</span>
      </div>

      <div className="price flex flex-col items-end shrink-0 text-right">
        <span className="text-sm font-semibold text-teal leading-tight">{hasPrice ? formatPrice(price) : "—"}</span>
        <span className="text-[10px] text-white/40 leading-tight">{hasPrev ? formatPrice(prev) : ""}</span>
      </div>

      <div className="pct shrink-0 text-right">
        <span className={`text-sm font-semibold ${pctClass}`}>{hasPct ? formatPercent(changePct) : "—"}</span>
      </div>

      <div className="flex flex-col items-center gap-1 shrink-0 w-[30px]">
        <button data-stop onClick={(e) => { e.stopPropagation(); toggle(s); }} className={`text-xs ${watched ? "gain-text" : "text-white/35"} hover:gain-text`}>★</button>
        <button data-stop onClick={(e) => { e.stopPropagation(); onInfo?.(s); }} className="text-white/35 hover:text-white/80 text-[10px]">ⓘ</button>
      </div>

      <div className={`row-hover-glow ${side === "loss" ? "row-hover-glow-loss" : "row-hover-glow-gain"}`} />
    </div>
  );
}
import React from "react";
import { useWatchlist } from "../context/WatchlistContext.jsx";

function cleanSymbol(sym) {
  if (!sym) return "";
  return String(sym).replace(/-(USD|USDT)$/i, "");
}

export default function TokenRow(props) {
  // accept multiple prop name shapes from legacy and new feeds
  const {
    index: propIndex,
    rank,
    symbol,
    price: propPrice,
    currentPrice,
    current_price,
    prevPrice,
    previousPrice,
    previous_price,
    changePct: propChange,
    priceChange1min,
    priceChange3min,
    price_change_percentage_1min,
    price_change_percentage_3min,
    side: propSide,
    isGainer,
    onInfo,
  } = props;

  // normalize index: the UI expects to show index+1 when index is zero-based.
  // legacy callers sometimes pass `rank` 1-based. If rank is present use rank-1.
  const index =
    typeof propIndex === "number" ? propIndex : typeof rank === "number" ? rank - 1 : undefined;

  // normalize prices
  const price =
    typeof propPrice === "number"
      ? propPrice
      : typeof currentPrice === "number"
      ? currentPrice
      : typeof current_price === "number"
      ? current_price
      : undefined;
  const prev =
    typeof prevPrice === "number"
      ? prevPrice
      : typeof previousPrice === "number"
      ? previousPrice
      : typeof previous_price === "number"
      ? previous_price
      : undefined;

  // normalize percent: prefer explicit changePct, then 1min then 3min
  const changePct =
    typeof propChange === "number"
      ? propChange
      : typeof priceChange1min === "number"
      ? priceChange1min
      : typeof price_change_percentage_1min === "number"
      ? price_change_percentage_1min
      : typeof priceChange3min === "number"
      ? priceChange3min
      : typeof price_change_percentage_3min === "number"
      ? price_change_percentage_3min
      : undefined;

  // normalize side: explicit prop, then isGainer flag, then infer from changePct
  const side =
    propSide ||
    (typeof isGainer === "boolean"
      ? isGainer
        ? "gain"
        : "loss"
      : typeof changePct === "number"
      ? changePct < 0
        ? "loss"
        : "gain"
      : "gain");

  // safe watchlist access (defensive when context missing)
  const wl = typeof useWatchlist === "function" ? useWatchlist() : null;
  const isWatched = wl && typeof wl.isWatched === "function" ? wl.isWatched : () => false;
  const toggle = wl && typeof wl.toggle === "function" ? wl.toggle : () => {};

  const s = cleanSymbol(symbol);
  const watched = isWatched(s);

  const hasPrice = typeof price === "number" && !Number.isNaN(price);
  const hasPrev = typeof prev === "number" && !Number.isNaN(prev);
  const hasPct = typeof changePct === "number" && !Number.isNaN(changePct);

  const pctClass = side === "loss" ? "loss-text" : "gain-text";
  const rankClasses =
    side === "loss"
      ? "bg-[rgba(162,75,255,.22)] border border-[#a24bff55]"
      : "bg-[rgba(249,200,107,.22)] border border-[#f9c86b55]";

  const handleRowClick = (e) => {
    if (e.target.closest("[data-stop]")) return;
    if (!s) return;
    try {
      window.open(
        `https://www.coinbase.com/advanced-trade/spot/${s.toLowerCase()}-usd`,
        "_blank",
        "noopener,noreferrer"
      );
    } catch (err) {
      // ignore in SSR / test envs
    }
  };

  return (
    <div
      className={
        "table-row flex items-center gap-4 py-2 pl-1 pr-3 relative " +
        (side === "loss" ? "is-loss" : "is-gain")
      }
      data-state={side}
      onClick={handleRowClick}
    >
      {/* 1) rank + symbol */}
      <div className="flex items-center gap-3 shrink-0">
        {typeof index === "number" && (
          <span
            className={
              "rank-badge w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold " +
              rankClasses
            }
          >
            {index + 1}
          </span>
        )}
        <span className="symbol text-sm font-semibold tracking-wide uppercase">
          {s || "—"}
        </span>
      </div>

      {/* 2) price stack */}
      <div className="price flex flex-col items-end shrink-0 text-right">
        <span className="text-sm font-semibold text-teal leading-tight">
          {hasPrice ? `$${price.toLocaleString()}` : "—"}
        </span>
        <span className="text-[10px] text-white/40 leading-tight">
          {hasPrev ? `$${prev.toLocaleString()}` : ""}
        </span>
      </div>

      {/* 3) percent */}
      <div className="pct shrink-0 text-right">
        <span className={`text-sm font-semibold ${pctClass}`}>
          {hasPct ? `${changePct.toFixed(3)}%` : "—"}
        </span>
      </div>

      {/* 4) star / info (vertical) */}
      <div className="flex flex-col items-center gap-1 shrink-0 w-[30px]">
        <button
          data-stop
          onClick={() => toggle(s)}
          className={`text-xs ${watched ? "gain-text" : "text-white/35"} hover:gain-text`}
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

      {/* bottom glow (centered, thin) */}
      <div
        className={
          "row-hover-glow " + (side === "loss" ? "row-hover-glow-loss" : "row-hover-glow-gain")
        }
      />
    </div>
  );
}
