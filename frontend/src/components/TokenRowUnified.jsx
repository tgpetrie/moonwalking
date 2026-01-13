// src/components/TokenRowUnified.jsx
import React, { useEffect, useRef, useState, memo } from "react";
import RowActions from "./tables/RowActions.jsx";
import { formatPct, formatPrice } from "../utils/format.js";
import { baselineOrNull } from "../utils/num.js";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";
import { getAlertConfig, getAlertColor } from "../config/alertConfig";
import "../styles/alerts.css";
import displaySymbol from "../utils/symbolFmt.js";

/**
 * Plain, non-animated BHABIT token row.
 * One layout used across:
 * - 1m gainers
 * - 3m gainers
 * - 3m losers
 * - Watchlist
 */

function TokenRowUnifiedComponent({
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
  activeAlert = null, // Alert object from DataContext.getActiveAlert(symbol)
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
  const [rankFlash, setRankFlash] = useState(false);
  const prevPriceRef = useRef(currentPrice);
  const prevPctRef = useRef(changeNum);
  const prevRankRef = useRef(rank);

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

  useEffect(() => {
    let timer;
    if (prevRankRef.current !== undefined && prevRankRef.current !== rank) {
      setRankFlash(true);
      timer = setTimeout(() => setRankFlash(false), 220);
    }
    prevRankRef.current = rank;
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [rank]);

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
        <div className={rankClassName}>{rank}</div>
      </CellTag>

      {/* 2. Token name */}
      <CellTag className="bh-cell bh-cell-symbol">
        <div className="bh-symbol mw-token-name">{displaySymbol(token.symbol || token.product_id || token.base)}</div>
        {token.base && <div className="bh-name">{displaySymbol(token.base)}</div>}
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
  const showDebug = Boolean(import.meta?.env?.VITE_MW_DEBUG);
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

  const setRabbitHover = (on) => (e) => {
    const row = e.currentTarget;
    if (on) {
      // per-row bloom follow
      const r = row.getBoundingClientRect();
      const x = ((e.clientX - r.left) / r.width) * 100;
      const y = ((e.clientY - r.top) / r.height) * 100;
      row.style.setProperty("--bh-mx", `${x}%`);
      row.style.setProperty("--bh-my", `${y}%`);
    }
    const board = row.closest(".board-core");
    if (!board) return;
    if (on) {
      board.setAttribute("data-row-hover", "1");
    } else {
      board.removeAttribute("data-row-hover");
    }
  };

  // Alert processing
  const [showAlertDetails, setShowAlertDetails] = useState(false);
  const alertType = activeAlert?.alert_type || activeAlert?.type;
  const alertSeverity = (activeAlert?.severity || activeAlert?.severity_lc || "info").toLowerCase();
  const alertConfig = getAlertConfig(alertType);
  const pulseColor = activeAlert ? getAlertColor(activeAlert) : null;
  const [alertFlash, setAlertFlash] = useState(false);
  const prevAlertIdRef = useRef(activeAlert?.id || null);

  useEffect(() => {
    let timer;
    const alertId = activeAlert?.id || null;
    if (alertId && prevAlertIdRef.current !== alertId) {
      setAlertFlash(true);
      timer = setTimeout(() => setAlertFlash(false), 360);
    } else if (!alertId) {
      setAlertFlash(false);
    }
    prevAlertIdRef.current = alertId;
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [activeAlert]);

  // Build dynamic styles for alert pulse
  const rowStyles = {
    ...(pulse ? { "--bh-pulse-delay": `${pulseDelayMs}ms` } : {}),
    ...(pulseColor ? { "--alert-pulse-color": pulseColor } : {}),
  };

  const rankClassName = ["bh-rank", rankFlash ? "is-updating" : ""].filter(Boolean).join(" ");
  const alertBadgeClass = ["alert-badge", alertFlash ? "is-fresh" : ""].filter(Boolean).join(" ");

  return (
    <>
      <RowTag
        className={`${rowClassName} token-row table-row ${pulse ? "is-pulsing" : ""} ${activeAlert ? "has-alert" : ""}`}
        style={Object.keys(rowStyles).length > 0 ? rowStyles : undefined}
        data-side={dataSide}
        data-symbol={symbol ? symbol.toUpperCase() : undefined}
        data-alert-severity={activeAlert ? alertSeverity : undefined}
        role={url ? "link" : undefined}
        tabIndex={url ? 0 : undefined}
        onClick={handleClick}
        onKeyDown={onKeyDown}
        onPointerEnter={(e) => {
          setRabbitHover(true)(e);
          if (activeAlert) setShowAlertDetails(true);
        }}
        onPointerLeave={(e) => {
          setRabbitHover(false)(e);
          if (activeAlert) setShowAlertDetails(false);
        }}
        onMouseMove={setRabbitHover(true)}
        aria-label={url ? `Open ${token?.symbol} on Coinbase` : undefined}
      >
        {renderCells()}

        {/* Alert Badge */}
        {activeAlert && alertConfig && (
          <div className={alertBadgeClass} title={activeAlert.message || activeAlert.title}>
            <span className="alert-badge__icon">{alertConfig.icon}</span>
            <span className="alert-badge__label">{alertConfig.label}</span>
          </div>
        )}

        {showDebug && (
          <div className="token-row-debug">
            <span className="dbg-label">base1m:</span>
            <span className="dbg-val">{prevPrice != null ? formatPrice(prevPrice) : "—"}</span>
            <span className="dbg-label">age:</span>
            <span className="dbg-val">
              {Number.isFinite(token?.baseline_age_s) ? `${token.baseline_age_s}s` : "n/a"}
            </span>
            <span className="dbg-label">pct:</span>
            <span className="dbg-val">
              {Number.isFinite(changeNum) ? formatPct(changeNum, { sign: true }) : "—"}
            </span>
          </div>
        )}
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

const areEqual = (prev, next) => {
  const fields = ["rank", "changeField", "side", "renderAs", "density", "pulse", "pulseDelayMs"];
  for (const key of fields) {
    if (prev[key] !== next[key]) return false;
  }
  if (prev.isWatchlisted !== next.isWatchlisted) return false;
  if (prev.activeAlert?.id !== next.activeAlert?.id) return false;
  if (prev.activeAlert?.severity !== next.activeAlert?.severity) return false;
  if (prev.activeAlert?.alert_type !== next.activeAlert?.alert_type) return false;
  const prevToken = prev.token || {};
  const nextToken = next.token || {};
  const tokenKeys = [
    "symbol",
    "product_id",
    "current_price",
    "price",
    "current",
    "previous_price_1m",
    "previous_price_3m",
    "initial_price_1min",
    "initial_price_3min",
    "price_1m_ago",
    "price_3m_ago",
    prev.changeField || "change_1m",
    next.changeField || "change_1m",
  ];
  for (const key of tokenKeys) {
    if (prevToken[key] !== nextToken[key]) return false;
  }
  return true;
};

export const TokenRowUnified = memo(TokenRowUnifiedComponent, areEqual);
