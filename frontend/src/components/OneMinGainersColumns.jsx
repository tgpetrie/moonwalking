import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { useWebSocket } from '../context/websocketcontext.jsx';
import GainersTable1Min from './GainersTable1Min.clean.jsx';

const POLL_MS = Number.parseInt(import.meta?.env?.VITE_POLL_MS ?? '30000', 10);

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
  }
  return out;
};

export default function OneMinGainersColumns({ expanded = false, onSelectCoin, onOpenSymbol, side = null, compact = false }) {
  const { gainersTop20, gainers3mTop, latestData } = useWebSocket();
  const loading = false;
  const error = null;
  const raw = latestData?.raw ?? null;
  const [localExpanded, setLocalExpanded] = React.useState(false);

  // Prefer 1-min feed; fallback to 3-min gainers for dev / cold starts
  const allRows = useMemo(() => {
    if (Array.isArray(gainersTop20) && gainersTop20.length > 0) return gainersTop20;
    if (Array.isArray(gainers3mTop) && gainers3mTop.length > 0) return gainers3mTop;
    return [];
  }, [gainersTop20, gainers3mTop]);

  const normalized = useMemo(() => {
    const base = Array.isArray(allRows) ? uniqBySymbol(allRows) : [];
    return base.map((item, idx) => ({
      ...item,
      rank: item.rank || idx + 1,
      symbol: sanitizeSymbol(item.symbol || item.pair || item.product_id || ''),
    }));
  }, [allRows]);

  const { left, right } = useMemo(() => {
    const baseLimit = 8;
    const expandLimit = 16;
    const targetTotal = localExpanded || expanded ? expandLimit : baseLimit;
    const available = normalized.length;
    const total = Math.min(targetTotal, available);
    const top = normalized.slice(0, total);

    // Interleave evenly: even indexes → left, odd → right
    const leftArr = [];
    const rightArr = [];
    for (let i = 0; i < top.length; i += 1) {
      if (i % 2 === 0) leftArr.push(top[i]);
      else rightArr.push(top[i]);
    }

    // Defensive dedupe: ensure left/right do not share the same symbol
    const seen = new Set();
    const compact = (arr) => arr.filter((it) => {
      const s = sanitizeSymbol(it?.symbol || it?.pair || it?.product_id || '');
      if (!s) return false;
      if (seen.has(s)) return false;
      seen.add(s);
      return true;
    });

    return {
      left: compact(leftArr),
      right: compact(rightArr),
    };
  }, [normalized, expanded, localExpanded]);

  // decide which rows to render based on side prop
  const seeded = Boolean(import.meta?.env?.DEV && (raw?.seeded || raw?.swr?.source === 'fixture-seed'));
  const derived = Boolean(import.meta?.env?.DEV && (raw?.swr?.source === 'derived-from-3min'));
  const allowEmpty = Boolean(seeded || derived || import.meta?.env?.DEV);

  // If side is provided, render just that column; otherwise render both columns side-by-side
  if (side === 'left' || side === 'right') {
    const rows = side === 'left' ? left : right;
    return (
      <div className="w-full h-full min-h-[320px]">
        <GainersTable1Min
          rows={rows}
          startRank={1}
          endRank={rows.length}
          loading={loading}
          error={error}
          seeded={seeded}
          allowEmpty={allowEmpty}
          onSelectCoin={onSelectCoin}
          onOpenSymbol={onOpenSymbol}
          compact={compact}
        />
      </div>
    );
  }

  return (
    <div className="w-full">
      <div className="w-full grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <GainersTable1Min
            rows={left}
            startRank={1}
            endRank={left.length}
            loading={loading}
            error={error}
            seeded={seeded}
            allowEmpty={allowEmpty}
            onSelectCoin={onSelectCoin}
            onOpenSymbol={onOpenSymbol}
            compact={compact}
          />
        </div>
        <div>
          <GainersTable1Min
            rows={right}
            startRank={left.length + 1}
            endRank={left.length + right.length}
            loading={loading}
            error={error}
            seeded={seeded}
            allowEmpty={allowEmpty}
            onSelectCoin={onSelectCoin}
            onOpenSymbol={onOpenSymbol}
            compact={compact}
          />
        </div>
      </div>

      {/* show more / show less matching MoverTable behavior */}
      {Array.isArray(normalized) && normalized.length > 8 && (
        <div className="w-full mt-3 flex justify-center">
          <button
            type="button"
            onClick={() => setLocalExpanded((s) => !s)}
            className="text-sm font-medium text-slate-200 bg-white/5 hover:bg-white/10 px-3 py-1 rounded-md"
            aria-expanded={localExpanded}
          >
            {localExpanded ? 'Show Less' : `Show more (${Math.min(normalized.length, 16)} max)`}
          </button>
        </div>
      )}
    </div>
  );
}

OneMinGainersColumns.propTypes = {
  expanded: PropTypes.bool,
  onSelectCoin: PropTypes.func,
  onOpenSymbol: PropTypes.func,
  side: PropTypes.oneOf(['left', 'right', null]),
  compact: PropTypes.bool,
};
