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
    const activePrice = currentPrice ?? token?.price ?? null;
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
        <div className="bh-symbol">{token.symbol}</div>
        {token.base && <div className="bh-name">{token.base}</div>}
      </CellTag>

      {/* 3. Price stack (current / previous) */}
      <CellTag className="bh-cell bh-cell-price">
        <div className={`tr-price-current bh-price-current${priceFlash ? " is-updating" : ""}`}>
          {formatPrice(currentPrice)}
        </div>
        <div className="bh-price-previous">{formatPrice(prevPrice)}</div>
      </CellTag>

      {/* 4. Percent change – main focal point */}
      <CellTag className="bh-cell bh-cell-change">
        <span className={`bh-change ${pctInfo.className}${pctFlash ? " is-updating" : ""}`}>{pctInfo.display}</span>
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
  const [infoOpen, setInfoOpen] = useState(false);
  const toggleInfo = (e) => {
    if (e?.preventDefault) e.preventDefault();
    if (e?.stopPropagation) e.stopPropagation();
    setInfoOpen((v) => !v);
  };

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

  const dataSide =
    side === "gainer" || side === "loser"
      ? side
      : Number.isFinite(changeNum)
        ? (changeNum >= 0 ? "gainer" : "loser")
        : "flat";

  const breatheDelayMs = Number.isFinite(rank) ? (rank * 137) % 9200 : 0;
  const breatheDurationMs = 8800 + (Number.isFinite(rank) ? (rank * 53) % 2400 : 0);
  const cellCadenceMs = 5200 + (Number.isFinite(rank) ? (rank * 83) % 1900 : 0);
  const cellCadenceDelayMs = Number.isFinite(rank) ? (rank * 41) % 620 : 0;
  const cellOrchDelayMs = Number.isFinite(rank) ? (rank * 67) % 980 : 0;
  const rowStyle = {
    ...(pulse ? { "--bh-pulse-delay": `${pulseDelayMs}ms` } : {}),
    "--bh-breathe-delay": `${breatheDelayMs}ms`,
    "--bh-breathe-duration": `${breatheDurationMs}ms`,
    "--bh-cell-cadence": `${cellCadenceMs}ms`,
    "--bh-cell-cadence-delay": `${cellCadenceDelayMs}ms`,
    "--bh-cell-orch-delay": `${cellOrchDelayMs}ms`,
    "--bh-cell-stagger": "120ms",
  };

  const setRabbitHover = (on) => (e) => {
    const row = e.currentTarget;
    const board = row.closest(".board-core");
    if (!board) return;

    if (on) {
      const r = row.getBoundingClientRect();
      const b = board.getBoundingClientRect();

      // These must match the CSS mural bleed values (see index.css)
      const bleedTop = 90;
      const bleedBottom = 180;
      const pad = 6;

      // Calculate position relative to board-core container
      const x = ((r.left + r.width / 2 - b.left) / (b.width || 1)) * 100;
      const y = ((r.top + r.height / 2 - b.top) / (b.height || 1)) * 100;

      // Clip coordinates are in the coordinate space of the mural pseudo-element,
      // which extends above/below the board by bleedTop/bleedBottom.
      const top = Math.max(0, r.top - b.top + bleedTop - pad);
      const left = Math.max(0, r.left - b.left - pad);
      const right = Math.max(0, b.right - r.right - pad);
      const bottom = Math.max(0, b.bottom - r.bottom + bleedBottom - pad);

      board.style.setProperty("--emit-x", `${x}%`);
      board.style.setProperty("--emit-y", `${y}%`);
      board.style.setProperty("--emit-top", `${top}px`);
      board.style.setProperty("--emit-right", `${right}px`);
      board.style.setProperty("--emit-bottom", `${bottom}px`);
      board.style.setProperty("--emit-left", `${left}px`);
      board.setAttribute("data-row-hover", "1");
    } else {
      board.setAttribute("data-row-hover", "0");
    }
  };

  return (
    <>
      <RowTag
        className={`${rowClassName}${pulse ? " is-pulsing" : ""}`}
        style={rowStyle}
        data-side={dataSide}
        role={url ? "link" : undefined}
        tabIndex={url ? 0 : undefined}
        onClick={handleClick}
        onKeyDown={onKeyDown}
        onPointerEnter={setRabbitHover(true)}
        onPointerLeave={setRabbitHover(false)}
        aria-label={url ? `Open ${token?.symbol} on Coinbase` : undefined}
      >
        <span className="bh-row-breathe" aria-hidden="true" />
        {renderCells()}
      </RowTag>

      {infoOpen && (renderAs === "tr" ? (
        <tr className="bh-info-row">
          <td colSpan="99">
            <div className="bh-info-panel" onMouseDown={(e) => e.stopPropagation()} onClick={(e) => e.stopPropagation()}>
              <div className="bh-info-panel__title">{token?.symbol ? token.symbol.toUpperCase() : "—"} Insight</div>
              <div className="bh-info-panel__muted">Hooking real intelligence next.</div>
            </div>
          </td>
        </tr>
      ) : (
        <div className="bh-info-panel" onMouseDown={(e) => e.stopPropagation()} onClick={(e) => e.stopPropagation()}>
          <div className="bh-info-panel__title">{token?.symbol ? token.symbol.toUpperCase() : "—"} Insight</div>
          <div className="bh-info-panel__muted">Hooking real intelligence next.</div>
        </div>
      ))}
    </>
  );
}
