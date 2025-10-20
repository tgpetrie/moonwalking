import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { useGainers } from '../hooks/useData';
import RowActions from './tables/RowActions';
import '../styles/rows.css';

const LIMIT_COMPACT = 8;
const LIMIT_EXPANDED = 12;

const Card = ({ rank, symbol, price, changePct }) => {
  const pct = Number(changePct ?? 0);
  const priceNum = typeof price === 'number' ? price : Number(price);
  return (
    <div className="relative rounded-2xl bg-black/40 border border-white/5 px-4 py-4 flex flex-col gap-3 hover:border-white/15 transition-colors">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-orange/30 text-orange font-semibold text-sm">
            {rank}
          </div>
          <div className="min-w-0">
            <div className="font-headline text-lg tracking-wide truncate">{symbol}</div>
            <div className="text-sm text-white/70 tabular-nums">
              ${Number.isFinite(priceNum) ? (priceNum < 1 ? priceNum.toFixed(4) : priceNum.toFixed(2)) : '—'}
            </div>
          </div>
        </div>
        <div className={`text-right font-mono text-lg tabular-nums ${pct >= 0 ? 'text-gain' : 'text-loss'}`}>
          {pct >= 0 ? '+' : ''}{Number.isFinite(pct) ? pct.toFixed(3) : '0.000'}%
        </div>
      </div>
      <div className="flex items-center justify-end">
        <RowActions symbol={symbol} price={priceNum} />
      </div>
    </div>
  );
};

Card.propTypes = {
  rank: PropTypes.number.isRequired,
  symbol: PropTypes.string.isRequired,
  price: PropTypes.number,
  changePct: PropTypes.number,
};

export default function OneMinGainersColumns({ expanded = false }) {
  const { rows, loading } = useGainers('1m');
  const limit = expanded ? LIMIT_EXPANDED : LIMIT_COMPACT;
  const sliced = useMemo(() => rows.slice(0, limit), [rows, limit]);

  const prepared = useMemo(
    () => sliced.map((item, idx) => ({ ...item, rank: idx + 1 })),
    [sliced]
  );

  const left = prepared.filter((_, idx) => idx % 2 === 0);
  const right = prepared.filter((_, idx) => idx % 2 === 1);

  const renderColumn = (entries) => (
    <div className="flex flex-col gap-3">
      {entries.map((item, idx) => (
        <Card key={item.symbol} rank={item.rank} symbol={item.symbol} price={item.price} changePct={item.changePct} />
      ))}
      {(!entries.length && loading) &&
        Array.from({ length: limit / 2 }).map((_, i) => (
          <div key={`skeleton-${i}`} className="rounded-2xl bg-white/5 h-24 animate-pulse" />
        ))}
    </div>
  );

  if (!sliced.length && loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Array.from({ length: 2 }).map((_, col) => (
          <div key={col} className="flex flex-col gap-3">
            {Array.from({ length: limit / 2 }).map((__, i) => (
              <div key={`${col}-${i}`} className="rounded-2xl bg-white/5 h-24 animate-pulse" />
            ))}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {renderColumn(left)}
      {renderColumn(right)}
    </div>
  );
}

OneMinGainersColumns.propTypes = {
  expanded: PropTypes.bool,
};
