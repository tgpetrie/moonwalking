import React, { useMemo, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useDataFeed } from "../hooks/useDataFeed";
import { useHybridLive as useHybridLiveNamed } from "../hooks/useHybridLive";
import { TableSkeletonRows } from "./TableSkeletonRows";
import { TokenRowUnified } from "./TokenRowUnified";
import { normalizeTableRow } from "../lib/adapters";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import { baselineOrNull } from "../utils/num.js";

const MAX_BASE = 8;

const getRowIdentity = (row) => (
  row?.product_id ??
  row?.symbol ??
  null
);

const buildRowKey = (row) => {
  const base = getRowIdentity(row);
  return base ? String(base) : undefined;
};

export default function Losers3m({
  tokens: tokensProp,
  loading: loadingProp,
  onInfo,
  onToggleWatchlist,
  watchlist = [],
}) {
  const { has, add, remove } = useWatchlist();
  const { data, isLoading: hookLoading, getActiveAlert } = useDataFeed();
  const lastValueRef = useRef(new Map());

  // Legacy live feed hook kept for wiring parity (data feed used by default)
  const { data: hybridPayload = {} } = useHybridLiveNamed({
    endpoint: "/api/component/losers-table",
    eventName: "losers3m",
    pollMs: 8000,
    initial: [],
  });

  const isLoading = loadingProp !== undefined ? loadingProp : hookLoading;

  const rows = useMemo(() => {
    // Prefer explicit tokens prop, then data feed, then legacy payload
    const sourceList = tokensProp ?? data?.losers_3m ?? hybridPayload?.data ?? [];
    const source = Array.isArray(sourceList)
      ? sourceList
      : Array.isArray(sourceList?.data)
      ? sourceList.data
      : [];

    const sorted = source
      .map((row, idx) => {
        const nr = normalizeTableRow(row);
        const pctRaw =
          row.price_change_percentage_3min ??
          row.change_3m ??
          nr._pct ??
          row.pct_change ??
          row.pct ??
          0;
        const pct = Number(pctRaw);

        const baselineOrNullPrev = baselineOrNull(row.previous_price_3m ?? row.initial_price_3min ?? nr._raw?.initial_price_3min ?? null);

        return {
          ...row,
          symbol: row.symbol ?? nr.symbol,
          current_price: row.price ?? row.current_price ?? nr.currentPrice,
          previous_price_3m: baselineOrNullPrev,
          change_3m: Number.isFinite(pct) ? pct : 0,
        };
      })
      .filter((r) => Number.isFinite(r.change_3m) && r.change_3m < 0)
      .sort((a, b) => a.change_3m - b.change_3m);

    const seen = new Set();
    const deduped = [];
    sorted.forEach((row) => {
      const ident = getRowIdentity(row);
      if (!ident) return;
      const key = String(ident).toUpperCase();
      if (seen.has(key)) return;
      seen.add(key);
      deduped.push(row);
    });

    return deduped;
  }, [data, hybridPayload, tokensProp]);

  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? rows : rows.slice(0, MAX_BASE);
  const rowsWithPulse = useMemo(() => {
    const map = lastValueRef.current;
    return visible.map((row) => {
      const key = getRowIdentity(row) ?? row?.ticker ?? row?.base ?? row?.rank;
      const price = Number(row?.current_price ?? row?.price ?? 0);
      const pct = Number(row?.change_3m ?? row?.price_change_percentage_3min ?? row?._pct ?? row?.pct ?? 0);
      const prev = key ? map.get(key) : null;
      const priceChanged = prev ? prev.price !== price : false;
      const pctChanged = prev ? prev.pct !== pct : false;
      if (key) {
        map.set(key, { price, pct });
      }
      return { row, priceChanged, pctChanged };
    });
  }, [visible]);
  const hasData = rows.length > 0;

  const handleToggleStar = (symbol, price) => {
    if (!symbol) return;
    if (onToggleWatchlist) {
      onToggleWatchlist(symbol, price ?? null);
      return;
    }
    if (has(symbol)) {
      remove(symbol);
    } else {
      add({ symbol, price });
    }
  };

  const handleInfo = (symbol) => {
    if (!symbol) return;
    if (onInfo) {
      onInfo(symbol);
    } else {
      window.dispatchEvent(new CustomEvent("openInfo", { detail: symbol }));
    }
  };

  const isStarred = (symbol) => {
    if (!symbol) return false;
    return (watchlist && watchlist.includes(symbol)) || has(symbol);
  };

  // Loading skeleton
  if (isLoading && !hasData) {
    return (
      <div className="bh-panel bh-panel-full">
        <div className="bh-table">
          <TableSkeletonRows columns={5} rows={6} />
        </div>
      </div>
    );
  }

  // No data
  if (!isLoading && !hasData) {
    return (
      <div className="bh-panel bh-panel-full">
        <div className="bh-table">
          <div className="bh-row token-row--empty">
            <div
              className="bh-cell"
              style={{ gridColumn: "1 / span 5", textAlign: "center", opacity: 0.7, padding: "0.75rem 0" }}
            >
              No 3-minute losers to show right now.
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="bh-panel bh-panel-full">
        <div className="bh-table">
          <AnimatePresence initial={false}>
            {rowsWithPulse.map(({ row, priceChanged, pctChanged }, idx) => {
              const rowKey = buildRowKey(row) || row.symbol || row.product_id;
              return (
                <motion.div
                  key={rowKey}
                  layout
                  layoutId={rowKey}
                  transition={{ type: "spring", stiffness: 680, damping: 36 }}
                >
                  <TokenRowUnified
                    token={row}
                    rank={idx + 1}
                    changeField="change_3m"
                    side="loser"
                    onInfo={handleInfo}
                    onToggleWatchlist={() => handleToggleStar(row.symbol, row.current_price ?? row.price)}
                    isWatchlisted={isStarred(row.symbol)}
                    renderAs="div"
                    pulsePrice={priceChanged}
                    pulsePct={pctChanged}
                    pulseDelayMs={idx * 18}
                    activeAlert={typeof getActiveAlert === "function" ? getActiveAlert(row.symbol) : null}
                  />
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      </div>

      {rows.length > MAX_BASE && (
        <div className="panel-footer">
          <button className="btn-show-more" onClick={() => setExpanded((s) => !s)}>
            {expanded ? "Show less" : `Show more (${rows.length - MAX_BASE} more)`}
          </button>
        </div>
      )}
    </>
  );
}
