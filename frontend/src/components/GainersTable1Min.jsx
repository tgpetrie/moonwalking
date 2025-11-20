import React, { useMemo, useState, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import TokenRow from "./TokenRow.jsx";

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
  const isLoading = Boolean(loading) || forceLoading;
  const [showMore, setShowMore] = useState(false);
  const allRows = Array.isArray(rows) ? rows : [];

  const normalizedRows = useMemo(() => {
    return allRows
      .map((row) => {
        const pctRaw =
          row.price_change_percentage_1min ??
          row.change_1m ??
          row.pct_change ??
          row.pct ??
          0;
        const pct = Number(pctRaw);
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

  if (error) {
    return (
      <section className="panel panel-1m panel-1m-gainers">
        <div className="panel-header">
          <div className="section-heading section-heading--gainers">
            <span className="section-heading__label">1-MIN GAINERS</span>
            <div className="section-heading__rail" />
          </div>
        </div>
        <div className="panel-skeleton">
          <div className="skeleton-row" />
          <div className="skeleton-row" />
          <div className="skeleton-row" />
        </div>
        <div className="panel-error-text">Temporarily unavailable. Try refresh.</div>
      </section>
    );
  }

  if (loading) {
    return (
      <section className="panel panel-1m panel-1m-gainers panel--loading">
        <div className="panel-header">
          <div className="section-heading section-heading--gainers">
            <span className="section-heading__label">1-MIN GAINERS</span>
            <div className="section-heading__rail" />
          </div>
        </div>
        <div className="panel-skeleton">
          <div className="skeleton-row" />
          <div className="skeleton-row" />
          <div className="skeleton-row" />
        </div>
      </section>
    );
  }


  return (
    <section className="panel panel-1m panel-1m-gainers">
      <div className="panel-header">
        <div className="section-heading section-heading--gainers">
          <span className="section-heading__label">1-MIN GAINERS</span>
          <div className="section-heading__rail" />
        </div>
      </div>

      <div className={`panel-body panel-1m-body${hasFew ? " panel-1m-body--single" : ""}`}>
        {total === 0 && (
          <div className="panel-empty">No 1m gainers yet.</div>
        )}

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
    </section>
  );
}
