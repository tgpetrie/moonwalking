// src/components/TokenRowUnified.jsx
import React, { useEffect, useRef, useState } from "react";
import RowActions from "./tables/RowActions.jsx";
import { formatPct, formatPrice } from "../utils/format.js";
import { baselineOrNull } from "../utils/num.js";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";

/**
 * Plain, non-animated BHABIT token row.
 * One layout used across:
 * - 1m gainers
 * - 3m gainers
 * - 3m losers
 * - Watchlist
 */

// Badge thresholds (hour-vs-hour volume, velocity 1m, dump 3m)
const BADGE_THRESH = {
  VEL_1M: 1.5,     // percent
  DUMP_3M: -2.0,   // percent
  VOL_1H: 80.0,    // percent change between last full hour vs previous full hour
};

function getBadges(token) {
  const badges = [];

  const ch1m = Number(token.change_1m);
  const ch3m = Number(token.change_3m);
  const vol1h = Number(token.volume_change_1h_pct); // from candle engine

  if (Number.isFinite(ch1m) && ch1m >= BADGE_THRESH.VEL_1M) {
    badges.push({ label: "VEL", tone: "gold" });
  }

  if (Number.isFinite(ch3m) && ch3m <= BADGE_THRESH.DUMP_3M) {
    badges.push({ label: "DUMP", tone: "purple" });
  }

  if (Number.isFinite(vol1h) && vol1h >= BADGE_THRESH.VOL_1H) {
    badges.push({ label: "VOL", tone: "cyan" });
  }

  return badges;
}

const Badge = ({ label, tone }) => (
  <span className={`bh-badge bh-badge--${tone}`}>{label}</span>
);

export function TokenRowUnified({
  token,
  rank,
  changeField, // "change_1m" or "change_3m"
  onToggleWatchlist,
  onInfo,
  isWatchlisted,
  side, // optional: "gainer" | "loser" (preferred; passed from parent tables)
  renderAs = "div",
  density = "normal", // "normal" | "tight"
  pulse = false,
  pulsePrice,
  pulsePct,
  pulseDelayMs = 0,
}) {
  const symbol = token?.symbol;
  const rawChange = token?.[changeField];
  const changeNum = typeof rawChange === "string" ? Number(String(rawChange).replace(/[%+]/g, "")) : Number(rawChange);
  const hasChange = Number.isFinite(changeNum);
  const pctState = !hasChange || changeNum === 0 ? "flat" : changeNum > 0 ? "positive" : "negative";
  const pctInfo = {
    state: pctState,
    display: formatPct(hasChange ? changeNum : undefined, { sign: true }),
    className: pctState === "positive" ? "bh-change-pos" : pctState === "negative" ? "bh-change-neg" : "bh-change-flat",
  };

  const currentPrice = token?.current_price;
  const prevPrice = baselineOrNull(token?.previous_price_1m ?? token?.previous_price_3m ?? token?.previous_price ?? token?.initial_price_1min ?? token?.initial_price_3min ?? token?.price_1m_ago ?? token?.price_3m_ago ?? null);

  const RowTag = renderAs === "tr" ? "tr" : "div";
  const CellTag = renderAs === "tr" ? "td" : "div";
  const rowClass = [
    "bh-row",
    "bh-row-grid",
    density === "tight" ? "bh-row--tight" : "",
    pctInfo.state === "negative" ? "bh-row--loss" : "",
    pctInfo.state === "positive" ? "is-gain" : pctInfo.state === "negative" ? "is-loss" : "is-flat",
  ]
    .filter(Boolean)
    .join(" ");

  const [priceFlash, setPriceFlash] = useState(false);
  const [pctFlash, setPctFlash] = useState(false);
  const prevPriceRef = useRef(currentPrice);
  const prevPctRef = useRef(changeNum);
  const pricePulse = Boolean(pulsePrice ?? pulse);
  const pctPulse = Boolean(pulsePct ?? pulse);
  const priceAnimate = priceFlash || pricePulse;
  const pctAnimate = pctFlash || pctPulse;

  useEffect(() => {
    let cleanup;
    const prev = prevPriceRef.current;
    if (prev !== undefined && prev !== currentPrice) {
      setPriceFlash(true);
      const timer = setTimeout(() => setPriceFlash(false), 420);
      cleanup = () => clearTimeout(timer);
    }
    prevPriceRef.current = currentPrice;
    return cleanup;
  }, [currentPrice]);

  useEffect(() => {
    let cleanup;
    const prev = prevPctRef.current;
    if (prev !== undefined && prev !== changeNum) {
      setPctFlash(true);
      const timer = setTimeout(() => setPctFlash(false), 420);
      cleanup = () => clearTimeout(timer);
    }
    prevPctRef.current = changeNum;
    return cleanup;
  }, [changeNum]);

  const handleToggleStar = () => {
    if (!symbol || typeof onToggleWatchlist !== "function") return;
    // Ensure we pass a valid numeric price
    const activePrice = Number(currentPrice ?? token?.price ?? token?.current);
    if (!Number.isFinite(activePrice) || activePrice <= 0) {
      console.warn(`[TokenRowUnified] Cannot toggle watchlist for ${symbol}: invalid price`, activePrice);
      return;
    }
    onToggleWatchlist(symbol, activePrice);
  };

  const openSentiment = (sym) => {
    const normalized = sym ? String(sym).toUpperCase() : null;
    if (!normalized) return;
    if (typeof onInfo === "function") {
      onInfo(normalized);
    }
    if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
      window.dispatchEvent(new CustomEvent("openInfo", { detail: normalized }));
    }
  };

  const renderCells = () => (
    <>
      {/* 1. Rank circle */}
      <CellTag className="bh-cell bh-cell-rank">
        <div className="bh-rank">{rank}</div>
      </CellTag>

      {/* 2. Token name */}
      <CellTag className="bh-cell bh-cell-symbol">
        <div className="bh-symbol-line">
          <span className="bh-symbol">{token.symbol}</span>
          {(() => {
            const badges = getBadges(token);
            return badges.length > 0 ? (
              <span className="bh-badges" aria-label="status badges">
                {badges.map((b, i) => (
                  <Badge key={`${b.label}-${i}`} label={b.label} tone={b.tone} />
                ))}
              </span>
            ) : null;
          })()}
        </div>
        {token.base && <div className="bh-name">{token.base}</div>}
      </CellTag>

      {/* 3. Price stack (current / previous) */}
      <CellTag className="bh-cell bh-cell-price">
        <div
          className={`tr-price-current bh-price-current${priceAnimate ? " is-updating bh-value-pulse" : ""}`}
          style={priceAnimate ? { "--bh-pulse-delay": `${pulseDelayMs}ms` } : undefined}
        >
          {formatPrice(currentPrice)}
        </div>
        <div className="bh-price-previous">{formatPrice(prevPrice)}</div>
      </CellTag>

      {/* 4. Percent change – main focal point */}
      <CellTag className="bh-cell bh-cell-change">
        <span
          className={`bh-change ${pctInfo.className}${pctAnimate ? " is-updating bh-value-pulse" : ""}`}
          style={pctAnimate ? { "--bh-pulse-delay": `${pulseDelayMs}ms` } : undefined}
        >
          {pctInfo.display}
        </span>
      </CellTag>

      {/* 5. Actions – stacked on far right */}
      <CellTag className="bh-cell bh-cell-actions">
        <RowActions
          starred={Boolean(isWatchlisted)}
          onToggleStar={handleToggleStar}
          onInfoClick={() => openSentiment(symbol || token?.ticker || token?.base || token?.product_id)}
        />
      </CellTag>
    </>
  );

  const url = coinbaseSpotUrl(token || {});
  const rowClassName = [rowClass, url ? "bh-row-clickable" : ""].filter(Boolean).join(" ");
  const open = () => {
    if (!url) return;
    if (window.getSelection?.().toString()) return;
    window.open(url, "_blank", "noopener,noreferrer");
  };
  const handleClick = (e) => {
    if (e?.target?.closest && e.target.closest("a,button")) return;
    open();
  };
  const onKeyDown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      if (e?.target?.closest && e.target.closest("a,button")) return;
      e.preventDefault();
      open();
    }
  };

  // Row click URL (use the same coinbaseSpotUrl utility for consistency)
  const rowUrl = url; // Already computed above via coinbaseSpotUrl(token)

  const onRowClick = (e) => {
    if (!rowUrl) return;
    const t = e.target;
    if (t && (t.closest("button") || t.closest("a"))) return;
    window.open(rowUrl, "_blank", "noopener,noreferrer");
  };

  const onRowKeyDown = (e) => {
    if (!rowUrl) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      window.open(rowUrl, "_blank", "noopener,noreferrer");
    }
  };

  const dataSide =
    side === "gainer" || side === "loser"
      ? side
      : Number.isFinite(changeNum)
        ? (changeNum >= 0 ? "gainer" : "loser")
        : "flat";

  const setRabbitHover = (on) => (e) => {
    const row = e.currentTarget;
    const board = row.closest(".board-core");
    if (!board) return;

    if (on) {
      board.setAttribute("data-row-hover", "1");
      const r = row.getBoundingClientRect();
      const b = board.getBoundingClientRect();

      // Calculate position relative to board-core container
      const x = ((r.left + r.width / 2 - b.left) / b.width) * 100;
      const y = ((r.top + r.height / 2 - b.top) / b.height) * 100;

      board.style.setProperty("--emit-x", `${x}%`);
      board.style.setProperty("--emit-y", `${y}%`);
    } else {
      board.removeAttribute("data-row-hover");
    }
  };

  return (
    <>
      <RowTag
        className={`${rowClassName} token-row table-row`}
        data-side={dataSide}
        role={rowUrl ? "link" : undefined}
        tabIndex={rowUrl ? 0 : undefined}
        onClick={onRowClick}
        onKeyDown={onRowKeyDown}
        onPointerEnter={setRabbitHover(true)}
        onPointerLeave={setRabbitHover(false)}
        aria-label={rowUrl ? `Open ${token?.symbol} on Coinbase` : undefined}
      >
        {renderCells()}
      </RowTag>

    </>
  );
}
