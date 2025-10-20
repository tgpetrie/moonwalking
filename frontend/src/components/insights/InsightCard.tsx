import React from 'react';
import { fetchInsights, InsightsResponse } from '../../api/sentiment';

const MIN_TTL_SECONDS = 15;

export function InsightList(): JSX.Element {
  const [payload, setPayload] = React.useState<InsightsResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const schedule = (seconds: number) => {
      const ttl = Math.max(MIN_TTL_SECONDS, Number.isFinite(seconds) ? seconds : MIN_TTL_SECONDS);
      timer = setTimeout(load, ttl * 1000);
    };

    const load = async () => {
      try {
        const res = await fetchInsights();
        if (!alive) return;
        setPayload(res);
        setError(null);
        const ttlSeconds = res?.swr?.ttl_seconds ?? res?.swr?.ttl ?? 60;
        schedule(ttlSeconds);
      } catch (err: any) {
        if (!alive) return;
        setError(err.message || 'Unable to load insights');
        schedule(45);
      }
    };

    load();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, []);

  const items = payload?.insights || [];

  if (error) {
    return (
      <div className="p-4 rounded-2xl shadow bg-white text-sm text-red-600" role="alert">
        {error}
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="p-4 rounded-2xl shadow bg-white text-sm text-gray-500">
        {payload?.empty ? 'No insights yet. Retry soon.' : 'Loading insights…'}
      </div>
    );
  }

  return (
    <div className="grid gap-3">
      {items.map((item) => (
        <div key={item.id} className="p-4 rounded-2xl shadow bg-white">
          <div className="text-sm uppercase tracking-wide text-gray-500">{item.kind}</div>
          <div className="text-lg font-semibold">{item.title}</div>
          <div className="text-sm text-gray-700 mt-1">{item.detail}</div>
          {item.action && <div className="text-sm text-blue-600 mt-2">→ {item.action}</div>}
        </div>
      ))}
    </div>
  );
}
