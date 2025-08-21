import { useRef } from 'react';

/**
 * Track numeric field changes per symbol and return flash direction.
 */
export function useRowFlash<T extends { symbol: string }>(rows: T[], getValue: (r: T)=>number){
  const prev = useRef<Map<string, number>>(new Map());
  const flashes = new Map<string, 'up' | 'down'>();
  for (const r of rows){
    const key = r.symbol;
    const val = getValue(r);
    if (prev.current.has(key)){
      const old = prev.current.get(key)!;
      if (val !== old){
        flashes.set(key, val > old ? 'up' : 'down');
      }
    }
    prev.current.set(key, val);
  }
  return flashes;
}
