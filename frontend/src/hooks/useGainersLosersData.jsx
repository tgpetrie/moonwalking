import { useEffect, useMemo, useRef, useState } from 'react';

const mapRows = (payload) => {
  if (!payload) return [];
  if (Array.isArray(payload?.rows)) return payload.rows;
  if (Array.isArray(payload?.data)) return payload.data;
  if (Array.isArray(payload)) return payload;
  return [];
};

const sanitizeSymbol = (symbol = '') => String(symbol).replace(/-USD$/i, '');

/**
 * Poll gainers/losers REST endpoints instead of relying on WebSockets.
 * Maintains the legacy `{ rows, loading, error }` signature expected by MoverTable.
 */
export function useGainersLosersData({ variant = 'gainers', window = '3min', pollInterval = 6000 }) {
  const [state, setState] = useState({ gainers: [], losers: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const timerRef = useRef(null);
  const abortRef = useRef(null);

  const normalizedWindow = String(window || '3min').toLowerCase();
  const normalizedVariant = String(variant || 'gainers').toLowerCase();

  const gainersEndpoint = normalizedWindow === '1min'
    ? '/api/component/gainers-table-1min'
    : '/api/component/gainers-table-3min';

  // Cloudflare worker currently only exposes 3-min losers.
  const losersEndpoint = '/api/component/losers-table-3min';

  useEffect(() => {
    let mounted = true;

    const fetchData = async () => {
      try {
        abortRef.current?.abort();
        const controller = new AbortController();
        abortRef.current = controller;
        if (!mounted) return;

        setLoading(true);

        const [gainersRes, losersRes] = await Promise.all([
          fetch(gainersEndpoint, { signal: controller.signal }).catch(() => null),
          fetch(losersEndpoint, { signal: controller.signal }).catch(() => null),
        ]);

        if (!mounted) return;

        const [gainersJson, losersJson] = await Promise.all([
          gainersRes?.ok ? gainersRes.json().catch(() => ({})) : {},
          losersRes?.ok ? losersRes.json().catch(() => ({})) : {},
        ]);

        const gainersRows = mapRows(gainersJson).map((item, idx) => ({
          ...item,
          rank: item.rank || idx + 1,
          symbol: sanitizeSymbol(item.symbol || item.pair || item.product_id || ''),
        }));

        const losersRows = mapRows(losersJson).map((item, idx) => ({
          ...item,
          rank: item.rank || idx + 1,
          symbol: sanitizeSymbol(item.symbol || item.pair || item.product_id || ''),
        }));

        if (mounted) {
          setState({ gainers: gainersRows, losers: losersRows });
          setError(null);
        }
      } catch (err) {
        if (!mounted) return;
        if (err.name !== 'AbortError') {
          console.error('useGainersLosersData poll failed', err);
          setError(err);
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };

    fetchData();
    timerRef.current = setInterval(fetchData, pollInterval);

    return () => {
      mounted = false;
      if (timerRef.current) clearInterval(timerRef.current);
      abortRef.current?.abort();
    };
  }, [gainersEndpoint, losersEndpoint, pollInterval]);

  const rows = useMemo(() => {
    if (normalizedVariant.startsWith('loser')) return state.losers;
    return state.gainers;
  }, [normalizedVariant, state]);

  return { rows, loading, error, gainers: state.gainers, losers: state.losers };
}

export default useGainersLosersData;
