import { useEffect, useMemo, useRef, useState } from 'react';

const mapBy = (arr, key = 'symbol') => {
  if (!Array.isArray(arr)) return new Map();
  return new Map(arr.filter(Boolean).map((item) => [item[key], item]));
};

const serializeDeps = (deps) => {
  if (!Array.isArray(deps) || deps.length === 0) return '';
  return deps
    .map((val) => {
      if (val === null || val === undefined) return String(val);
      if (typeof val === 'number' || typeof val === 'boolean' || typeof val === 'string') return String(val);
      try {
        return JSON.stringify(val);
      } catch (err) {
        return String(val);
      }
    })
    .join('|');
};

const defaultSelector = (json) => {
  if (Array.isArray(json)) return json;
  if (json && Array.isArray(json.data)) return json.data;
  if (json && Array.isArray(json.rows)) return json.rows;
  if (json && Array.isArray(json.items)) return json.items;
  if (json && typeof json === 'object') {
    // component payloads often store rows under .gainers or .losers
    if (Array.isArray(json.gainers)) return json.gainers;
    if (Array.isArray(json.losers)) return json.losers;
  }
  return [];
};

export function useLiveData(url, deps = [], mapKey = 'symbol', selector = defaultSelector) {
  const [data, setData] = useState([]);
  const [changedMap, setChangedMap] = useState(() => new Map());
  const [raw, setRaw] = useState(null);
  const previous = useRef(new Map());
  const [error, setError] = useState(null);

  const depSignature = serializeDeps(deps);

  useEffect(() => {
    let aborted = false;

    const run = async () => {
      try {
        const resp = await fetch(url, {
          method: 'GET',
          headers: { accept: 'application/json' },
          cache: 'no-store',
        });
        if (!resp.ok) throw new Error(String(resp.status));
        const json = await resp.json();
        if (aborted) return;

        setError(null);
        setRaw(json);
        const list = selector(json);
        const safeList = Array.isArray(list) ? list.filter(Boolean) : [];
        const nextMap = mapBy(safeList, mapKey);
        const delta = new Map();

        nextMap.forEach((value, key) => {
          if (!key) return;
          const prev = previous.current.get(key);
          if (!prev) return;
          const prevVal = Number(
            prev.change ??
              prev.delta ??
              prev.price_change_percentage_1min ??
              prev.price_change_percentage ??
              prev.gain ??
              prev.pct ??
              prev.change_pct ??
              0
          );
          const nextVal = Number(
            value.change ??
              value.delta ??
              value.price_change_percentage_1min ??
              value.price_change_percentage ??
              value.gain ??
              value.pct ??
              value.change_pct ??
              0
          );
          if (Number.isFinite(prevVal) && Number.isFinite(nextVal) && prevVal !== nextVal) {
            delta.set(key, nextVal > prevVal ? 'up' : 'down');
          }
        });

        previous.current = nextMap;
        setChangedMap(delta);
        setData(safeList);
      } catch (err) {
        if (!aborted) {
          setError(err instanceof Error ? err : new Error('live data fetch failed'));
          // preserve existing data; clear change map so cells don't flash on errors
          setChangedMap(new Map());
        }
      }
    };

    run();
    return () => {
      aborted = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, depSignature, mapKey, selector]);

  return useMemo(
    () => ({
      data,
      changedMap,
      raw,
      error,
    }),
    [data, changedMap, raw, error]
  );
}
