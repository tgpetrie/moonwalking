import { useMemo } from 'react';
import { useWebSocket } from '../context/websocketcontext.jsx';

type Variant = 'gainers' | 'losers';
type WindowOption = '1min' | '3min';

type HookOptions = {
  variant?: Variant | string;
  window?: WindowOption | string;
};

const sanitizeSymbol = (symbol: string = '') => symbol.replace(/-USD$/i, '');

const mapRows = (rows: any[] = []) =>
  rows.map((item = {}, idx) => ({
    ...item,
    rank: item?.rank || idx + 1,
    symbol: sanitizeSymbol(String(item?.symbol || item?.pair || item?.product_id || item?.ticker || '')),
  }));

export default function useGainersLosersData(options: HookOptions = {}) {
  const { latestData, isPolling, error } = useWebSocket();
  const normalizedWindow = String(options.window || '3min').toLowerCase();
  const normalizedVariant = String(options.variant || 'gainers').toLowerCase();

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
