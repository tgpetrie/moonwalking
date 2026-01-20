// src/components/TokenRowUnified.jsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import RowActions from "./tables/RowActions.jsx";
import { formatPct, formatPrice } from "../utils/format.js";
import { baselineOrNull } from "../utils/num.js";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";

const hashString = (value) => {
  const str = String(value ?? "");
  let hash = 0;
  for (let i = 0; i < str.length; i += 1) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
};

const phaseMsFromId = (id, spanMs = 12600) => {
  const s = String(id ?? "");
  let h = 0;
  for (let i = 0; i < s.length; i += 1) {
    h = (h * 31 + s.charCodeAt(i)) >>> 0;
  }
  return spanMs > 0 ? h % spanMs : 0;
};

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

  const tickRef = useRef(new Map());

  const useTick = (key, value, ttlMs = 900) => {
    const [on, setOn] = useState(false);

    useEffect(() => {
      const prev = tickRef.current.get(key);

      // Normalize to avoid noise (strings, floats).
      const next = typeof value === "number" ? Number(value) : String(value ?? "");

      if (prev === undefined) {
        tickRef.current.set(key, next);
        return undefined;
      }

      if (prev !== next) {
        tickRef.current.set(key, next);
        setOn(true);
        const t = setTimeout(() => setOn(false), ttlMs);
        return () => clearTimeout(t);
      }

      return undefined;
    }, [key, value, ttlMs]);

    return on;
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

  const rowId = token?.product_id || token?.symbol || "row";
  const phaseMs = useMemo(() => phaseMsFromId(rowId), [rowId]);
  const drift01 = useMemo(() => {
    const h = hashString(rowId);
    return ((h >> 4) % 1000) / 1000;
  }, [rowId]);
  const pctTickSource = token?.[changeField] ?? token?.price_change_percentage_1min ?? token?.price_change_percentage_3min;
  const priceTick = useTick(`${rowId}:price`, currentPrice);
  const pctTick = useTick(`${rowId}:pct`, pctTickSource);

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
        <div className={`tr-price-current bh-price-current${priceTick ? " bh-tick" : ""}`}>
          {formatPrice(currentPrice)}
        </div>
        <div className="bh-price-previous">{formatPrice(prevPrice)}</div>
      </CellTag>

      {/* 4. Percent change – main focal point */}
      <CellTag className="bh-cell bh-cell-change">
        <span className={`bh-change ${pctInfo.className}${pctTick ? " bh-tick" : ""}`}>{pctInfo.display}</span>
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

  const setRabbitHover = (on, e) => {
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
        className={[
          rowClassName,
          "token-row",
          "table-row",
          "bh-row",
          pulse ? "is-pulsing" : "",
        ].join(" ")}
        style={{
          ...(pulse ? { "--bh-pulse-delay": `${pulseDelayMs}ms` } : null),
          "--bh-phase": `${phaseMs}ms`,
          "--bh-drift": drift01,
        }}
        data-side={dataSide}
        role={url ? "link" : undefined}
        tabIndex={url ? 0 : undefined}
        onClick={handleClick}
        onKeyDown={onKeyDown}
        onPointerEnter={(e) => setRabbitHover(true, e)}
        onPointerLeave={(e) => setRabbitHover(false, e)}
        aria-label={url ? `Open ${token?.symbol} on Coinbase` : undefined}
      >
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
