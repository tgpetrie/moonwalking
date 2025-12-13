import { useMemo } from "react";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import { tickerFromSymbol } from "../utils/format";
import { useDataFeed } from "../hooks/useDataFeed";
import { TokenRowUnified } from "./TokenRowUnified";

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

export default function WatchlistPanel() {
  // useWatchlist wraps useContext(WatchlistContext) to keep panel in sync with starred items.
  const { items, toggle: toggleWatchlist } = useWatchlist();
  const { data } = useDataFeed();
  const payload = data?.data ?? data ?? {};

  const liveBySymbol = useMemo(() => {
    const latest = payload.latest_by_symbol || {};
    const merged = {};
    Object.entries(latest).forEach(([k, v]) => {
      merged[String(k).toUpperCase()] = v;
    });
    return merged;
  }, [payload]);

  const watchlistTokens = useMemo(() => {
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
        current_price: livePrice,
        previous_price: baseline,
        change_1m: pct ?? 0,
      };
    });
  }, [items, liveBySymbol]);

  if (!items.length) {
    return null;
  }

  const handleToggleWatchlist = (symbol) => {
    if (!symbol) return;
    toggleWatchlist({ symbol });
  };

  return (
    <div className="bh-panel bh-panel-full">
      <div className="bh-table">
        {watchlistTokens.map((token, index) => (
          <TokenRowUnified
            key={token.key ?? `${token.symbol}-${index}`}
            token={token}
            rank={index + 1}
            changeField="change_1m"
            onToggleWatchlist={handleToggleWatchlist}
            isWatchlisted
          />
        ))}
      </div>
    </div>
  );
}
