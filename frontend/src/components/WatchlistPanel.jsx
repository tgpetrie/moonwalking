import { useMemo } from "react";
import { AnimatePresence, motion } from "framer-motion";
import AnimatedTokenRow from "./AnimatedTokenRow.jsx";
import { rowVariants, listVariants } from "./motionVariants";
import StatusGate from "./ui/StatusGate";
import SkeletonTable from "./ui/SkeletonTable";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import { tickerFromSymbol } from "../utils/format";
import { useDataFeed } from "../hooks/useDataFeed";

function deltaPct(baseline, current) {
  const base = Number(baseline);
  const curr = Number(current);
  if (!Number.isFinite(base) || !Number.isFinite(curr) || base === 0) return null;
  return ((curr - base) / base) * 100;
}

const pickPrice = (source = {}) => {
  if (!source) return null;
  return (
    source.current_price ??
    source.currentPrice ??
    source.price ??
    source.last_price ??
    source.latest_price ??
    null
  );
};

export default function WatchlistPanel({ onInfo }) {
  const { items, remove } = useWatchlist();
  const { data, isLoading } = useDataFeed();
  const payload = data?.data ?? data ?? {};

  const liveBySymbol = useMemo(() => {
    const latest = payload.latest_by_symbol || {};
    const merged = {};
    Object.entries(latest).forEach(([k, v]) => {
      merged[String(k).toUpperCase()] = v;
    });
    return merged;
  }, [payload]);

  const handleToggleWatchlist = (symbol) => {
    if (!remove) return;
    remove(symbol);
  };

  const rows = useMemo(() => {
    if (!items.length) return [];

    return items.map((entry, index) => {
      const canonSymbol = tickerFromSymbol(entry.symbol) || entry.symbol;
      const live = liveBySymbol[canonSymbol] || {};
      const livePrice = pickPrice(live) ?? entry.current ?? entry.baseline ?? null;
      const baseline = entry.baseline ?? entry.current ?? pickPrice(live);
      const pct = deltaPct(baseline, livePrice);

      return {
        key: `${canonSymbol}-${index}`,
        rank: index + 1,
        symbol: canonSymbol,
        currentPrice: livePrice,
        previousPrice: baseline,
        percentChange: pct ?? 0,
      };
    });
  }, [items, liveBySymbol]);

  const panelStatus = rows.length > 0 ? "ready" : isLoading ? "loading" : "empty";

  return (
    <StatusGate
      status={panelStatus}
      skeleton={<SkeletonTable rows={3} />}
      empty={<p className="bh-watchlist-empty">Star a token in the tables above to pin it here.</p>}
    >
      <div className="bh-table">
        <motion.div initial="hidden" animate="visible" exit="exit" variants={listVariants}>
          <AnimatePresence>
            {rows.map((row) => {
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
                <a key={row.key} href={href} target="_blank" rel="noreferrer" className="bh-row-link">
                  <AnimatedTokenRow
                    layout
                    variants={rowVariants}
                    rank={row.rank}
                    symbol={row.symbol}
                    name={null}
                    currentPrice={row.currentPrice}
                    previousPrice={row.previousPrice}
                    percentChange={row.percentChange}
                    onToggleWatchlist={() => handleToggleWatchlist(row.symbol)}
                    onInfo={() => onInfo && onInfo(row.symbol)}
                    isWatchlisted={true}
                  />
                </a>
              );
            })}
          </AnimatePresence>
        </motion.div>
      </div>
    </StatusGate>
  );
}
