```jsx
import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { useWebSocket } from '../context/websocketcontext.jsx';
import GainersTable1Min from './GainersTable1Min.clean.jsx';

const sanitizeSymbol = (symbol = '') => String(symbol).replace(/-USD$/i, '');

const uniqBySymbol = (rows = []) => {
  const seen = new Set();
  const out = [];
  for (const it of rows) {
    const sym = sanitizeSymbol(it?.symbol || it?.pair || it?.product_id || '');
    if (!sym) continue;
    if (seen.has(sym)) continue;
    seen.add(sym);
    out.push(it);
  };
export default function OneMinColumn({ side = 'left', expanded = false, onSelectCoin }) {
  const { gainersTop20, latestData } = useWebSocket();

  const normalized = useMemo(() => {
    const base = Array.isArray(gainersTop20) ? uniqBySymbol(gainersTop20) : [];
    return base.map((item, idx) => ({
      ...item,
      rank: item.rank || idx + 1,
      symbol: sanitizeSymbol(item.symbol || item.pair || item.product_id || ''),
    }));
  }, [gainersTop20]);

  const { left, right } = useMemo(() => {
    const targetTotal = expanded ? 12 : 8;
    const available = normalized.length;
    const total = Math.min(targetTotal, available);
    const top = normalized.slice(0, total);

    const leftArr = [];
    const rightArr = [];
    for (let i = 0; i < top.length; i += 1) {
      if (i % 2 === 0) leftArr.push(top[i]);
      else rightArr.push(top[i]);
    }
    return { left: leftArr, right: rightArr };
  }, [normalized, expanded]);

  const rows = side === 'left' ? left : right;

  // No seeded/derived markers via websocket; allowEmpty only if rows exist or in DEV we may tolerate empty
  const allowEmpty = Boolean(import.meta?.env?.DEV && !rows?.length);

  return (
    <div className="px-4 py-2">
      <GainersTable1Min
        rows={rows}
        loading={false}
        error={null}
        seeded={false}
        allowEmpty={allowEmpty}
        onSelectCoin={onSelectCoin}
      />
    </div>
  );
}

OneMinColumn.propTypes = {
  side: PropTypes.oneOf(['left', 'right']),
  expanded: PropTypes.bool,
  onSelectCoin: PropTypes.func,
};

```