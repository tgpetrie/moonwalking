import { useCallback, useEffect, useMemo, useState } from 'react';
import TokenRow from './TokenRow.jsx';
import { normalizeTableRow } from '../lib/adapters';
import {
  API_ENDPOINTS,
  fetchData,
  getWatchlist,
  addToWatchlist,
  removeFromWatchlist,
} from '../api.js';

const DEFAULT_REFRESH_MS = 10000;

export default function GainersTable({ refreshMs = DEFAULT_REFRESH_MS }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [watchlist, setWatchlist] = useState([]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const list = await getWatchlist();
        if (active && Array.isArray(list)) {
          setWatchlist(list);
        }
      } catch (err) {
        console.error('[GainersTable] failed to hydrate watchlist', err);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer;

    // prefer adapter normalization to keep shapes consistent across components
    const normalizeRows = (data = []) => data.map((row) => {
      const norm = normalizeTableRow(row || {});
      return {
        ...row,
        symbol: (norm.symbol || '').toUpperCase().replace(/-USD$/, ''),
        current_price: (norm.currentPrice != null ? Number(norm.currentPrice) : null),
        price_change_percentage_3min: (norm.priceChange1h != null ? Number(norm.priceChange1h) : 0),
        // include canonical volume fields for downstream components
        volume_24h: Number(norm.volume24h || 0),
        volume_change_pct: Number(norm.volumeChangePct || 0),
      };
    });

    const fetchRows = async () => {
      try {
        const endpoint = API_ENDPOINTS.gainersTable3Min || API_ENDPOINTS.gainersTable;
        const response = await fetchData(endpoint);
        if (cancelled) return;
        const dataset = Array.isArray(response?.data) ? response.data : [];
        const normalized = normalizeRows(dataset);
        setRows(normalized);
        // Dev: log samples so we can verify UI data presence quickly
        try {
          if (import.meta.env && import.meta.env.DEV && typeof console !== 'undefined') {
            console.debug('[GainersTable] fetched dataset sample', dataset.slice(0,3));
            console.debug('[GainersTable] normalized sample', normalized.slice(0,3));
          }
        } catch (e) {}
        setError(null);
      } catch (err) {
        if (cancelled) return;
        console.error('[GainersTable] fetch error', err);
        setError('Unable to load gainers right now.');
      } finally {
        if (!cancelled) {
          setLoading(false);
          timer = setTimeout(fetchRows, refreshMs);
        }
      }
    };

    fetchRows();

    return () => {
      cancelled = true;
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [refreshMs]);

  const handleToggleWatch = useCallback(
    async (symbol) => {
      if (!symbol) return;
      try {
        const exists = watchlist.some((item) => item?.symbol === symbol);
        const row = rows.find((entry) => entry.symbol === symbol);
        const next = exists
          ? await removeFromWatchlist(symbol)
          : await addToWatchlist(symbol, row?.current_price ?? row?.price ?? null);
        setWatchlist(next);
      } catch (err) {
        console.error('[GainersTable] watchlist toggle failed', err);
      }
    },
    [rows, watchlist],
  );

  const normalizedRows = useMemo(() => rows.slice(0, 20), [rows]);

  const renderBody = () => {
    if (loading) {
      return (
        <tr>
          <td colSpan={4} className="py-6 text-center text-dim text-[13px] animate-pulse">
            Loading gainers…
          </td>
        </tr>
      );
    }

    if (error) {
      return (
        <tr>
          <td colSpan={4} className="py-6 text-center text-pink text-[13px]">
            {error}
          </td>
        </tr>
      );
    }

    if (!normalizedRows.length) {
      return (
        <tr>
          <td colSpan={4} className="py-6 text-center text-dim text-[13px]">
            No data yet
          </td>
        </tr>
      );
    }

    return normalizedRows.map((row, index) => {
      const isWatched = watchlist.some((item) => item?.symbol === row.symbol);
      return (
        <TokenRow
          key={`${row.symbol || 'row'}-${index}`}
          {...row}
          isWatched={isWatched}
          isGainer={true}
          onToggleWatch={handleToggleWatch}
          volume={row.volume_24h}
          displayVolumeAsPrice={true}
        />
      );
    });
  };

  return (
    <div className="card p-3">
      <div className="section-title px-1 pb-2">Gainers (3m)</div>
      <table className="table">
        <thead>
          <tr>
            <th className="py-2.5 px-3">Symbol</th>
            <th className="py-2.5 px-3">Price</th>
            <th className="py-2.5 px-3">% Chg</th>
            <th className="py-2.5 px-3 text-center">Watch</th>
          </tr>
        </thead>
        <tbody>{renderBody()}</tbody>
      </table>
    </div>
  );
}
