import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import AnimatedTokenRow from "./AnimatedTokenRow.jsx";
import { rowVariants, listVariants } from "./motionVariants";
import StatusGate from "./ui/StatusGate";
import SkeletonTable from "./ui/SkeletonTable";
import { useDataFeed } from "../hooks/useDataFeed";
import { useWatchlist } from "../context/WatchlistContext.jsx";

export default function GainersTable1Min({ onInfo }) {
  const { data, isLoading, isError } = useDataFeed();
  const { has, add, remove } = useWatchlist();

  const items = useMemo(() => {
    const list = data?.gainers_1m;
    const source = Array.isArray(list)
      ? list
      : list && Array.isArray(list.data)
      ? list.data
      : [];
    return source
      .map((row) => ({
        ...row,
        pct:
          row.price_change_percentage_1min ??
          row.change_1m ??
          row.pct_change ??
          row.pct ??
          0,
      }))
      .filter((r) => r.pct > 0)
      .sort((a, b) => b.pct - a.pct);
  }, [data]);

  const [expanded, setExpanded] = useState(false);
  const visibleItems = expanded ? items : items.slice(0, 8);

  const handleToggleWatchlist = (item) => {
    if (!add || !remove) return;
    has(item.symbol)
      ? remove(item.symbol)
      : add({ symbol: item.symbol, price: item.current_price });
  };

  const panelStatus = isError ? "error" : items.length > 0 ? "ready" : isLoading ? "loading" : "empty";

  const renderRows = (rows, rankOffset = 0) => (
    <motion.div initial="hidden" animate="visible" exit="exit" variants={listVariants}>
      <AnimatePresence>
        {rows.map((t, i) => {
          const buildCoinbaseUrl = (symbol) => {
            if (!symbol) return "#";
            let pair = symbol;
            if (!/-USD$|-USDT$|-PERP$/i.test(pair)) {
              pair = `${pair}-USD`;
            }
            return `https://www.coinbase.com/advanced-trade/spot/${pair}`;
          };

          const href = t.trade_url || buildCoinbaseUrl(t.symbol);
          const previous = t.price_1m_ago ?? t.previous_price ?? t.prev_price ?? t.initial_price_1m ?? t.initial_price_3min ?? null;

          return (
            <a
              key={t.symbol}
              href={href}
              target="_blank"
              rel="noreferrer"
              className="bh-row-link"
            >
              <AnimatedTokenRow
                layout
                variants={rowVariants}
                rank={rankOffset + i + 1}
                symbol={t.symbol}
                name={t.name}
                currentPrice={t.current_price}
                previousPrice={previous}
                percentChange={t.pct}
                onToggleWatchlist={() => handleToggleWatchlist(t)}
                onInfo={() => onInfo(t.symbol)}
                isWatchlisted={has(t.symbol)}
              />
            </a>
          );
        })}
      </AnimatePresence>
    </motion.div>
  );

  const isSingleColumn = visibleItems.length <= 4;

  if (isSingleColumn) {
    return (
      <section className="bh-board-row-full">
        <div className="bh-board-panel">
          <h2 className="bh-section-header">1-min Gainers</h2>
          <StatusGate status={panelStatus} skeleton={<SkeletonTable rows={4} />} empty={<p className="bh-empty-copy">No 1-min gainers right now.</p>} error={<p className="state-copy">Gainers stream down.</p>}>
            <div className="bh-table">{renderRows(visibleItems)}</div>
          </StatusGate>
          {items.length > 8 && (
            <div className="panel-footer">
              <button className="btn-show-more" onClick={() => setExpanded((s) => !s)}>
                {expanded ? "Show less" : `Show more (${items.length - 8} more)`}
              </button>
            </div>
          )}
        </div>
      </section>
    );
  }

  const mid = Math.ceil(visibleItems.length / 2);
  const left = visibleItems.slice(0, mid);
  const right = visibleItems.slice(mid);

  return (
    <>
      <section className="bh-board-row-halves">
      <div className="bh-board-panel">
        <h2 className="bh-section-header">1-min Gainers</h2>
        <StatusGate status={panelStatus} skeleton={<SkeletonTable rows={left.length || 5} />} empty={<p className="bh-empty-copy">No 1-min gainers right now.</p>} error={<p className="state-copy">Gainers stream down.</p>}>
          <div className="bh-table">{renderRows(left)}</div>
        </StatusGate>
      </div>
      <div className="bh-board-panel">
        <h2 className="bh-section-header bh-section-header--ghost">1-min Gainers</h2>
        <StatusGate status={panelStatus} skeleton={<SkeletonTable rows={right.length || 5} />} empty={null} error={null}>
          <div className="bh-table">{renderRows(right, mid)}</div>
        </StatusGate>
      </div>
      </section>
      {items.length > 8 && (
        <div className="panel-footer">
          <button className="btn-show-more" onClick={() => setExpanded((s) => !s)}>
            {expanded ? "Show less" : `Show more (${items.length - 8} more)`}
          </button>
        </div>
      )}
    </>
  );
}
