import React, { useEffect, useRef } from "react";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import { formatPrice, formatPercent } from "../utils/formatters.js";

function cleanSymbol(sym) {
  if (!sym) return "";
  return String(sym).replace(/-(USD|USDT)$/i, "");
}

function computePercent(current, previous) {
  const c = Number(current);
  const p = Number(previous);
  if (!Number.isFinite(c) || !Number.isFinite(p) || p === 0) return null;
  // percent value, e.g. 77.9 for +77.9%
  const pct = ((c - p) / p) * 100;
  return pct;
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

  const hasPrice = typeof price === "number" && !Number.isNaN(price);
  const hasPrev = typeof prev === "number" && !Number.isNaN(prev);
  const hasPct = typeof changePct === "number" && !Number.isNaN(changePct);

  // Prefer computing percent from the two prices when available to avoid
  // double-multiplication or trusting a malformed backend value.
  const computedPct = hasPrice && hasPrev ? computePercent(price, prev) : null;
  const finalPct = computedPct != null ? computedPct : changePct;
  const hasFinalPct = typeof finalPct === "number" && !Number.isNaN(finalPct);

  const pctClass = side === "loss" ? "loss-text" : "gain-text";
  const rankClasses =
    side === "loss"
      ? "bg-[rgba(162,75,255,.22)] border border-[#a24bff55]"
      : "bg-[rgba(249,200,107,.22)] border border-[#f9c86b55]";

  const handleRowClick = (e) => {
    // if an inner control has data-stop, don't trigger the row click
    if (e?.target?.closest && e.target.closest("[data-stop]")) return;
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

  const rootRef = useRef(null);
  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    // Prefer scroll-in reveal via IntersectionObserver; fallback to one-shot
    // honor prefers-reduced-motion: skip reveal animations for users who opt out
    if (typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return;
    }
    const fallback = () => {
      el.classList.add("reveal");
      const t = setTimeout(() => el.classList.remove("reveal"), 400);
      return () => clearTimeout(t);
    };

    if (typeof window === 'undefined' || typeof IntersectionObserver === 'undefined') {
      return fallback();
    }

    let done = false;
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!done && entry.isIntersecting) {
          el.classList.add('reveal');
          done = true;
          setTimeout(() => el.classList.remove('reveal'), 420);
          io.disconnect();
        }
      });
    }, { root: null, rootMargin: '0px', threshold: 0.15 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div
      ref={rootRef}
      style={{ "--row-index": index ?? 0 }}
      className={
        "token-row table-row flex items-center gap-4 py-2 pl-1 pr-3 relative " +
        (side === "loss" ? "is-loss" : "is-gain")
      }
      data-state={side}
      onClick={handleRowClick}
    >
      {/* center accent line */}
      <div className="token-row-line" aria-hidden />

      {/* rank */}
      <div className="col-rank w-12 flex items-center justify-start shrink-0">
        {typeof index === "number" && (
          <span
            className={
              "rank-badge token-rank w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold " +
              rankClasses
            }
          >
            {index + 1}
          </span>
        )}
      </div>

      {/* symbol (flexible) */}
      <div className="col-symbol token-symbol-block flex-1 min-w-[90px]">
        <span className="symbol text-sm font-semibold tracking-wide uppercase">{s || "—"}</span>
      </div>

      {/* price (right aligned, fixed width) */}
      <div className="col-price token-price-block w-28 flex flex-col items-end shrink-0 text-right">
        <span className="text-sm font-semibold text-teal token-price-current leading-tight">
          {hasPrice ? formatPrice(price) : "—"}
        </span>
        <span className="text-[10px] text-white/40 token-price-prev leading-tight">{hasPrev ? formatPrice(prev) : ""}</span>
      </div>

      {/* percent (fixed width) */}
      <div className="col-pct token-pct w-20 shrink-0 text-right">
        <span className={`text-sm font-semibold ${pctClass} ${side === "loss" ? "token-pct-loss" : "token-pct-gain"}`}>
          {hasFinalPct ? formatPercent(finalPct, { fromFraction: false, max: 3 }) : "—"}
        </span>
      </div>

      {/* actions (star / info) */}
      <div className="col-actions token-actions w-[36px] flex flex-col items-center gap-1 shrink-0">
        <button
          data-stop
          onClick={() => toggle(s)}
          className={`text-xs ${watched ? "gain-text" : "text-white/35"} hover:gain-text`}
        >
          {watched ? "★" : "☆"}
        </button>
        <button data-stop onClick={() => onInfo?.(s)} className="text-white/35 hover:text-white/80 text-[10px]">
          ⓘ
        </button>
      </div>

      {/* bottom glow (centered, thin) */}
      <div className={"row-hover-glow " + (side === "loss" ? "row-hover-glow-loss" : "row-hover-glow-gain")} />
    </div>
  );
}
