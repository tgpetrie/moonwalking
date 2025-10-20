import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { useWebSocket } from '../context/websocketcontext.jsx';
import GainersTable1Min from './GainersTable1Min.jsx';

export default function OneMinGainersColumns({ expanded = false, onSelectCoin }) {
  const { gainersTop20 } = useWebSocket();

  const { left, right, ranges } = useMemo(() => {
    const total = expanded ? 12 : 8;
    const half = Math.ceil(total / 2);
    const leftRange = { start: 1, end: half }; // ranks are 1-indexed; end exclusive in child logic
    const rightRange = { start: half + 1, end: total };
    const top = gainersTop20.slice(0, total);
    return {
      left: top.slice(0, half),
      right: top.slice(half, total),
      ranges: { left: leftRange, right: rightRange },
    };
  }, [gainersTop20, expanded]);

  // Ranges are passed via startRank/endRank; no additional local slice offsets needed

  const hasRight = right && right.length > 0;

  return (
    <div className="tables-grid mt-3">
      <div className={"table-card " + (!hasRight ? 'sm:col-span-2' : '')}>
        <GainersTable1Min
          rows={left}
      startRank={ranges.left.start}
      endRank={ranges.left.end}
          hideShowMore
          onSelectCoin={onSelectCoin}
        />
      </div>
    {hasRight && (
      <div className="table-card">
          <GainersTable1Min
            rows={right}
        startRank={ranges.right.start}
        endRank={ranges.right.end}
            hideShowMore
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
