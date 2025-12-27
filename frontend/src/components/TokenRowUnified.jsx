// src/components/TokenRowUnified.jsx
import React, { useEffect, useRef, useState } from "react";
import RowActions from "./tables/RowActions.jsx";
import { formatPct, formatPrice } from "../utils/format.js";
import { baselineOrNull } from "../utils/num.js";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";
import { useIntelligence } from "../context/IntelligenceContext";

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
  className = "",
  cellClassMap = {},
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

  let intel = null;
  try { intel = useIntelligence(); } catch (e) { intel = null; }

  const [infoOpen, setInfoOpen] = useState(false);

  const symbolUpper = String(token?.symbol || "").toUpperCase();
  const report = intel && symbolUpper ? intel.reports?.[symbolUpper] : null;

  const tvSymbol = symbolUpper ? `${symbolUpper}USD` : "";
  const tradingViewUrl = tvSymbol
    ? `https://www.tradingview.com/chart/?symbol=COINBASE%3A${encodeURIComponent(tvSymbol)}`
    : "";

  const toggleInfo = (e) => {
    if (e?.preventDefault) e.preventDefault();
    if (e?.stopPropagation) e.stopPropagation();
    setInfoOpen((v) => {
      const next = !v;
      if (next && intel?.refresh) intel.refresh();
      return next;
    });
  };

  const closeInfo = (e) => {
    if (e?.preventDefault) e.preventDefault();
    if (e?.stopPropagation) e.stopPropagation();
    setInfoOpen(false);
  };

  const RowTag = renderAs === "tr" ? "tr" : "div";
  const CellTag = renderAs === "tr" ? "td" : "div";
  const baseRowClasses = [
    "bh-row",
    "bh-row-grid",
    density === "tight" ? "bh-row--tight" : "",
    pctInfo.state === "negative" ? "bh-row--loss" : "",
    pctInfo.state === "positive" ? "is-gain" : pctInfo.state === "negative" ? "is-loss" : "is-flat",
    className,
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

  const getCellClass = (slot, fallback = "bh-cell") => {
    const baseMap = {
      rank: "bh-cell bh-cell--rank",
      symbol: "bh-cell bh-cell--symbol",
      name: "bh-cell bh-cell--name",
      price: "bh-cell bh-cell--price",
      pct: "bh-cell bh-cell--pct",
      actions: "bh-cell bh-cell--actions",
    };
    const base = baseMap[slot] || fallback;
    const override = cellClassMap?.[slot];
    return override ? `${base} ${override}` : base;
  };

  const renderCells = () => (
    <>
      <CellTag className={getCellClass("rank")}>
        <div className="bh-rank">{rank}</div>
      </CellTag>
      <CellTag className={getCellClass("symbol")}>
        <div className="bh-symbol">{token.symbol}</div>
      </CellTag>
      <CellTag className={getCellClass("name")}>
        <div className="bh-name">{token.base || ""}</div>
      </CellTag>
      <CellTag className={getCellClass("price")}>
        <div className={`tr-price-current bh-price-current${priceFlash ? " is-updating" : ""}`}>
          {formatPrice(currentPrice)}
        </div>
        {prevPrice != null && (
          <div className="tr-price-prev bh-price-prev">
            {formatPrice(prevPrice)}
          </div>
        )}
      </CellTag>
      <CellTag className={getCellClass("pct")}>
        <span className={[
          "bh-change",
          "bh-pct",
          pctInfo.className,
          pctInfo.state === "positive" ? "token-pct-gain" : "",
          pctInfo.state === "negative" ? "token-pct-loss" : "",
          pctFlash ? "is-updating" : "",
        ].filter(Boolean).join(" ")}>{pctInfo.display}</span>
      </CellTag>
      <CellTag className={getCellClass("actions")}>
        <RowActions
          starred={Boolean(isWatchlisted)}
          onToggleStar={handleToggleStar}
          onInfoClick={toggleInfo}
        />
      </CellTag>
    </>
  );

  const url = coinbaseSpotUrl(token || {});
  const rowClassName = [baseRowClasses, url ? "bh-row-clickable" : ""].filter(Boolean).join(" ");
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

  // ===== Hover-driven rabbit glow vars (rabbit-space, not row-space) =====
  const getRabbitEl = () =>
    document.querySelector(".bh-bunny-layer") ||
    document.querySelector(".rabbit-bg");

  const setGlowVars = (e) => {
    const root = document.documentElement;
    const rabbit = getRabbitEl();
    if (!rabbit) return;

    const rr = rabbit.getBoundingClientRect();
    const x = Math.max(0, Math.min(rr.width, e.clientX - rr.left));
    const y = Math.max(0, Math.min(rr.height, e.clientY - rr.top));

    root.style.setProperty("--bh-glow-x", `${x}px`);
    root.style.setProperty("--bh-glow-y", `${y}px`);
  };

  const onEnter = (e) => {
    const root = document.documentElement;
    root.setAttribute("data-hover-side", dataSide || "neutral");
    root.style.setProperty("--bh-glow-a", "1");
    setGlowVars(e);
  };

  const onMove = (e) => {
    setGlowVars(e);
  };

  const onLeave = () => {
    const root = document.documentElement;
    root.style.setProperty("--bh-glow-a", "0");
    root.removeAttribute("data-hover-side");
  };

  return (
    <>
      <RowTag
        className={`${rowClassName} token-row table-row ${pulse ? "is-pulsing" : ""}`}
        style={pulse ? { "--bh-pulse-delay": `${pulseDelayMs}ms` } : undefined}
        data-side={dataSide}
        role={url ? "link" : undefined}
        tabIndex={url ? 0 : undefined}
        onClick={handleClick}
        onKeyDown={onKeyDown}
        aria-label={url ? `Open ${token?.symbol} on Coinbase` : undefined}
        onMouseEnter={onEnter}
        onMouseMove={onMove}
        onMouseLeave={onLeave}
      >
        {renderCells()}
      </RowTag>

      {infoOpen && (
        <div className="bh-info-panel" onClick={(e) => e.stopPropagation()}>
          <div className="bh-info-panel__top">
            <div className="bh-info-panel__title">
              <span className="bh-info-panel__sym">{symbolUpper || "—"}</span>
              <span className="bh-info-panel__tag">INSIGHT</span>
            </div>
            <button type="button" className="bh-info-panel__close" onClick={closeInfo} aria-label="Close info">×</button>
          </div>

          <div className="bh-info-panel__body">
            {intel && intel.loading && !report ? (
              <div className="bh-info-panel__muted">Loading intelligence…</div>
            ) : null}

            {!intel ? (
              <div className="bh-info-panel__muted">
                Intelligence provider not mounted. Chart link is still available.
              </div>
            ) : null}

            {report ? (
              <>
                <div className="bh-info-panel__line">
                  <span className="k">Narrative</span>
                  <span className="v">{report.narrative || "—"}</span>
                </div>

                <div className="bh-info-panel__grid">
                  <div className="cell">
                    <div className="k">FinBERT</div>
                    <div className="v">{report?.metrics?.finbert_label ?? "—"} ({String(report?.metrics?.finbert_score ?? "—")})</div>
                  </div>
                  <div className="cell">
                    <div className="k">Fear/Greed</div>
                    <div className="v">{String(report?.metrics?.fear_greed_index ?? "—")}</div>
                  </div>
                  <div className="cell">
                    <div className="k">Social Vol</div>
                    <div className="v">{String(report?.metrics?.social_volume ?? "—")}</div>
                  </div>
                  <div className="cell">
                    <div className="k">Confidence</div>
                    <div className="v">{String(report?.metrics?.confidence ?? "—")}</div>
                  </div>
                </div>

                <div className="bh-info-panel__line">
                  <span className="k">Freshness</span>
                  <span className="v">{report.freshness || "—"}</span>
                </div>
              </>
            ) : (
              <div className="bh-info-panel__muted">No intelligence report available yet for this symbol.</div>
            )}

            <div className="bh-info-panel__links">
              {tradingViewUrl ? (
                <a className="bh-info-panel__link" href={tradingViewUrl} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
                  Open TradingView chart
                </a>
              ) : null}
            </div>

            {intel && intel.lastError ? (
              <div className="bh-info-panel__err">Intel error: {intel.lastError}</div>
            ) : null}
          </div>
        </div>
      )}
    </>
  );
}
