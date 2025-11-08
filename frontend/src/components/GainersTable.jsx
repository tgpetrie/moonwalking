import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchData } from '../api.js';
import { normalizeTableRow } from '../lib/adapters';
import TokenRow from './TokenRow.jsx';

/**
 * 3‑minute gainers list using adapter-normalized rows and unified TokenRow.
 * Keeps polling behavior from the original component but renders using
 * the hardened TokenRow to ensure consistent click/info/star behavior.
 */
export default function GainersTable({ refreshTrigger, rows: externalRows, loading: externalLoading, error: externalError, onInfo }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const usingExternal = Array.isArray(externalRows);

  useEffect(() => {
    if (usingExternal) return; // parent-provided path
    let mounted = true;
    const fetchRows = async () => {
      setLoading(true);
      try {
        const res = await fetchData(API_ENDPOINTS.gainersTable);
        const data = (res && Array.isArray(res.data)) ? res.data : [];
        const normalized = data.map((r, i) => {
          const base = normalizeTableRow(r || {});
          return {
            rank: base.rank ?? (i + 1),
            symbol: base.symbol,
            currentPrice: base.currentPrice ?? (r.current_price ?? r.price ?? null),
            previousPrice: r.previous_price ?? null,
            priceChange3min: r.price_change_percentage_3min ?? r.change_pct_3min ?? null,
            trendDirection: base.trendDirection,
            trendScore: base.trendScore,
            trendStreak: base.trendStreak,
            _raw: r,
          };
        }).slice(0, 8);
        if (mounted) setRows(normalized);
      } catch (e) {
        console.error('GainersTable fetch error', e);
        if (mounted) setError(e?.message || String(e));
      } finally {
        if (mounted) setLoading(false);
      }
    };
    fetchRows();
    const id = setInterval(fetchRows, 30_000);
    return () => { mounted = false; clearInterval(id); };
  }, [refreshTrigger, usingExternal]);

  const finalRows = usingExternal ? externalRows : rows;
  const finalLoading = usingExternal ? !!externalLoading : loading;
  const finalError = usingExternal ? externalError : error;

  if (finalLoading && finalRows.length === 0) return <div className="text-center py-8">Loading...</div>;
  if (!finalLoading && finalError && finalRows.length === 0) return <div className="text-center py-8">Backend unavailable (no data)</div>;
  if (!finalLoading && !finalError && finalRows.length === 0) return <div className="text-center py-8">No gainers data</div>;

  return (
    <div className="overflow-auto w-full">
      <div className="flex flex-col gap-1">
        {finalRows.map((r, idx) => (
          <TokenRow
            key={r.symbol || idx}
            index={typeof r.rank === 'number' ? r.rank - 1 : idx}
            symbol={r.symbol}
            price={r.currentPrice ?? r.current_price ?? r.price ?? null}
            prevPrice={r.previousPrice ?? r.previous_price ?? null}
            changePct={
              r.priceChange3min ?? r.priceChange1min ?? r.price_change_3min ?? r.price_change_percentage_3min ?? null
            }
            side={r.isGainer === false ? 'loss' : 'gain'}
            onInfo={onInfo}
          />
        ))}
      </div>
    </div>
  );
}
