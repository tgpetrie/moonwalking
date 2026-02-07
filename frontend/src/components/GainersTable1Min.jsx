import { useMemo, useState, useEffect, useRef } from "react";
import PropTypes from "prop-types";
import { motion, AnimatePresence } from "framer-motion";
import { useDataFeed } from "../hooks/useDataFeed";
import { TokenRowUnified } from "./TokenRowUnified";
import { baselineOrNull } from "../utils/num.js";
import "./ui/skeleton.css";

// Reordering mode presets for 1-minute gainers table
// smooth: Default, balanced feel — fast enough to catch rockets, stable enough to avoid twitchy noise
// predator: Optional aggressive mode — tighter timing for traders who want immediate response
const PRESETS = {
  smooth: {
    alpha: 0.30,         // EMA smoothing coefficient (lower = smoother, less reactive to spikes)
    commitMs: 420,       // How often we allow UI reorders (ms)
    minStayMs: 2200,     // Min time a row stays visible once shown (prevents rapid churn)
    swapMargin: 0.18,    // Challenger must beat incumbent by this % to swap positions
    bubblePasses: 2,     // Number of bubble sort passes for hysteresis reordering
    vanishGraceMs: 1600, // Keep recently-seen coins briefly if they drop out of feed
    bufferRows: 8,       // Extra rows beyond visible to reduce cutoff thrashing
    spring: { type: "spring", stiffness: 520, damping: 40, mass: 0.9 },
  },
  predator: {
    alpha: 0.55,         // More reactive to raw changes
    commitMs: 320,       // Much faster commits
    minStayMs: 900,      // Shorter locks
    swapMargin: 0.08,    // Easier to swap positions
    bubblePasses: 4,     // More aggressive bubble passes
    vanishGraceMs: 800,  // Shorter grace period
    bufferRows: 6,       // Tighter buffer
    spring: { type: "spring", stiffness: 760, damping: 34, mass: 0.75 },
  },
};

// Read mode from localStorage: smooth (default) or predator
// Set via: localStorage.setItem("mw_1m_mode", "predator"); location.reload();
function getModePreset() {
  try {
    if (typeof window === "undefined" || !window.localStorage) return { mode: "smooth", ...PRESETS.smooth };
    const mode = (window.localStorage.getItem("mw_1m_mode") || "smooth").toLowerCase();
    return PRESETS[mode] ? { mode, ...PRESETS[mode] } : { mode: "smooth", ...PRESETS.smooth };
  } catch {
    return { mode: "smooth", ...PRESETS.smooth };
  }
}

const PRESET = getModePreset();
const COMMIT_MS = Math.max(420, Number(PRESET.commitMs) || 420);
const SPRING_CONFIG = PRESET.spring;
const RANK_STAGGER_STEP_MS = 32;
const RANK_STAGGER_MAX_MS = 360;

const SkeletonGrid1m = ({ rows = 4 }) => {
  return (
    <div className="bh-skel-grid bh-skel-grid--1m" role="status" aria-label="Loading 1-minute movers">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="bh-skel-row">
          <div className="bh-skel bh-skel-chip" />
          <div className="bh-skel bh-skel-line" />
          <div className="bh-skel bh-skel-pill" />
          <div className="bh-skel bh-skel-icon" />
        </div>
      ))}
    </div>
  );
}

GainersTable1Min.propTypes = {
  refreshTrigger: PropTypes.any,
  onWatchlistChange: PropTypes.func,
  topWatchlist: PropTypes.array,
  sliceStart: PropTypes.number,
  sliceEnd: PropTypes.number,
  fixedRows: PropTypes.number,
  hideShowMore: PropTypes.bool
};

const getRowIdentity = (row = {}) => {
  if (row?.product_id) return String(row.product_id);
  if (row?.symbol) return String(row.symbol);
  return null;
};

const buildRowKey = (row) => {
  const base = getRowIdentity(row);
  if (base) return String(base);
  const alt = row?.ticker ?? row?.base ?? row?.rank;
  return alt ? String(alt) : undefined;
};

const sortByPct1mThenSymbol = (a, b) => {
  const ap = Number(a?.change_1m);
  const bp = Number(b?.change_1m);
  const aValid = Number.isFinite(ap);
  const bValid = Number.isFinite(bp);

  if (aValid && bValid && bp !== ap) return bp - ap;
  if (aValid !== bValid) return aValid ? -1 : 1;

  const aSym = String(a?.symbol ?? a?.ticker ?? a?.base ?? a?.product_id ?? "").toUpperCase();
  const bSym = String(b?.symbol ?? b?.ticker ?? b?.base ?? b?.product_id ?? "").toUpperCase();
  if (aSym !== bSym) return aSym.localeCompare(bSym);

  const aId = getRowIdentity(a) ?? "";
  const bId = getRowIdentity(b) ?? "";
  return String(aId).localeCompare(String(bId));
};

const pct1mOf = (row) => {
  const raw =
    row?.change_1m ??
    row?.price_change_percentage_1min ??
    row?.pct_change ??
    row?.pct ??
    row?.changePct ??
    0;

  const n = typeof raw === "string" ? Number(String(raw).replace(/[%+]/g, "")) : Number(raw);
  return Number.isFinite(n) ? n : 0;
};

const priceOf = (row) => {
  const n = Number(row?.current_price ?? row?.price ?? row?.current ?? 0);
  return Number.isFinite(n) ? n : 0;
};

function useReorderCadence(rows, sortFn, ms = 420) {
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
      if (!id) return;
      if (!map.has(id)) map.set(id, row);
    });
    return map;
  }, [rows]);

  // Always keep the latest snapshot available for the cadence commit.
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

    // If membership changes (enter/exit), commit immediately so new coins appear quickly.
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

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, []);

  return useMemo(
    () => displayOrder.map((id) => rowsById.get(id)).filter(Boolean),
    [displayOrder, rowsById]
  );
}
export default function GainersTable1Min({ tokens: tokensProp, loading: loadingProp, onInfo, onToggleWatchlist, watchlist = [] }) {
  // Support both prop-based (new centralized approach) and hook-based (legacy) usage
  const { data, isLoading: hookLoading, getActiveAlert } = useDataFeed();

  // Use props if provided, otherwise fall back to hook data
  const isLoading = loadingProp !== undefined ? loadingProp : hookLoading;

  const gainers1m = useMemo(() => {
    const list = Array.isArray(tokensProp)
      ? tokensProp
      : (() => {
          const src = data?.gainers_1m;
          if (Array.isArray(src)) return src;
          if (src && Array.isArray(src.data)) return src.data;
          return [];
        })();


    const sorted = list
      .map((row) => {
        const symbol = row?.symbol ?? row?.ticker ?? row?.base ?? row?.product_id ?? "";
        const changeRaw =
          row?.change_1m ??
          row?.price_change_percentage_1min ??
          row?.pct_change ??
          row?.pct ??
          row?.changePct ??
          0;
        const change = Number(changeRaw);
        const baselineOrNullPrev = baselineOrNull(
          row?.previous_price_1m ??
            row?.price_1m_ago ??
            row?.previous_price ??
            row?.prev_price ??
            row?.initial_price_1min ??
            null
        );

        return {
          ...row,
          symbol: symbol || row?.symbol,
          change_1m: Number.isFinite(change) ? change : 0,
          previous_price_1m: baselineOrNullPrev,
          current_price: row?.current_price ?? row?.price ?? row?.current,
        };
      })
      .filter((r) => Math.abs(Number(r.change_1m)) > 0)
      .sort((a, b) => {
        const av = Math.abs(Number(a.change_1m));
        const bv = Math.abs(Number(b.change_1m));
        if (bv !== av) return bv - av;
        return sortByPct1mThenSymbol(a, b);
      });
    const seen = new Set();
    const deduped = [];
    sorted.forEach((row) => {
      const ident = getRowIdentity(row);
      if (!ident) {
        deduped.push(row);
        return;
      }
      const key = String(ident).toUpperCase();
      if (seen.has(key)) return;
      seen.add(key);
      deduped.push(row);
    });

    return deduped;
  }, [data, tokensProp]);

  const MAX_VISIBLE_COLLAPSED = 8;
  const MAX_VISIBLE_EXPANDED = 16;

  const [expanded, setExpanded] = useState(false);
  const prevByIdRef = useRef(new Map());
  const pulseTimersRef = useRef(new Map());
  const [pulsePriceById, setPulsePriceById] = useState({});
  const [pulsePctById, setPulsePctById] = useState({});
  const [rankById, setRankById] = useState({});

  const filteredRows = useMemo(
    () =>
      (gainers1m || [])
        .filter(Boolean)
        .filter((row) => row.symbol || row.product_id),
    [gainers1m]
  );
  const maxVisible = expanded ? MAX_VISIBLE_EXPANDED : MAX_VISIBLE_COLLAPSED;

  const orderedRows = useReorderCadence(filteredRows, sortByPct1mThenSymbol, COMMIT_MS);
  const displayRows = useMemo(() => orderedRows.slice(0, maxVisible), [orderedRows, maxVisible]);
  const displayOrderSignature = useMemo(
    () => displayRows.map((row) => getRowIdentity(row) || "").join("|"),
    [displayRows]
  );
  const rankedRows = useMemo(() => displayRows, [displayOrderSignature]);

  useEffect(() => {
    return () => {
      for (const timerId of pulseTimersRef.current.values()) {
        clearTimeout(timerId);
      }
      pulseTimersRef.current.clear();
    };
  }, []);

  useEffect(() => {
    const prev = prevByIdRef.current;
    const activeIds = new Set();

    const trigger = (kind, id) => {
      const timerKey = `${kind}:${id}`;
      const existing = pulseTimersRef.current.get(timerKey);
      if (existing) clearTimeout(existing);

      const setActive = kind === "price" ? setPulsePriceById : setPulsePctById;

      setActive((s) => (s?.[id] ? s : { ...s, [id]: true }));
      const t = setTimeout(() => {
        setActive((s) => {
          if (!s?.[id]) return s;
          const next = { ...s };
          delete next[id];
          return next;
        });
      }, 220);
      pulseTimersRef.current.set(timerKey, t);
    };

    for (const row of displayRows) {
      const id = getRowIdentity(row);
      if (!id) continue;
      activeIds.add(id);

      const nextPrice = priceOf(row);
      const nextPct = pct1mOf(row);
      const p = prev.get(id);

      if (p) {
        if (p.price !== nextPrice) trigger("price", id);
        if (p.pct !== nextPct) trigger("pct", id);
      }

      prev.set(id, { price: nextPrice, pct: nextPct });
    }

    // Prune prev cache for rows that left the visible set.
    for (const id of prev.keys()) {
      if (!activeIds.has(id)) prev.delete(id);
    }
  }, [displayRows]);

  useEffect(() => {
    // Stagger rank updates so reorders ripple row-by-row instead of snapping all at once.
    const timers = [];
    const activeIds = [];

    rankedRows.forEach((row, index) => {
      const id = getRowIdentity(row);
      if (!id) return;
      activeIds.push(id);
      const delay = Math.min(RANK_STAGGER_MAX_MS, index * RANK_STAGGER_STEP_MS);
      const t = setTimeout(() => {
        setRankById((prev) => {
          if (prev[id] === index + 1) return prev;
          return { ...prev, [id]: index + 1 };
        });
      }, delay);
      timers.push(t);
    });

    setRankById((prev) => {
      if (!activeIds.length) return {};
      let changed = prev ? Object.keys(prev).length !== activeIds.length : true;
      const next = {};
      for (const id of activeIds) {
        if (prev && prev[id] !== undefined) {
          next[id] = prev[id];
        } else {
          changed = true;
        }
      }
      return changed ? next : prev;
    });

    return () => {
      timers.forEach(clearTimeout);
    };
  }, [rankedRows]);

  const rowsWithPulse = useMemo(
    () =>
      displayRows.map((row) => {
        const id = getRowIdentity(row);
        return {
          row,
          rank: id && rankById?.[id] ? rankById[id] : undefined,
          priceChanged: id ? Boolean(pulsePriceById?.[id]) : false,
          pctChanged: id ? Boolean(pulsePctById?.[id]) : false,
        };
      }),
    [displayRows, pulsePriceById, pulsePctById, rankById]
  );

  const hasData = displayRows.length > 0;

  // Loading skeleton state
  if (isLoading && !hasData) {
    return (
      <div className="gainers-table">
        <div className="bh-1m-grid bh-1m-grid--single-col">
          <div className="bh-col">
            <SkeletonGrid1m rows={4} cols={4} />
          </div>
        </div>
      </div>
    );
  }

  // No data state
  if (!isLoading && !hasData) {
    return (
      <div className="gainers-table">
        <div className="bh-1m-grid bh-1m-grid--single-col">
          <div className="bh-col">
            <div className="bh-table">
              <div className="token-row token-row--empty">
                <div style={{ width: "100%", textAlign: "center", opacity: 0.7, padding: "0.75rem 0" }}>
                  No 1-minute movers to show right now.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const items = rowsWithPulse;
  const split = items.length > 4;
  const rowsPerColumn = expanded ? 8 : 4;
  const leftColumn = split ? items.slice(0, rowsPerColumn) : items;
  const rightColumn = split ? items.slice(rowsPerColumn, rowsPerColumn * 2) : [];
  const density = split ? "normal" : "tight";

  return (
    <div className="gainers-table">
      <div className={`bh-1m-grid ${split ? "bh-1m-grid--two-col" : "bh-1m-grid--single-col"}`}>
        <div className="bh-col">
          <div className="bh-table">
            <AnimatePresence initial={false} mode="popLayout">
              {leftColumn.map(({ row: token, rank, priceChanged, pctChanged }, index) => {
                const displayRank = rank ?? index + 1;
                const rowKey = buildRowKey(token);
                const rowTransition = { ...SPRING_CONFIG, delay: Math.min(0.32, (displayRank - 1) * 0.018) };
                return (
                  <motion.div
                    key={rowKey}
                    layout
                    layoutId={rowKey}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={rowTransition}
                    style={{ "--mw-i": index }}
                  >
                    <TokenRowUnified
                      token={token}
                      rank={displayRank}
                      rowIndex={index}
                      changeField="change_1m"
                      side="gainer"
                      renderAs="div"
                      onInfo={onInfo}
                      onToggleWatchlist={onToggleWatchlist}
                      isWatchlisted={watchlist.includes(token.symbol)}
                      density={density}
                      pulsePrice={priceChanged}
                      pulsePct={pctChanged}
                      pulseDelayMs={Math.min(240, (displayRank - 1) * 24)}
                      activeAlert={typeof getActiveAlert === "function" ? getActiveAlert(token.symbol) : null}
                    />
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        </div>

        {split && (
          <div className="bh-col">
            <div className="bh-table">
              <AnimatePresence initial={false} mode="popLayout">
                {rightColumn.map(({ row: token, rank, priceChanged, pctChanged }, index) => {
                  const absoluteIndex = rowsPerColumn + index;
                  const displayRank = rank ?? absoluteIndex + 1;
                  const rowKey = buildRowKey(token);
                  const rowTransition = { ...SPRING_CONFIG, delay: Math.min(0.32, (displayRank - 1) * 0.018) };
                  return (
                    <motion.div
                      key={rowKey}
                      layout
                      layoutId={rowKey}
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      transition={rowTransition}
                      style={{ "--mw-i": absoluteIndex }}
                    >
                    <TokenRowUnified
                      token={token}
                      rank={displayRank}
                      rowIndex={absoluteIndex}
                      changeField="change_1m"
                      side="gainer"
                      renderAs="div"
                        onInfo={onInfo}
                        onToggleWatchlist={onToggleWatchlist}
                        isWatchlisted={watchlist.includes(token.symbol)}
                        density={density}
                        pulsePrice={priceChanged}
                        pulsePct={pctChanged}
                        pulseDelayMs={Math.min(240, (displayRank - 1) * 24)}
                        activeAlert={typeof getActiveAlert === "function" ? getActiveAlert(token.symbol) : null}
                      />
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          </div>
        )}
      </div>
      {filteredRows.length > MAX_VISIBLE_COLLAPSED && (
        <div className="panel-footer">
          <button className="btn-show-more" onClick={() => setExpanded((s) => !s)}>
            {expanded
              ? "Show less"
              : `Show more (${Math.min(filteredRows.length, MAX_VISIBLE_EXPANDED) - MAX_VISIBLE_COLLAPSED} more)`}
          </button>
        </div>
      )}
    </div>
  );
}
