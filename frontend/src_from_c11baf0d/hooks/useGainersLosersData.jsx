import { useMemo } from 'react';
import { useWebSocket } from '../context/websocketcontext.jsx';

/**
 * Hook to get gainers/losers data for a specific variant and window.
 * variant: 'gainers' or 'losers'
 * window: '3min' (only supported for now)
 */
export function useGainersLosersData({ variant, window }) {
  const { gainers3mTop, losers3mTop, isPolling } = useWebSocket();

  const rows = useMemo(() => {
    if (window !== '3min') return [];
    if (variant === 'gainers') return gainers3mTop || [];
    if (variant === 'losers') return losers3mTop || [];
    return [];
  }, [variant, window, gainers3mTop, losers3mTop]);

  return {
    rows,
    loading: isPolling && rows.length === 0,
    error: null, // No error handling for now
  };
}