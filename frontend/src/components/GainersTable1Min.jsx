import PropTypes from 'prop-types';
import React, { useMemo } from 'react';
import StatusNote from './StatusNote.jsx';
import AnimatedRow from './shared/AnimatedRow.jsx';
import { useDataClock } from '../hooks/useDataClock.js';
import { useLiveData } from '../hooks/useLiveData.js';

const ENDPOINT = '/api/component/gainers-table-1min';

const selectRows = (payload) => {
  const source = Array.isArray(payload?.data)
    ? payload.data
    : Array.isArray(payload?.rows)
    ? payload.rows
    : Array.isArray(payload?.gainers)
    ? payload.gainers
    : [];
  return source.map((item, idx) => {
    const symbol = String(
      item?.symbol ?? item?.pair ?? item?.asset ?? item?.product_id ?? item?.ticker ?? ''
    ).replace(/-USD$/i, '');
    return {
      ...item,
      rank: item?.rank ?? idx + 1,
      symbol,
      change:
        item?.change ??
        item?.gain ??
        item?.price_change_percentage_1min ??
        item?.price_change_percentage ??
        item?.pct ??
        item?.delta ??
        0,
      price: item?.price ?? item?.current_price ?? item?.current ?? item?.last ?? item?.close ?? 0,
    };
  });
};

export default function GainersTable1Min({ onRowClick }) {
  const heartbeat = useDataClock(3000);
  const { data, changedMap, raw, error } = useLiveData(ENDPOINT, [heartbeat], 'symbol', selectRows);

  const seeded = Boolean(raw?.seeded || raw?.swr?.seed || (raw && raw?.swr?.source === 'fixture-seed'));

  const rows = useMemo(() => data.slice(0, 20), [data]);

  if (error && rows.length === 0) {
    return <StatusNote state="error" message="Unable to load 1-min gainers" />;
  }

  if (rows.length === 0) {
    return <StatusNote state="loading" message="Loading 1-min gainers…" />;
  }

  return (
    <div className="relative overflow-x-auto">
      {seeded && (
        <span className="absolute top-2 right-4 text-[10px] px-2 py-0.5 rounded-full bg-purple-700/60 text-white tracking-wide font-semibold uppercase">
          Dev Seed
        </span>
      )}
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-gray-500 uppercase text-xs">
            <th className="px-3 py-1 text-left">Symbol</th>
            <th className="px-3 py-1 text-right">1-min Δ%</th>
            <th className="px-3 py-1 text-right">Price</th>
            <th className="px-3 py-1 text-right hidden sm:table-cell">Cadence</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((coin, index) => (
            <AnimatedRow
              key={coin.symbol || index}
              coin={coin}
              index={index}
              changeDirection={changedMap.get(coin.symbol)}
              changeLabel="Live"
              onRowClick={onRowClick}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

GainersTable1Min.propTypes = {
  onRowClick: PropTypes.func,
};
