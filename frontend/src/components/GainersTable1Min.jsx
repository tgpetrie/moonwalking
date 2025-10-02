import React, { useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { motion, useReducedMotion } from 'framer-motion';
import { FiInfo } from 'react-icons/fi';
import WatchStar from './WatchStar.jsx';
import { formatPercentage, truncateSymbol, formatPrice } from '../utils/formatters.js';
import { updateStreaks } from '../logic/streaks';

const sanitizeSymbol = (symbol = '') => String(symbol).replace(/-USD$/i, '');

const derivePrevPrice = (current, pct) => {
  if (!Number.isFinite(current) || !Number.isFinite(pct) || pct === 0) return null;
  return current / (1 + pct / 100);
};

const extractChange = (row) => {
  const sources = [
    row?.price_change_percentage_1min,
    row?.change,
    row?.change1m,
    row?.gain,
  ];
  const value = sources.find((v) => Number.isFinite(Number(v)));
  return Number.isFinite(Number(value)) ? Number(value) : 0;
};

export default function GainersTable1Min({
  rows = [],
  startRank,
  endRank,
  loading = false,
  error = null,
  onSelectCoin,
}) {
  const shouldReduceMotion = useReducedMotion();
  const [popStar, setPopStar] = useState(null);

  const slicedRows = useMemo(() => {
    const data = Array.isArray(rows) ? rows : [];
    const start = typeof startRank === 'number' ? Math.max(0, startRank - 1) : 0;
    const end = typeof endRank === 'number' ? Math.max(start, endRank) : data.length;
    return data.slice(start, end);
  }, [rows, startRank, endRank]);

  const normalizedRows = useMemo(() => slicedRows.map((item, idx) => {
    const symbol = sanitizeSymbol(item.symbol || item.pair || item.product_id || '');
    const price = Number(item.current_price ?? item.price ?? 0);
    const change = extractChange(item);
    return {
      ...item,
      rank: item.rank || (typeof startRank === 'number' ? startRank + idx : idx + 1),
      symbol,
      price,
      change,
      prevPrice: Number.isFinite(item.initial_price_1min) ? item.initial_price_1min : derivePrevPrice(price, change),
    };
  }), [slicedRows, startRank]);

  const streaks = updateStreaks('1m', normalizedRows.map((row) => ({ symbol: row.symbol })));
  const badgeSymbol = popStar;

  if (error) {
    return (
      <div className="w-full min-h-[320px] flex items-center justify-center text-sm text-red-300 bg-black/20 rounded-xl">
        Failed to load 1-minute gainers.
      </div>
    );
  }

  if (loading && normalizedRows.length === 0) {
    return (
      <div className="w-full min-h-[320px] flex items-center justify-center">
        <div className="animate-pulse text-muted font-mono">Loading 1-min gainers...</div>
      </div>
    );
  }

  if (!loading && normalizedRows.length === 0) {
    return (
      <div className="w-full min-h-[320px] flex items-center justify-center text-muted font-mono">
        No 1-minute gainers data available.
      </div>
    );
  }

  return (
    <div className="w-full h-full min-h-[320px] px-0">
      {normalizedRows.map((row, idx) => {
        const entranceDelay = shouldReduceMotion ? 0 : (idx % 12) * 0.035;
        const loopDelay = shouldReduceMotion ? 0 : (idx % 8) * 0.12;
        const streak = streaks(row.symbol);
        const change = Number(row.change || 0);
        const positive = Number.isFinite(change) && change >= 0;
        const prevPrice = Number.isFinite(row.prevPrice) ? row.prevPrice : null;

        const handleStar = (active) => {
          setPopStar(active ? row.symbol : null);
          setTimeout(() => setPopStar(null), 350);
        };

        const handleInfoClick = (event) => {
          event.preventDefault();
          event.stopPropagation();
          if (typeof onSelectCoin === 'function' && row.symbol) {
            onSelectCoin(row.symbol);
          }
        };

        const content = (
          <div className="grid relative z-10 grid-cols-[minmax(0,1fr)_152px_108px_44px] gap-x-4 items-start">
            <div className="flex items-center gap-4 min-w-0">
              <div className="flex items-center justify-center w-8 h-8 rounded-full font-bold text-sm shrink-0" style={{ background: 'rgba(254,164,0,0.28)', color: 'var(--pos)' }}>
                {row.rank}
              </div>
              <div className="min-w-0 flex items-center gap-3">
                <span className="font-headline font-bold text-white text-lg tracking-wide truncate">{truncateSymbol(row.symbol, 6)}</span>
                {Number.isFinite(streak) && streak > 1 && (
                  <span className="flex gap-[2px] ml-1" aria-label="streak indicator">
                    {Array.from({ length: Math.min(3, streak) }).map((_, dotIdx) => (
                      <span key={`dot-${row.symbol}-${dotIdx}`} className="w-1.5 h-1.5 rounded-full" style={{ background: '#C026D3' }} />
                    ))}
                  </span>
                )}
              </div>
            </div>

            <div className="w-[152px] pr-6 text-right">
              <div className="text-lg md:text-xl font-bold text-teal font-mono tabular-nums leading-none whitespace-nowrap">
                {Number.isFinite(row.price) ? formatPrice(row.price) : '—'}
              </div>
              <div className="text-sm leading-tight text-white/80 font-mono tabular-nums whitespace-nowrap">
                {prevPrice != null ? formatPrice(prevPrice) : '--'}
              </div>
            </div>

            <div className="w-[108px] pr-1.5 text-right align-top">
              <div className={`text-lg md:text-xl font-bold font-mono tabular-nums leading-none whitespace-nowrap ${positive ? 'text-orange' : 'text-neg'}`}>
                {positive && '+'}{formatPercentage(change)}
              </div>
            </div>

            <div className="w-[44px] flex flex-col items-end gap-2">
              <WatchStar
                productId={row.symbol}
                className={badgeSymbol === row.symbol ? 'animate-star-pop' : ''}
                onToggled={handleStar}
              />
              <button
                type="button"
                onClick={handleInfoClick}
                className="flex items-center justify-center w-6 h-6 transition focus:outline-none focus:ring-1 focus:ring-purple-500/60"
                aria-label={`Open ${row.symbol || 'token'} insights`}
              >
                <FiInfo className="w-4 h-4" />
              </button>
            </div>
          </div>
        );

        if (shouldReduceMotion) {
          return (
            <div key={row.symbol || idx} className="relative group block py-5 px-4 mb-1 rounded-xl bg-white/5 hover:bg-white/8 transition-colors">
              {content}
            </div>
          );
        }

        return (
          <motion.div
            key={row.symbol || idx}
            className="relative group block py-5 px-4 mb-1 rounded-xl bg-white/5 hover:bg-white/8 transition-colors"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.28, delay: entranceDelay }}
            whileHover={{ scale: 1.01 }}
          >
            <motion.div
              className="absolute inset-0 opacity-0 group-hover:opacity-100 rounded-xl"
              style={{ background: 'radial-gradient(circle at 30% 30%, rgba(254,164,0,0.16) 0%, rgba(254,164,0,0.05) 60%, transparent 100%)' }}
              animate={{ opacity: [0, 0.45, 0], scale: [0.96, 1.02, 0.96] }}
              transition={{ duration: 3.6, repeat: Infinity, delay: loopDelay, ease: 'easeInOut' }}
            />
            <div className="relative z-10">
              {content}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}

GainersTable1Min.propTypes = {
  rows: PropTypes.arrayOf(PropTypes.object),
  startRank: PropTypes.number,
  endRank: PropTypes.number,
  loading: PropTypes.bool,
  error: PropTypes.any,
  onSelectCoin: PropTypes.func,
};
