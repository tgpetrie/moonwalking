import { useCallback, useEffect, useMemo, useState } from 'react';
import TokenRow from './TokenRow.jsx';
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

    const normalizeRows = (data = []) =>
      data.map((row) => {
        const rawSymbol = row.symbol || row.ticker || '';
        const normalizedSymbol = rawSymbol.toUpperCase().replace(/-USD$/, '');
        const candidatePrices = [row.current_price, row.price, row.last_price, row.currentPrice];
        const priceValue = candidatePrices.find((value) => typeof value === 'number');
        const candidatePctFields = [
          row.price_change_percentage_3min,
          row.change3m,
          row.change,
          row.percent_change,
        ];
        const pctValue = candidatePctFields.reduce((acc, value) => {
          if (acc !== null) return acc;
          if (typeof value === 'number') return value;
          const parsed = Number(value);
          if (!Number.isNaN(parsed)) {
            return parsed;
          }
          return null;
        }, null);

        return {
          ...row,
          symbol: normalizedSymbol,
          current_price: priceValue ?? null,
          price_change_percentage_3min: pctValue ?? 0,
        };
      });

    const fetchRows = async () => {
      try {
        const endpoint = API_ENDPOINTS.gainersTable3Min || API_ENDPOINTS.gainersTable;
        const response = await fetchData(endpoint);
        if (cancelled) return;
        const dataset = Array.isArray(response?.data) ? response.data : [];
        setRows(normalizeRows(dataset));
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
          row={row}
          isWatched={isWatched}
          isGainer={true}
          onToggleWatch={handleToggleWatch}
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
