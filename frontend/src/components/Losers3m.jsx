// src/components/Losers3m.jsx
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

export default function Losers3m({ onInfo }) {
  const { data, isLoading, isError } = useDataFeed();
  const { has, add, remove } = useWatchlist();
  const [isExpanded, setIsExpanded] = useState(false);

  const losers = useMemo(() => {
    const list = data?.losers_3m;
    const source = Array.isArray(list) ? list : list && Array.isArray(list.data) ? list.data : [];

    return source
      .map((row) => {
        const key = "price_change_percentage_3min";
        const raw = row?.[key] ?? row?.gain ?? 0;
        const num = Number(raw);
        const pct = Number.isFinite(num) ? num : 0;
        return { ...row, pct, _pct: pct };
      })
      .filter((r) => Number.isFinite(r._pct) && r._pct < 0)
      .sort((a, b) => a._pct - b._pct);
  }, [data]);

  const handleToggleWatchlist = (item) => {
    if (!add || !remove) return;
    has(item.symbol)
      ? remove(item.symbol)
      : add({ symbol: item.symbol, price: item.current_price });
  };

  const count = losers.length;
  const visible = isExpanded ? losers.slice(0, MAX_EXPANDED) : losers.slice(0, MAX_BASE);
  const panelStatus = isError ? "error" : count > 0 ? "ready" : isLoading ? "loading" : "empty";

  return (
    <div className="bh-board-panel">
      <h2 className="bh-section-header bh-section-header--losers">Top Losers (3m)</h2>
      <StatusGate
        status={panelStatus}
        skeleton={<SkeletonTable rows={MAX_BASE} />}
        empty={<p className="bh-empty-copy">No 3m losers yet.</p>}
        error={<p className="state-copy">Failed to load 3m losers.</p>}
      >
        <div className="bh-table">
          <motion.div initial="hidden" animate="visible" exit="exit" variants={listVariants}>
            <AnimatePresence>
              {visible.map((row, idx) => {
                const forced = -Math.abs(row.pct ?? row._pct ?? 0);
                const rank = row.rank ?? idx + 1;

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
                  <a key={row.symbol || idx} href={href} target="_blank" rel="noreferrer" className="bh-row-link">
                    <AnimatedTokenRow
                      layout
                      variants={rowVariants}
                      rank={rank}
                      symbol={row.symbol}
                      name={row.name}
                      currentPrice={row.current_price}
                      previousPrice={row.initial_price_3min}
                      percentChange={forced}
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
}
