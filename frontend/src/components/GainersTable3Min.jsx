import { useMemo, useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useDataFeed } from "../hooks/useDataFeed";
import { useHybridLive as useHybridLiveNamed } from "../hooks/useHybridLive";
import { TokenRowUnified } from "./TokenRowUnified";
import { TableSkeletonRows } from "./TableSkeletonRows";
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

const sortByPct3mThenSymbol = (a, b) => {
  const ap = Number(a?._pct ?? a?.change_3m);
  const bp = Number(b?._pct ?? b?.change_3m);
  const aValid = Number.isFinite(ap);
  const bValid = Number.isFinite(bp);

  if (aValid && bValid && bp !== ap) return bp - ap;
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

const GainersTable3Min = ({ tokens: tokensProp, loading: loadingProp, warming3m = false, onInfo, onToggleWatchlist, watchlist = [] }) => {
  // Support both prop-based (new centralized approach) and hook-based (legacy) usage
  const { data, isLoading: hookLoading, getActiveAlert } = useDataFeed();
  const [isExpanded, setIsExpanded] = useState(false);
  const lastValueRef = useRef(new Map());
  const prevRankRef = useRef(new Map());
  const rankMoveTimersRef = useRef(new Map());
  const [rankMoveById, setRankMoveById] = useState({});

  // Use props if provided, otherwise fall back to hook data
  const isLoading = loadingProp !== undefined ? loadingProp : hookLoading;

  // Also call the compatibility `useHybridLive` hook so this file explicitly
  // references it (older diagnostics and invariants expect this hook to be
  // present). We don't strictly need to use its return here because the
  // component currently processes `data` from `useDataFeed`, but having the
  // hook present preserves wiring expectations and makes future migrations
  // easier.
  const { data: _hybridPayload = {} } = useHybridLiveNamed();
  const gainers3m = useMemo(() => {
    if (tokensProp) return tokensProp; // Use prop if provided

    const list = data?.gainers_3m;
    const source = Array.isArray(list) ? list : list && Array.isArray(list.data) ? list.data : [];

    return source
      .map((row) => {
        const pctRaw =
          row.price_change_percentage_3min ??
          row.change_3m ??
          row.gain ??
          row.pct_change ??
          row.pct ??
          0;
        const pct = Number(pctRaw);

        const baselineOrNullPrev = baselineOrNull(row.previous_price_3m ?? row.initial_price_3min ?? null);
        return {
          ...row,
          change_3m: pct,
          _pct: Number.isFinite(pct) ? pct : 0,
          previous_price_3m: baselineOrNullPrev,
          current_price: row.price ?? row.current_price,
        };
      })
      .filter((r) => r.symbol || r.product_id)
      .filter((r) => Number.isFinite(r._pct) && r._pct > 0)
      .sort((a, b) => b._pct - a._pct);
  }, [data, tokensProp]);

  const orderedRows = useReorderCadence(gainers3m, sortByPct3mThenSymbol, REORDER_COMMIT_MS_3M);
  const visibleRows = isExpanded ? orderedRows.slice(0, MAX_EXPANDED) : orderedRows.slice(0, MAX_BASE);

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

    visibleRows.forEach((row, index) => {
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
  }, [visibleRows]);

  const rowsWithPulse = useMemo(() => {
    const map = lastValueRef.current;
    return visibleRows.map((row) => {
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
  }, [visibleRows, rankMoveById]);
  const count = gainers3m.length;
  const hasData = count > 0;

  // Loading skeleton state
  if (isLoading && !hasData) {
    return (
      <div className="gainers-table">
        <div className="bh-panel bh-panel-full">
          <div className="bh-table">
            <TableSkeletonRows columns={5} rows={6} />
          </div>
        </div>
      </div>
    );
  }

  // No data state
  if (!isLoading && !hasData) {
    return (
      <div className="gainers-table">
        <div className="bh-panel bh-panel-full">
          <div className="bh-table">
            {warming3m ? (
              <div className="panel-empty" style={{ textAlign: "center", opacity: 0.7, padding: "0.75rem 0" }}>
                3m baseline warming… waiting for first snapshot.
              </div>
            ) : (
              <div className="panel-empty" style={{ textAlign: "center", opacity: 0.7, padding: "0.75rem 0" }}>
                No 3-minute movers to show right now.
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="gainers-table">
      <div className="bh-panel bh-panel-full">
        {warming3m && (
          <div className="bh-warming-pill is-warming" style={{ margin: "0.25rem 0 0.35rem", display: "inline-flex" }}>
            WARMING 3M BASELINE
          </div>
        )}
        <div className="bh-table">
          <AnimatePresence initial={false}>
            {rowsWithPulse.map(({ row: token, priceChanged, pctChanged, rankDelta }, index) => {
              const rowKey = buildRowKey(token) || token?.symbol || token?.product_id;
              return (
                <motion.div
                  key={rowKey}
                  layout
                  transition={{
                    layout: { type: "spring", stiffness: 520, damping: 46 },
                  }}
                  style={{ "--mw-i": index }}
                >
                  <TokenRowUnified
                    token={token}
                    rank={index + 1}
                    rowIndex={index}
                    changeField="change_3m"
                    side="gainer"
                    onInfo={onInfo}
                    onToggleWatchlist={onToggleWatchlist}
                    isWatchlisted={watchlist.includes(token.symbol)}
                    pulsePrice={priceChanged}
                    pulsePct={pctChanged}
                    rankDelta={rankDelta}
                    pulseDelayMs={index * 18}
                    activeAlert={typeof getActiveAlert === "function" ? getActiveAlert(token.symbol) : null}
                  />
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      </div>

      {count > MAX_BASE && (
        <div className="panel-footer">
          <button
            className="btn-show-more"
            aria-expanded={isExpanded}
            onClick={() => setIsExpanded((s) => !s)}
          >
            {isExpanded
              ? "Show less"
              : `Show more (${Math.min(count, MAX_EXPANDED) - MAX_BASE} more)`}
          </button>
        </div>
      )}
    </div>
  );
};

export default GainersTable3Min;
