import { useMemo, useState, useCallback } from "react";
import { LayoutGroup, motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { useDataFeed } from "../hooks/useDataFeed";
import { TokenRowUnified } from "./TokenRowUnified";
import { baselineOrNull } from "../utils/num.js";
import "./ui/skeleton.css";
import { useReorderCadence } from "../hooks/useReorderCadence";
import { rowVariants } from "./motionVariants.js";

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
};

const getRowIdentity = (row) => (
  row?.product_id ??
  row?.symbol ??
  row?.base ??
  row?.ticker ??
  null
);

const buildRowKey = (row, index) => {
  const base = getRowIdentity(row);
  if (!base) return `row-${index}`;
  // Use a stable key based on the row identity (avoid including index)
  // so reorders keep the same key and framer-motion can animate layout changes.
  return String(base);
};

export default function GainersTable1Min({ tokens: tokensProp, loading: loadingProp, onInfo, onToggleWatchlist, watchlist = [] }) {
  // Support both prop-based (new centralized approach) and hook-based (legacy) usage
  const { data, isLoading: hookLoading } = useDataFeed();
  const prefersReducedMotion = useReducedMotion();

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
      .filter((r) => Number(r.change_1m) > 0)
      .sort((a, b) => Number(b.change_1m) - Number(a.change_1m));

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

  const MAX_ROWS_PER_COLUMN = 4;
  const MAX_VISIBLE_COLLAPSED = 8;
  const MAX_VISIBLE_EXPANDED = 16;

  const [expanded, setExpanded] = useState(false);
  const filteredRows = useMemo(
    () =>
      (gainers1m || [])
        .filter(Boolean)
        .filter((row) => row.symbol || row.product_id),
    [gainers1m]
  );

  const sortFn = useCallback((a, b) => Number(b.change_1m ?? 0) - Number(a.change_1m ?? 0), []);

  const cadenced = useReorderCadence(
    filteredRows,
    sortFn,
    prefersReducedMotion ? 0 : 360
  );
  const maxVisible = expanded ? MAX_VISIBLE_EXPANDED : MAX_VISIBLE_COLLAPSED;
  const displayRows = cadenced.slice(0, maxVisible);
  const isSingleColumn = displayRows.length > 0 && displayRows.length <= MAX_ROWS_PER_COLUMN;
  const skeletonSingle = filteredRows.length <= MAX_ROWS_PER_COLUMN;

  const hasData = displayRows.length > 0;

  // Loading skeleton state
  if (isLoading && !hasData) {
    return (
      <div className="gainers-table">
        <div className="panel-row--1m panel-row--grid-skeleton">
          <SkeletonGrid1m rows={4} cols={4} />
        </div>
      </div>
    );
  }

  // No data state
  if (!isLoading && !hasData) {
    return (
      <div className="gainers-table">
        <div className={`panel-row--1m ${isSingleColumn ? "panel-row--single" : ""}`}>
          <div className="bh-table">
            <div className="token-row token-row--empty">
              <div style={{ width: "100%", textAlign: "center", opacity: 0.7, padding: "0.75rem 0" }}>
                No 1-minute movers to show right now.
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const leftLimit = displayRows.length > MAX_VISIBLE_COLLAPSED ? 8 : 4;
  const leftColumn = displayRows.slice(0, leftLimit);
  const rightColumn = displayRows.slice(leftLimit, leftLimit * 2);
  const hasSecondColumn = rightColumn.length > 0;
  const density = hasSecondColumn ? "normal" : "tight";

  return (
    <div className="gainers-table">
      <LayoutGroup>
        <div className={`panel-row--1m ${isSingleColumn ? "panel-row--single" : ""}`}>
          <div className="bh-table">
            <AnimatePresence initial={false}>
              {leftColumn.map((token, index) => {
                const rowKey = buildRowKey(token, index);
                return (
                  <motion.div
                    key={rowKey}
                    layout={prefersReducedMotion ? false : "position"}
                    layoutId={rowKey}
                    initial="hidden"
                    animate="visible"
                    exit="exit"
                    variants={rowVariants}
                    transition={prefersReducedMotion ? { duration: 0 } : { type: "spring", stiffness: 680, damping: 36 }}
                  >
                    <TokenRowUnified
                      token={token}
                      rank={index + 1}
                      changeField="change_1m"
                      side="gainer"
                      renderAs="div"
                      onInfo={onInfo}
                      onToggleWatchlist={onToggleWatchlist}
                      isWatchlisted={watchlist.includes(token.symbol)}
                      density={density}
                    />
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>

          {hasSecondColumn && (
            <div className="bh-table">
              <AnimatePresence initial={false}>
                {rightColumn.map((token, index) => {
                  const absoluteIndex = leftLimit + index;
                  const rowKey = buildRowKey(token, absoluteIndex);
                  return (
                    <motion.div
                      key={rowKey}
                      layout={prefersReducedMotion ? false : "position"}
                      layoutId={rowKey}
                      initial="hidden"
                      animate="visible"
                      exit="exit"
                      variants={rowVariants}
                      transition={prefersReducedMotion ? { duration: 0 } : { type: "spring", stiffness: 680, damping: 36 }}
                    >
                      <TokenRowUnified
                        token={token}
                        rank={absoluteIndex + 1}
                        changeField="change_1m"
                        side="gainer"
                        renderAs="div"
                        onInfo={onInfo}
                        onToggleWatchlist={onToggleWatchlist}
                        isWatchlisted={watchlist.includes(token.symbol)}
                        density={density}
                      />
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          )}
        </div>
      </LayoutGroup>
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
