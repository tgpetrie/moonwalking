import React from 'react';
import { endpoints, httpGet as fetchJSON } from '../lib/api';
// @ts-ignore - Vite injects import.meta.env at build/runtime
const pollMs = Number((import.meta as any).env?.VITE_POLL_MS || 10000);

export default function useGainersData() {
  const [data, setData] = React.useState<any[]>([]);
  const [isLoading, setIsLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<any>(null);

  React.useEffect(() => {
    let alive = true;

    async function tick() {
      try {
        const j = await fetchJSON(endpoints.gainers1m);
        let rawRows: any[] = [];
        const anyJ: any = j as any;
        if (Array.isArray(anyJ?.data)) rawRows = anyJ.data;
        else if (Array.isArray(anyJ?.rows)) rawRows = anyJ.rows;
        else if (Array.isArray(anyJ)) rawRows = anyJ;
        const rows = rawRows.map((item: any, idx: number) => {
          const symbol = String(item.symbol || item.pair || item.product_id || '').replace(/-USD$/i, '');
          const price = Number(item.current_price ?? item.price ?? 0);
          const change = Number(
            item.price_change_percentage_1min ?? item.change ?? item.change1m ?? item.gain ?? 0,
          );
          return {
            ...item,
            rank: item.rank || idx + 1,
            symbol,
            current_price: price,
            changePct: change,
          };
        });
        if (alive) {
          setData(rows);
            setIsLoading(false);
        }
      } catch (e) {
        if (alive) {
          setError(e);
          setIsLoading(false);
        }
      }
    }

    tick();
    const id = setInterval(tick, pollMs);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return { data, isLoading, error };
}
