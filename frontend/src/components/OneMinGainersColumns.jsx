import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import useGainersData from '../hooks/useGainersData.jsx';
import GainersTable1Min from './GainersTable1Min.jsx';

const sanitizeSymbol = (symbol = '') => String(symbol).replace(/-USD$/i, '');

export default function OneMinGainersColumns({ expanded = false, onSelectCoin }) {
  const { rows: allRows, loading, error } = useGainersData({ window: '1min', pollInterval: 5000 });

  const normalized = useMemo(() => (
    Array.isArray(allRows)
      ? allRows.map((item, idx) => ({
          ...item,
          rank: item.rank || idx + 1,
          symbol: sanitizeSymbol(item.symbol || item.pair || item.product_id || ''),
        }))
      : []
  ), [allRows]);

  const { left, right, ranges } = useMemo(() => {
    const total = expanded ? 12 : 8;
    const half = Math.ceil(total / 2);
    const leftRange = { start: 1, end: half };
    const rightRange = { start: half + 1, end: total };
    const top = normalized.slice(0, total);
    return {
      left: top.slice(0, half),
      right: top.slice(half, total),
      ranges: { left: leftRange, right: rightRange },
    };
  }, [normalized, expanded]);

  const hasRight = right && right.length > 0;

  return (
    <div className="tables-grid mt-3">
      <div className={"table-card " + (!hasRight ? 'sm:col-span-2' : '')}>
        <GainersTable1Min
          rows={left}
          startRank={ranges.left.start}
          endRank={ranges.left.end}
          loading={loading}
          error={error}
          onSelectCoin={onSelectCoin}
        />
      </div>
      {hasRight && (
        <div className="table-card">
          <GainersTable1Min
            rows={right}
            startRank={ranges.right.start}
            endRank={ranges.right.end}
            loading={loading}
            error={error}
            onSelectCoin={onSelectCoin}
          />
        </div>
      )}
    </div>
  );
}

OneMinGainersColumns.propTypes = {
  expanded: PropTypes.bool,
  onSelectCoin: PropTypes.func,
};
