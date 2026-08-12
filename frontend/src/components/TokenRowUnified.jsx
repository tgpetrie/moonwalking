// src/components/TokenRowUnified.jsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import RowActions from "./tables/RowActions.jsx";
import { formatPct, formatPrice } from "../utils/format.js";
import { baselineOrNull } from "../utils/num.js";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";
import { deriveRowCue } from "../utils/rowCue.js";
import { getMoveStatus } from "../utils/moveStatus.js";

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
  rowIndex,
  changeField, // "change_1m" or "change_3m"
  onToggleWatchlist,
  onInfo,
  isWatchlisted,
  side, // optional: "gainer" | "loser" (preferred; passed from parent tables)
  renderAs = "div",
  density = "normal", // "normal" | "tight"
  pulse = false,
  pulsePrice = false,
  pulsePct = false,
  pulseDelayMs = 0,
  activeAlert = null,
  recentAlerts = [],
  rankDelta = 0,
}) {
  const symbol = token?.symbol;
  const rawChange = token?.[changeField];
  const changeNum = typeof rawChange === "string" ? Number(String(rawChange).replace(/[%+]/g, "")) : Number(rawChange);
  const hasChange = rawChange !== null && rawChange !== undefined && Number.isFinite(changeNum);
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
  const rowCue = useMemo(
    () =>
      deriveRowCue({
        token,
        changeField,
        activeAlert,
        recentAlerts,
        rankDelta,
        isWatchlisted,
      }),
    [token, changeField, activeAlert, recentAlerts, rankDelta, isWatchlisted]
  );
  const primaryCue =
    rowCue?.primary || (rowCue?.display?.key && rowCue.display.key !== "normal" ? rowCue.display : null);
  const secondaryCue = rowCue?.secondary || null;
  const persistenceCue = rowCue?.persistence || null;
  const rowClass = [
    "bh-row",
    "bh-row-grid",
    "mw-row",
    "mw-hover-hook",
    density === "tight" ? "bh-row--tight" : "",
    pctInfo.state === "negative" ? "bh-row--loss" : "",
    pctInfo.state === "positive" ? "is-gain" : pctInfo.state === "negative" ? "is-loss" : "is-flat",
    rowCue?.intensity === "high" ? "bh-row--hot" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const [priceFlash, setPriceFlash] = useState(false);
  const [pctFlash, setPctFlash] = useState(false);
  const [eventPulse, setEventPulse] = useState(false);
  const prevPriceRef = useRef(currentPrice);
  const prevPctRef = useRef(changeNum);
  const prevCueKeyRef = useRef(rowCue?.triggerKey || "");

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
    if (!pulse && !pulsePrice && !pulsePct) return undefined;
    setEventPulse(true);
    const timer = setTimeout(() => setEventPulse(false), 520);
    return () => clearTimeout(timer);
  }, [pulse, pulsePrice, pulsePct]);

  useEffect(() => {
    const nextKey = rowCue?.triggerKey || "";
    if (!nextKey || prevCueKeyRef.current === nextKey) return;
    prevCueKeyRef.current = nextKey;
    setEventPulse(true);
    const timer = setTimeout(() => setEventPulse(false), 760);
    return () => clearTimeout(timer);
  }, [rowCue?.triggerKey]);

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

  const url = coinbaseSpotUrl(token || {});

  const openTrading = () => {
    if (!url) return;
    if (window.getSelection?.().toString()) return;
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const dataSide =
    side === "gainer" || side === "loser"
      ? side
      : Number.isFinite(changeNum)
        ? (changeNum >= 0 ? "gainer" : "loser")
        : "flat";
  const dataState =
    pctInfo.state === "negative"
      ? "loss"
      : pctInfo.state === "positive"
        ? "gain"
        : "flat";
  const rankMoveTone = !rowCue?.rankShiftLabel
    ? "flat"
    : dataSide === "loser"
      ? "neutral"
      : rowCue.rankShiftTone;
  const rankMoveMagnitude = Math.abs(Number(rankDelta) || 0);
  const rankMoveLabel = !rowCue?.rankShiftLabel
    ? ""
    : dataSide === "loser"
      ? `${rankMoveMagnitude}${rankDelta > 0 ? "↑" : "↓"}`
      : rowCue.rankShiftLabel;
  const rankMoveTitle = !rowCue?.rankShiftLabel
    ? ""
    : dataSide === "loser"
      ? `Moved ${rankDelta > 0 ? "up" : "down"} ${rankMoveMagnitude} position${rankMoveMagnitude === 1 ? "" : "s"} on losers board`
      : "Board position shift";
  const rankMoveAria = !rowCue?.rankShiftLabel
    ? ""
    : dataSide === "loser"
      ? `Moved ${rankDelta > 0 ? "up" : "down"} ${rankMoveMagnitude} position${rankMoveMagnitude === 1 ? "" : "s"} on losers board`
      : `Board position shift ${rankMoveLabel}`;
  const liveRank = Number(token?.live_rank);
  const liveScore = Number(token?.live_score);
  const liveUniverse = Number(token?.universe_size);
  const hasLiveRank = Number.isFinite(liveRank) && Number.isFinite(liveScore);
  const liveEvidence = Array.isArray(token?.live_reasons) ? token.live_reasons.join(" · ") : "";
  const liveRisks = Array.isArray(token?.live_risks) ? token.live_risks.map((item) => String(item).toLowerCase()) : [];
  const dataQuality = Number(token?.data_quality) || 0;
  const moveStatus = getMoveStatus(token, dataSide);
  const moveTone = moveStatus.toLowerCase();
  const liveInputRead = Number.isFinite(Number(token?.observed_inputs))
    ? `${token.observed_inputs}/${token.expected_inputs || 6} inputs live`
    : `${dataQuality}% input coverage`;
  const liveRankTitle = hasLiveRank
    ? `${moveStatus} move · live strength #${liveRank}${Number.isFinite(liveUniverse) ? ` of ${liveUniverse}` : ""} · ${liveScore}/100 ${token?.live_label || ""} · ${liveInputRead}${liveEvidence ? ` · ${liveEvidence}` : ""}${liveRisks.length ? ` · risk: ${liveRisks.join(" · ")}` : ""}`
    : "";

  const renderCells = () => (
    <>
      {/* 1. Rank circle */}
      <CellTag className="bh-cell bh-cell-rank mw-cell mw-cell--rank" style={{ "--mw-j": 0 }}>
        <div className="bh-rank-stack">
          <div className="bh-rank">{rank}</div>
        </div>
      </CellTag>

      {/* 2. Token name */}
      <CellTag className="bh-cell bh-cell-symbol mw-cell mw-cell--symbol" style={{ "--mw-j": 1 }}>
        <div className="bh-symbol-stack">
          <div className="bh-symbol-line">
            <div className="bh-symbol">{token.symbol}</div>
            <div className="bh-symbol-markers">
              {hasLiveRank ? (
                <span
                  className={`bh-live-rank bh-live-rank--${moveTone}`}
                  title={liveRankTitle}
                  aria-label={liveRankTitle}
                >
                  {moveStatus}
                </span>
              ) : null}
              {primaryCue?.emoji ? (
                <span
                  className={`bh-symbol-cue bh-symbol-cue--${primaryCue.tone === "warning" ? "negative" : primaryCue.tone || "neutral"}`}
                  title={primaryCue?.title || primaryCue?.label}
                  aria-label={primaryCue?.label}
                >
                  {primaryCue.emoji}
                </span>
              ) : null}
              {secondaryCue?.emoji ? (
                <span
                  className={`bh-symbol-cue bh-symbol-cue--recent bh-symbol-cue--${secondaryCue.tone === "warning" ? "negative" : secondaryCue.tone || "neutral"}`}
                  title={secondaryCue?.title || secondaryCue?.label}
                  aria-label={secondaryCue?.title || secondaryCue?.label}
                >
                  {secondaryCue.emoji}
                </span>
              ) : null}
              {persistenceCue ? (
                <span className="bh-symbol-persist" title={persistenceCue.title} aria-label={persistenceCue.ariaLabel}>
                  <span className="bh-symbol-persist-dot" aria-hidden="true" />
                  {persistenceCue.compactCount ? (
                    <span className="bh-symbol-persist-count" aria-hidden="true">
                      {persistenceCue.compactCount}
                    </span>
                  ) : null}
                </span>
              ) : null}
              {rankMoveLabel ? (
                <span
                  className={`bh-symbol-move bh-symbol-move--${rankMoveTone}`}
                  title={rankMoveTitle}
                  aria-label={rankMoveAria}
                >
                  {rankMoveLabel}
                </span>
              ) : null}
            </div>
          </div>
        </div>
      </CellTag>

      {/* 3. Price stack (current / previous) */}
      <CellTag className="bh-cell bh-cell-price mw-cell mw-cell--price" style={{ "--mw-j": 2 }}>
        <div className={`tr-price-current bh-price-current${priceFlash ? " is-updating" : ""}`}>
          {formatPrice(currentPrice)}
        </div>
        {!isWatchlisted && prevPrice !== null && (
          <div className="bh-price-previous">{formatPrice(prevPrice)}</div>
        )}
      </CellTag>

      {/* 4. Percent change – main focal point */}
      <CellTag className="bh-cell bh-cell-change mw-cell mw-cell--pct" style={{ "--mw-j": 3 }}>
        <div className="bh-change-stack">
          <span className={`bh-change ${pctInfo.className}${pctFlash ? " is-updating" : ""}`}>{pctInfo.display}</span>
          {isWatchlisted && changeField === "change_watch" && hasChange && (
            <span className="bh-change-label">Since added</span>
          )}
        </div>
      </CellTag>

      {/* 5. Actions – stacked on far right */}
      <CellTag className="bh-cell bh-cell-actions">
        <RowActions
          starred={Boolean(isWatchlisted)}
          onToggleStar={handleToggleStar}
          onInfoClick={openTrading}
        />
      </CellTag>
    </>
  );

  const rowClassName = [rowClass, symbol ? "bh-row-clickable" : ""].filter(Boolean).join(" ");
  const open = () => {
    const target = symbol || token?.ticker || token?.base || token?.product_id;
    if (!target) return;
    if (window.getSelection?.().toString()) return;
    openSentiment(target);
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

  const breatheDelayMs = Number.isFinite(rank) ? (rank * 137) % 9200 : 0;
  const breatheDurationMs = 8800 + (Number.isFinite(rank) ? (rank * 53) % 2400 : 0);
  const cellCadenceMs = 5200 + (Number.isFinite(rank) ? (rank * 83) % 1900 : 0);
  const cellCadenceDelayMs = Number.isFinite(rank) ? (rank * 41) % 620 : 0;
  const cellOrchDelayMs = Number.isFinite(rank) ? (rank * 67) % 980 : 0;
  const mwRowIndex = Number.isFinite(rowIndex) ? rowIndex : Number.isFinite(rank) ? rank - 1 : 0;
  const mwSeed = (mwRowIndex * 37) % 97;
  const rowStyle = {
    ...(pulse ? { "--bh-pulse-delay": `${pulseDelayMs}ms` } : {}),
    "--bh-breathe-delay": `${breatheDelayMs}ms`,
    "--bh-breathe-duration": `${breatheDurationMs}ms`,
    "--bh-cell-cadence": `${cellCadenceMs}ms`,
    "--bh-cell-cadence-delay": `${cellCadenceDelayMs}ms`,
    "--bh-cell-orch-delay": `${cellOrchDelayMs}ms`,
    "--bh-cell-stagger": "120ms",
    "--mw-i": mwRowIndex,
    "--mw-seed": mwSeed,
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

      const panelOrigin = row.closest("[data-hover-origin]")?.getAttribute("data-hover-origin");
      const col = row.closest(".bh-col");
      let focusRatioX = 0.5;

      if (panelOrigin === "right") {
        focusRatioX = 0.74;
      } else if (panelOrigin === "left") {
        focusRatioX = 0.26;
      } else if (col?.parentElement) {
        if (!col.previousElementSibling) {
          focusRatioX = 0.74;
        } else if (!col.nextElementSibling) {
          focusRatioX = 0.26;
        }
      } else {
        const boardMid = b.left + (b.width || 0) / 2;
        const rowMid = r.left + r.width / 2;
        focusRatioX = rowMid < boardMid ? 0.72 : 0.28;
      }

      const focusX = Math.max(0, r.left - b.left + r.width * focusRatioX);
      const focusY = Math.max(0, r.top - b.top + bleedTop + r.height * 0.5);
      const spotW = Math.max(96, Math.min(180, r.width * 0.34));
      const spotH = Math.max(28, Math.min(56, r.height * 0.84));

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
      board.style.setProperty("--emit-focus-x", `${focusX}px`);
      board.style.setProperty("--emit-focus-y", `${focusY}px`);
      board.style.setProperty("--emit-spot-w", `${spotW}px`);
      board.style.setProperty("--emit-spot-h", `${spotH}px`);
      board.setAttribute("data-row-hover", "1");
    } else {
      board.setAttribute("data-row-hover", "0");
    }
  };

  return (
    <>
      <RowTag
        className={`${rowClassName}${pulse || pulsePrice || pulsePct || eventPulse ? " is-pulsing" : ""}${eventPulse ? " bh-row--event" : ""}`}
        style={rowStyle}
        data-side={dataSide}
        data-state={dataState}
        data-cue={rowCue?.key || "normal"}
        data-cue-tone={rowCue?.tone || "neutral"}
        data-cue-intensity={rowCue?.intensity || "low"}
        role={symbol ? "button" : undefined}
        tabIndex={symbol ? 0 : undefined}
        onClick={handleClick}
        onKeyDown={onKeyDown}
        onPointerEnter={setRabbitHover(true)}
        onPointerLeave={setRabbitHover(false)}
        aria-label={symbol ? `Open ${token?.symbol} sentiment` : undefined}
      >
        <span className="bh-row-accent" aria-hidden="true" />
        <span className="bh-row-trigger" aria-hidden="true" />
        <span className="bh-row-breathe" aria-hidden="true" />
        {renderCells()}
      </RowTag>
    </>
  );
}
