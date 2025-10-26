import { useMemo } from 'react';
import { useWebSocket } from '../context/websocketcontext.jsx';

const sanitizeSymbol = (symbol = '') => String(symbol).replace(/-USD$/i, '');

const mapRows = (rows = []) =>
  rows.map((item, idx) => ({
    ...item,
    rank: item?.rank || idx + 1,
    symbol: sanitizeSymbol(item?.symbol || item?.pair || item?.product_id || item?.ticker || ''),
  }));

export function useGainersLosersData({ variant = 'gainers', window = '3min' } = {}) {
  const { latestData, isPolling, error } = useWebSocket();
  const normalizedWindow = String(window || '3min').toLowerCase();
  const normalizedVariant = String(variant || 'gainers').toLowerCase();

  const gainersSource = normalizedWindow.startsWith('1')
    ? latestData?.crypto
    : latestData?.gainers3m;
  const losersSource = latestData?.losers3m;

  const gainers = useMemo(() => mapRows(Array.isArray(gainersSource) ? gainersSource : []), [gainersSource]);
  const losers = useMemo(() => mapRows(Array.isArray(losersSource) ? losersSource : []), [losersSource]);

  const rows = normalizedVariant.startsWith('loser') ? losers : gainers;
  const loading = rows.length === 0 && isPolling;

  return {
    rows,
    data: rows,
    loading,
    error,
    gainers,
    losers,
  };
}

export default useGainersLosersData;
