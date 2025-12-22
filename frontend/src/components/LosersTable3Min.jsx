import React, { useState, useMemo, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useHybridLive as useHybridLiveNamed } from "../hooks/useHybridLive";
import { TableSkeletonRows } from "./TableSkeletonRows";
import { TokenRowUnified } from "./TokenRowUnified";
import { normalizeTableRow } from "../lib/adapters";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import { baselineOrNull } from "../utils/num.js";

const buildRowKey = (row, index) => {
  const base = row.symbol ?? row.base ?? row.ticker ?? `row-${index}`;
  return `${base}-${index}`;
};

export default function LosersTable3Min({ tokens: tokensProp, loading: loadingProp, onInfo, onToggleWatchlist, watchlist = [] }) {
  const { has, add, remove } = useWatchlist();

  // Support both prop-based (new centralized approach) and hook-based (legacy) usage
  const { data: payload = {} } = useHybridLiveNamed({
    endpoint: "/api/component/losers-table",
    eventName: "losers3m",
    pollMs: 8000,
    initial: [],
  });

  const isLoading = loadingProp !== undefined ? loadingProp : false;

  // Use props if provided, otherwise fall back to hook data
  const mapped = useMemo(() => {
    if (tokensProp) {
      // Use prop tokens - they should already be normalized
      return tokensProp.map((row) => ({
        symbol: row.symbol,
        current_price: row.price ?? row.current_price,
        previous_price: baselineOrNull(row.initial_price_3min ?? row.previous_price ?? null),
        price_change_percentage_3min: row.changePct ?? row.price_change_percentage_3min ?? row.change_3m ?? null,
        isGainer: false, // PURPLE accent
        price: row.price ?? row.current_price,
      }));
    }

    // Fall back to hook data
    const raw = Array.isArray(payload?.data) ? payload.data : [];
    return raw.map((row) => {
      const nr = normalizeTableRow(row);
      return {
        symbol: nr.symbol ?? row.symbol,
        current_price: nr.currentPrice ?? row.current_price,
        previous_price: baselineOrNull(row.initial_price_3min ?? nr._raw?.initial_price_3min ?? null),
        price_change_percentage_1min: undefined,
        price_change_percentage_3min: row.price_change_percentage_3min ?? nr._raw?.price_change_percentage_3min ?? null,
        isGainer: false, // PURPLE accent
      };
    });
  }, [tokensProp, payload]);

  const [expanded, setExpanded] = useState(false);
  const [pulseOn, setPulseOn] = useState(false);
  const filtered = useMemo(
    () =>
      mapped
        .map((row) => ({
          ...row,
          change_3m: row.price_change_percentage_3min ?? row.change_3m ?? row._pct ?? row.pct ?? 0,
        }))
        .filter((row) => Number(row.change_3m) < 0)
        .sort((a, b) => Number(a.change_3m) - Number(b.change_3m)),
    [mapped]
  );
  const visible = useMemo(() => (expanded ? filtered : filtered.slice(0, 8)), [filtered, expanded]);
  const refreshSig = useMemo(() => {
    return visible
      .map((row) => `${row.symbol}:${Number(row.change_3m ?? 0).toFixed(4)}`)
      .join("|");
  }, [visible]);
  useEffect(() => {
    if (!visible.length) return;
    setPulseOn(true);
    const timer = setTimeout(() => setPulseOn(false), 700);
    return () => clearTimeout(timer);
  }, [refreshSig, visible.length]);

  const hasData = filtered.length > 0;

  const isStarred = (symbol) => {
    if (!symbol) return false;
    return watchlist.includes(symbol) || has(symbol);
  };

  const handleToggleStar = (symbol, price) => {
    if (!symbol) return;
    if (onToggleWatchlist) {
      onToggleWatchlist(symbol, price ?? null);
      return;
    }
    if (has(symbol)) {
      remove(symbol);
    } else {
      add({ symbol, price });
    }
  };

  const handleInfo = (symbol) => {
    if (!symbol) return;
    if (onInfo) {
      onInfo(symbol);
    } else {
      window.dispatchEvent(new CustomEvent("openInfo", { detail: symbol }));
    }
  };

  const buildCoinbaseUrl = (symbol) => {
    if (!symbol) return "#";
    let pair = symbol;
    if (!/-USD$|-USDT$|-PERP$/i.test(pair)) {
      pair = `${pair}-USD`;
    }
    return `https://www.coinbase.com/advanced-trade/spot/${pair}`;
  };

  // Loading skeleton state
  if (isLoading && !hasData) {
    return (
      <div className="losers-table">
        <div className="bh-panel bh-panel-half">
          <div className="bh-table">
            {/* Render div-based skeleton rows to match TokenRowUnified */}
            <TableSkeletonRows columns={5} rows={6} renderAs="div" />
          </div>
        </div>
      </div>
    );
  }

  // No data state
  if (!isLoading && !hasData) {
    return (
      <div className="losers-table">
        <div className="bh-panel bh-panel-half">
          <div className="bh-table">
            <div className="token-row token-row--empty">
              <div style={{ width: "100%", textAlign: "center", opacity: 0.7, padding: "0.75rem 0" }}>
                No 3-minute losers to show right now.
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="losers-table">
      <div className="bh-panel bh-panel-half">
        <div className="bh-table">
          <AnimatePresence initial={false}>
            {visible.map((tokenProps, idx) => {
              const rowKey = buildRowKey(tokenProps, idx);
              return (
                <motion.div key={rowKey} layout="position">
                  <TokenRowUnified
                    token={{ ...tokenProps, change_3m: tokenProps.change_3m ?? tokenProps.price_change_percentage_3min ?? tokenProps._pct ?? tokenProps.pct ?? 0 }}
                    rank={idx + 1}
                    changeField="change_3m"
                    side="loser"
                    onInfo={() => handleInfo(tokenProps.symbol)}
                    onToggleWatchlist={() => handleToggleStar(tokenProps.symbol, tokenProps.current_price ?? tokenProps.price)}
                    isWatchlisted={isStarred(tokenProps.symbol)}
                    pulse={pulseOn}
                    pulseDelayMs={idx * 18}
                  />
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      </div>

      {!expanded && mapped.length > 8 && (
        <div className="panel-footer">
          <button className="btn-show-more" onClick={() => setExpanded(true)}>
            Show more
          </button>
        </div>
      )}
    </div>
  );
}
