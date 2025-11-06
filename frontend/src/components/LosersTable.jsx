import React, { useEffect, useState } from 'react';
import { API_ENDPOINTS, fetchData } from '../api.js';
import { normalizeTableRow } from '../lib/adapters';
import TokenRow from './TokenRow.jsx';

export default function LosersTable({ refreshTrigger }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    const fetchRows = async () => {
      setLoading(true);
      try {
        const res = await fetchData(API_ENDPOINTS.losersTable);
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
        console.error('LosersTable fetch error', e);
        if (mounted) setError(e?.message || String(e));
      } finally {
        if (mounted) setLoading(false);
      }
    };
    fetchRows();
    const id = setInterval(fetchRows, 30_000);
    return () => { mounted = false; clearInterval(id); };
  }, [refreshTrigger]);

  if (loading && rows.length === 0) return <div className="text-center py-8">Loading...</div>;
  if (!loading && error && rows.length === 0) return <div className="text-center py-8">Error loading losers</div>;
  if (!loading && !error && rows.length === 0) return <div className="text-center py-8">No losers data</div>;

  return (
    <div className="overflow-auto w-full">
      <table className="w-full table-fixed border-collapse">
        <tbody>
          {rows.map((r, idx) => (
            <TokenRow
              key={r.symbol || idx}
              rank={r.rank}
              symbol={r.symbol}
              currentPrice={r.currentPrice}
              previousPrice={r.previousPrice}
              priceChange1min={r.priceChange1min}
              priceChange3min={r.priceChange3min}
              isGainer={false}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
