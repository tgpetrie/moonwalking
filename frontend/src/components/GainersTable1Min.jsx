import React, { useMemo, useState, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import TokenRow from "./TokenRow.jsx";
import StatusGate from "./ui/StatusGate";
import SkeletonTable from "./ui/SkeletonTable";
import { useDataFeed } from "../hooks/useDataFeed";

// Framer Motion row variants and transition for soft enter/exit and reordering
const rowVariants = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -6 },
};

const rowTransition = {
  type: "spring",
  stiffness: 240,
  damping: 30,
  mass: 0.65,
};

const MotionTokenRow = motion(TokenRow);

export default function GainersTable1Min({
  rows = [],
  loading,
  error,
  onInfo,
}) {
  const { data, isLoading: feedLoading, isError: feedError } = useDataFeed();
  // Debug: allow forcing the loading state via URL query `?forceLoading1m=1`
  let forceLoading = false;
  if (typeof window !== "undefined") {
    try {
      const params = new URLSearchParams(window.location.search);
      forceLoading = params.has("forceLoading1m") || params.get("forceLoading1m") === "1";
    } catch (e) {
      forceLoading = false;
    }
  }
  const isLoading = Boolean(loading) || feedLoading || forceLoading;
  const [showMore, setShowMore] = useState(false);

  const feedRows = useMemo(() => {
    const list = data?.gainers_1m;
    if (Array.isArray(list)) return list;
    if (list && Array.isArray(list.data)) return list.data;
    return [];
  }, [data]);

  const allRows = useMemo(() => {
    const source = Array.isArray(rows) && rows.length ? rows : feedRows;
    console.log("[1m gainers raw]", source);
    if (Array.isArray(source)) return source;
    if (source && Array.isArray(source.data)) return source.data;
    if (source && Array.isArray(source.items)) return source.items;
    return [];
  }, [rows, feedRows]);

  const normalizedRows = useMemo(() => {
    return allRows
      .map((row) => {
        const pctRaw =
          row.price_change_percentage_1min ??
          row.change_1m ??
          row.pct_change ??
          row.pct ??
          row.percentChange ??
          0;
        const pct = typeof pctRaw === "string"
          ? Number(pctRaw.replace(/%/g, ""))
          : Number(pctRaw);
        return {
          ...row,
          pct,
          _pct: Number.isFinite(pct) ? pct : 0,
        };
      })
        .filter((r) => Number.isFinite(r._pct) && r._pct > 0)
      .sort((a, b) => b._pct - a._pct);
  }, [allRows]);

  const total = normalizedRows.length;
  const visibleCount = showMore
    ? Math.min(total, 16)
    : Math.min(total, 8);

  // Visible slice in canonical rank order (1..N)
  const { visibleRows, leftRows, rightRows, hasFew } = useMemo(() => {
    const slice = normalizedRows.slice(0, visibleCount);

    const withRank = slice.map((row, index) => {
      const displayRank = row.rank && row.rank >= 1 ? row.rank : index + 1;
      return { ...row, displayRank };
    });

    const few = withRank.length <= 4;

    // New split strategy: interleave rows into two columns when >4 visible rows.
    if (few) {
      return {
        visibleRows: withRank,
        leftRows: withRank,
        rightRows: [],
        hasFew: true,
      };
    }

    const left = [];
    const right = [];
    // Interleave: even indices -> left, odd indices -> right
    withRank.forEach((r, i) => {
      if (i % 2 === 0) left.push(r);
      else right.push(r);
    });

    return {
      visibleRows: withRank,
      leftRows: left,
      rightRows: right,
      hasFew: false,
    };
  }, [normalizedRows, visibleCount, showMore]);

  // Animated guard: maintain animated left/right slices and only update when symbol order changes
  const [animatedLeftRows, setAnimatedLeftRows] = useState([]);
  const [animatedRightRows, setAnimatedRightRows] = useState([]);

  useEffect(() => {
    const sameLeft =
      animatedLeftRows.length === leftRows.length &&
      animatedLeftRows.every((r, i) => r?.symbol === leftRows[i]?.symbol);
    if (!sameLeft) setAnimatedLeftRows(leftRows);

    const sameRight =
      animatedRightRows.length === rightRows.length &&
      animatedRightRows.every((r, i) => r?.symbol === rightRows[i]?.symbol);
    if (!sameRight) setAnimatedRightRows(rightRows);
  }, [leftRows, rightRows, animatedLeftRows, animatedRightRows]);

  const panelStatus = error || feedError
    ? "error"
    : total > 0
    ? "ready"
    : isLoading
    ? "loading"
    : "empty";

  return (
    <section className="panel panel-1m">
      <header className="panel-header">
        <div className="section-head section-head--center section-head-gain">
          <span className="section-head__label">1-MIN GAINERS</span>
          <span className="section-head-line section-head-line-gain" />
        </div>
      </header>
      <StatusGate
        status={panelStatus}
        skeleton={<SkeletonTable rows={6} />}
        empty={<div className="state-copy">No 1-min gainers right now.</div>}
        error={<div className="state-copy">Gainers stream down. Auto-recovering.</div>}
      >
        <div className={`panel-body panel-1m-body${hasFew ? " panel-1m-body--single" : ""}`}>
          {total > 0 && (
            <div className={`gainers-1m-grid ${hasFew ? "is-single-column" : ""}`}>
              <div className="gainers-1m-col">
                <AnimatePresence initial={false}>
                  {animatedLeftRows.map((row, idx) => (
                    <motion.div
                      key={row.symbol || idx}
                      layout
                      variants={rowVariants}
                      initial="initial"
                      animate="animate"
                      exit="exit"
                      transition={{ ...rowTransition, delay: idx * 0.015 }}
                    >
                      <MotionTokenRow
                        rank={row.displayRank}
                        row={row}
                        changeKey="price_change_percentage_1min"
                        rowType="gainer"
                        onInfo={onInfo}
                      />
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>

              {!hasFew && (
                <div className="gainers-1m-col">
                  <AnimatePresence initial={false}>
                    {animatedRightRows.map((row, idx) => (
                      <motion.div
                        key={row.symbol || idx}
                        layout
                        variants={rowVariants}
                        initial="initial"
                        animate="animate"
                        exit="exit"
                        transition={{ ...rowTransition, delay: idx * 0.015 }}
                      >
                        <MotionTokenRow
                          rank={row.displayRank}
                          row={row}
                          changeKey="price_change_percentage_1min"
                          rowType="gainer"
                          onInfo={onInfo}
                        />
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              )}
            </div>
          )}
        </div>

        {total > 8 && (
          <div className="panel-footer panel-1m-footer">
            <button
              type="button"
              className="btn-show-more show-more-btn"
              aria-expanded={showMore}
              aria-controls="one-min-list"
              onClick={() => setShowMore((prev) => !prev)}
            >
              {showMore ? "Show Less" : "Show More"}
            </button>
          </div>
        )}
      </StatusGate>
    </section>
  );
}
