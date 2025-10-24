import PropTypes from 'prop-types';
import React, { useMemo } from 'react';
import StatusNote from './StatusNote.jsx';
import AnimatedRow from './shared/AnimatedRow.jsx';
import { useDataClock } from '../hooks/useDataClock.js';
import { useLiveData } from '../hooks/useLiveData.js';

const ENDPOINT = '/api/component/gainers-table';

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
        item?.price_change_percentage_3min ??
        item?.price_change_percentage ??
        item?.pct ??
        item?.delta ??
        0,
      price: item?.price ?? item?.current_price ?? item?.current ?? item?.last ?? item?.close ?? 0,
    };
  });
};

export default function GainersTable({ rows: rowsProp, loading = false, error = null, onRowClick }) {
  const heartbeat = useDataClock(5000);
  const { data, changedMap, error: fetchError } = useLiveData(
    ENDPOINT,
    [heartbeat],
    'symbol',
    selectRows
  );

  const rows = useMemo(() => {
    if (Array.isArray(rowsProp) && rowsProp.length > 0) return rowsProp;
    return data.slice(0, 20);
  }, [rowsProp, data]);

  if (loading) {
    return <StatusNote state="loading" message="Loading 3-min gainers…" />;
  }

  if ((error || fetchError) && rows.length === 0) {
    return <StatusNote state="error" message="Unable to load 3-min gainers" />;
  }

  if (rows.length === 0) {
    return <StatusNote state="empty" message="No 3-min data available" />;
  }

  return (
    <div className="relative overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-gray-500 uppercase text-xs">
            <th className="px-3 py-1 text-left">Symbol</th>
            <th className="px-3 py-1 text-right">3-min Δ%</th>
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
              changeLabel="3-min Δ%"
              onRowClick={onRowClick}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

GainersTable.propTypes = {
  rows: PropTypes.array,
  loading: PropTypes.bool,
  error: PropTypes.any,
  onRowClick: PropTypes.func,
};
