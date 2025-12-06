import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import AnimatedTokenRow from "./AnimatedTokenRow.jsx";
import { rowVariants, listVariants } from "./motionVariants";
import StatusGate from "./ui/StatusGate";
import SkeletonTable from "./ui/SkeletonTable";
import { useDataFeed } from "../hooks/useDataFeed";
import { useWatchlist } from "../context/WatchlistContext.jsx";

const MAX_BASE = 8;
const MAX_EXPANDED = 16;

const GainersTable3Min = ({ onInfo }) => {
  const { data, isLoading, isError } = useDataFeed();
  const { has, add, remove } = useWatchlist();
  const [isExpanded, setIsExpanded] = useState(false);

  const gainers = useMemo(() => {
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
        return {
          ...row,
          pct,
          _pct: Number.isFinite(pct) ? pct : 0,
        };
      })
      .filter((r) => Number.isFinite(r._pct) && r._pct > 0)
      .sort((a, b) => b._pct - a._pct);
  }, [data]);

  const handleToggleWatchlist = (item) => {
    if (!add || !remove) return;
    has(item.symbol)
      ? remove(item.symbol)
      : add({ symbol: item.symbol, price: item.current_price });
  };

  const visibleRows = isExpanded ? gainers.slice(0, MAX_EXPANDED) : gainers.slice(0, MAX_BASE);
  const count = gainers.length;
  const panelStatus = isError ? "error" : count > 0 ? "ready" : isLoading ? "loading" : "empty";

  return (
    <div className="bh-board-panel">
      <h2 className="bh-section-header">Top Gainers (3m)</h2>
      <StatusGate
        status={panelStatus}
        skeleton={<SkeletonTable rows={MAX_BASE} />}
        empty={<p className="bh-empty-copy">No 3m gainers yet.</p>}
        error={<p className="state-copy">Failed to load 3m gainers.</p>}
      >
        <div className="bh-table">
          <motion.div initial="hidden" animate="visible" exit="exit" variants={listVariants}>
            <AnimatePresence>
              {visibleRows.map((row, index) => {
                const buildCoinbaseUrl = (symbol) => {
                  if (!symbol) return "#";
                  let pair = symbol;
                  if (!/-USD$|-USDT$|-PERP$/i.test(pair)) {
                    pair = `${pair}-USD`;
                  }
                  return `https://www.coinbase.com/advanced-trade/spot/${pair}`;
                };

                const href = row.trade_url || buildCoinbaseUrl(row.symbol);

                return (
                  <a key={row.symbol} href={href} target="_blank" rel="noreferrer" className="bh-row-link">
                    <AnimatedTokenRow
                      layout
                      variants={rowVariants}
                      rank={row.rank ?? index + 1}
                      symbol={row.symbol}
                      name={row.name}
                      currentPrice={row.current_price}
                      previousPrice={row.initial_price_3min}
                      percentChange={row.pct}
                      onToggleWatchlist={() => handleToggleWatchlist(row)}
                      onInfo={() => onInfo && onInfo(row.symbol)}
                      isWatchlisted={has(row.symbol)}
                    />
                  </a>
                );
              })}
            </AnimatePresence>
          </motion.div>
        </div>

        {count > MAX_BASE && (
          <div className="panel-footer">
            <button
              className="btn-show-more"
              aria-expanded={isExpanded}
              onClick={() => setIsExpanded((s) => !s)}
            >
              {isExpanded ? "Show Less" : "Show More"}
            </button>
          </div>
        )}
      </StatusGate>
    </div>
  );
};

export default GainersTable3Min;
