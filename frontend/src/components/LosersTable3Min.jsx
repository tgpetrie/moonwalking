import React, { useState, useMemo, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useHybridLive as useHybridLiveNamed } from "../hooks/useHybridLive";
import { useDataFeed } from "../hooks/useDataFeed";
import { TableSkeletonRows } from "./TableSkeletonRows";
import { TokenRowUnified } from "./TokenRowUnified";
import { normalizeTableRow } from "../lib/adapters";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import { baselineOrNull } from "../utils/num.js";

const MAX_BASE = 8;
const MAX_EXPANDED = 16;
const REORDER_COMMIT_MS_3M = 700;

const buildRowKey = (row) => {
  const base = row?.product_id ?? row?.symbol;
  return base ? String(base) : undefined;
};

const getRowIdentity = (row = {}) => {
  if (row?.product_id) return String(row.product_id);
  if (row?.symbol) return String(row.symbol);
  return null;
};

const sortByPct3mLosersThenSymbol = (a, b) => {
  const ap = Number(a?.change_3m ?? a?.price_change_percentage_3min);
  const bp = Number(b?.change_3m ?? b?.price_change_percentage_3min);
  const aValid = Number.isFinite(ap);
  const bValid = Number.isFinite(bp);

  if (aValid && bValid && ap !== bp) return ap - bp;
  if (aValid !== bValid) return aValid ? -1 : 1;

  const aSym = String(a?.symbol ?? a?.ticker ?? "").toUpperCase();
  const bSym = String(b?.symbol ?? b?.ticker ?? "").toUpperCase();
  return aSym.localeCompare(bSym);
};

function useReorderCadence(rows, sortFn, ms = REORDER_COMMIT_MS_3M) {
  const latestRowsRef = useRef(rows);
  const timerRef = useRef(null);
  const prevLenRef = useRef(Array.isArray(rows) ? rows.length : 0);
  const [displayOrder, setDisplayOrder] = useState(() => {
    const list = Array.isArray(rows) ? [...rows] : [];
    list.sort(sortFn);
    return list.map(getRowIdentity).filter(Boolean);
  });

  const rowsById = useMemo(() => {
    const map = new Map();
    (Array.isArray(rows) ? rows : []).forEach((row) => {
      const id = getRowIdentity(row);
      if (!id || map.has(id)) return;
      map.set(id, row);
    });
    return map;
  }, [rows]);

  latestRowsRef.current = Array.isArray(rows) ? rows : [];

  useEffect(() => {
    const nextRows = Array.isArray(rows) ? rows : [];
    const nextLen = nextRows.length;
    const prevLen = prevLenRef.current;
    prevLenRef.current = nextLen;

    const commit = () => {
      const snapshot = Array.isArray(latestRowsRef.current) ? latestRowsRef.current : [];
      const sorted = [...snapshot];
      sorted.sort(sortFn);
      setDisplayOrder(sorted.map(getRowIdentity).filter(Boolean));
    };

    if (nextLen !== prevLen) {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      commit();
      return;
    }

    if (timerRef.current) return;
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      commit();
    }, ms);
  }, [rows, sortFn, ms]);

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  return useMemo(
    () => displayOrder.map((id) => rowsById.get(id)).filter(Boolean),
    [displayOrder, rowsById]
  );
}

export default function LosersTable3Min({ tokens: tokensProp, loading: loadingProp, warming3m = false, onInfo, onToggleWatchlist, watchlist = [] }) {
  const { has, add, remove } = useWatchlist();
  const { getActiveAlert } = useDataFeed();
  const lastValueRef = useRef(new Map());
  const prevRankRef = useRef(new Map());
  const rankMoveTimersRef = useRef(new Map());
  const [rankMoveById, setRankMoveById] = useState({});

  // Support both prop-based (new centralized approach) and hook-based (legacy) usage
  const { data: payload = {} } = useHybridLiveNamed({
    endpoint: "/api/component/losers-table",
    eventName: "losers3m",
    pollMs: 8000,
    initial: [],
  });

  const isLoading = loadingProp !== undefined ? loadingProp : false;

  // Use props if provided, otherwise fall back to hook data
  const mapped = useMemo(() => {
    if (tokensProp) {
      // Use prop tokens - they should already be normalized
      return tokensProp.map((row) => ({
        symbol: row.symbol,
        current_price: row.price ?? row.current_price,
        previous_price: baselineOrNull(row.initial_price_3min ?? row.previous_price ?? null),
        price_change_percentage_3min: row.changePct ?? row.price_change_percentage_3min ?? row.change_3m ?? null,
        isGainer: false, // PURPLE accent
        price: row.price ?? row.current_price,
      }));
    }

    // Fall back to hook data
    const raw = Array.isArray(payload?.data) ? payload.data : [];
    return raw.map((row) => {
      const nr = normalizeTableRow(row);
      return {
        symbol: nr.symbol ?? row.symbol,
        current_price: nr.currentPrice ?? row.current_price,
        previous_price: baselineOrNull(row.initial_price_3min ?? nr._raw?.initial_price_3min ?? null),
        price_change_percentage_1min: undefined,
        price_change_percentage_3min: row.price_change_percentage_3min ?? nr._raw?.price_change_percentage_3min ?? null,
        isGainer: false, // PURPLE accent
      };
    });
  }, [tokensProp, payload]);

  const [expanded, setExpanded] = useState(false);
  const filtered = useMemo(
    () =>
      mapped
        .map((row) => ({
          ...row,
          change_3m: row.price_change_percentage_3min ?? row.change_3m ?? row._pct ?? row.pct ?? 0,
        }))
        .filter((row) => row.symbol || row.product_id)
        .filter((row) => Number(row.change_3m) < 0)
        .sort((a, b) => Number(a.change_3m) - Number(b.change_3m)),
    [mapped]
  );
  const orderedRows = useReorderCadence(filtered, sortByPct3mLosersThenSymbol, REORDER_COMMIT_MS_3M);
  const visible = useMemo(
    () => (expanded ? orderedRows.slice(0, MAX_EXPANDED) : orderedRows.slice(0, MAX_BASE)),
    [orderedRows, expanded]
  );

  useEffect(() => {
    return () => {
      for (const timerId of rankMoveTimersRef.current.values()) {
        clearTimeout(timerId);
      }
      rankMoveTimersRef.current.clear();
    };
  }, []);

  useEffect(() => {
    const prev = prevRankRef.current;
    const nextRanks = new Map();
    const activeIds = new Set();

    visible.forEach((row, index) => {
      const id = getRowIdentity(row);
      if (!id) return;
      const nextRank = index + 1;
      activeIds.add(id);
      nextRanks.set(id, nextRank);
      const prevRank = prev.get(id);
      if (Number.isFinite(prevRank) && prevRank !== nextRank) {
        const delta = prevRank - nextRank;
        setRankMoveById((state) => ({ ...state, [id]: delta }));
        const existing = rankMoveTimersRef.current.get(id);
        if (existing) clearTimeout(existing);
        const timer = setTimeout(() => {
          setRankMoveById((state) => {
            if (!(id in state)) return state;
            const next = { ...state };
            delete next[id];
            return next;
          });
        }, 2600);
        rankMoveTimersRef.current.set(id, timer);
      }
    });

    for (const [id, timer] of rankMoveTimersRef.current.entries()) {
      if (activeIds.has(id)) continue;
      clearTimeout(timer);
      rankMoveTimersRef.current.delete(id);
    }

    prevRankRef.current = nextRanks;
  }, [visible]);

  const rowsWithPulse = useMemo(() => {
    const map = lastValueRef.current;
    return visible.map((row) => {
      const key = row?.product_id ?? row?.symbol ?? row?.ticker ?? row?.base ?? row?.rank;
      const price = Number(row?.current_price ?? row?.price ?? 0);
      const pct = Number(row?.change_3m ?? row?.price_change_percentage_3min ?? row?._pct ?? row?.pct ?? 0);
      const prev = key ? map.get(key) : null;
      const priceChanged = prev ? prev.price !== price : false;
      const pctChanged = prev ? prev.pct !== pct : false;
      if (key) {
        map.set(key, { price, pct });
      }
      return { row, priceChanged, pctChanged, rankDelta: key ? rankMoveById?.[key] ?? 0 : 0 };
    });
  }, [visible, rankMoveById]);

  const hasData = filtered.length > 0;

  const isStarred = (symbol) => {
    if (!symbol) return false;
    return watchlist.includes(symbol) || has(symbol);
  };

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

  const buildCoinbaseUrl = (symbol) => {
    if (!symbol) return "#";
    let pair = symbol;
    if (!/-USD$|-USDT$|-PERP$/i.test(pair)) {
      pair = `${pair}-USD`;
    }
    return `https://www.coinbase.com/advanced-trade/spot/${pair}`;
  };

  // Loading skeleton state
  if (isLoading && !hasData) {
    return (
      <div className="losers-table">
        <div className="bh-panel bh-panel-half">
          <div className="bh-table">
            {/* Render div-based skeleton rows to match TokenRowUnified */}
            <TableSkeletonRows columns={5} rows={6} renderAs="div" />
          </div>
        </div>
      </div>
    );
  }

  // No data state
  if (!isLoading && !hasData) {
    return (
      <div className="losers-table">
        <div className="bh-panel bh-panel-half">
          <div className="bh-table">
            <div className="panel-empty" style={{ width: "100%", textAlign: "center", opacity: 0.7, padding: "0.75rem 0" }}>
              {warming3m ? "3m baseline warming… waiting for first snapshot." : "No 3-minute losers to show right now."}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="losers-table">
      <div className="bh-panel bh-panel-half">
        {warming3m && (
          <div className="bh-warming-pill is-warming" style={{ margin: "0.25rem 0 0.35rem", display: "inline-flex" }}>
            WARMING 3M BASELINE
          </div>
        )}
        <div className="bh-table">
          <AnimatePresence initial={false}>
            {rowsWithPulse.map(({ row: tokenProps, priceChanged, pctChanged, rankDelta }, idx) => {
              const rowKey = buildRowKey(tokenProps) || tokenProps.symbol || tokenProps.product_id;
              return (
                <motion.div
                  key={rowKey}
                  layout
                  transition={{
                    layout: { type: "spring", stiffness: 520, damping: 46 },
                  }}
                  style={{ "--mw-i": idx }}
                >
                  <TokenRowUnified
                    token={{ ...tokenProps, change_3m: tokenProps.change_3m ?? tokenProps.price_change_percentage_3min ?? tokenProps._pct ?? tokenProps.pct ?? 0 }}
                    rank={idx + 1}
                    rowIndex={idx}
                    changeField="change_3m"
                    side="loser"
                    onInfo={() => handleInfo(tokenProps.symbol)}
                    onToggleWatchlist={() => handleToggleStar(tokenProps.symbol, tokenProps.current_price ?? tokenProps.price)}
                    isWatchlisted={isStarred(tokenProps.symbol)}
                    pulsePrice={priceChanged}
                    pulsePct={pctChanged}
                    rankDelta={rankDelta}
                    pulseDelayMs={idx * 18}
                    activeAlert={typeof getActiveAlert === "function" ? getActiveAlert(tokenProps.symbol) : null}
                  />
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      </div>

      {mapped.length > MAX_BASE && (
        <div className="panel-footer">
          <button className="btn-show-more" onClick={() => setExpanded((s) => !s)}>
            {expanded
              ? "Show less"
              : `Show more (${Math.min(mapped.length, MAX_EXPANDED) - MAX_BASE} more)`}
          </button>
        </div>
      )}
    </div>
  );
}
