import { useEffect, useRef, useState } from 'react';

export function useDataClock(intervalMs = 3000) {
  const [tick, setTick] = useState(() => Date.now());
  const timerRef = useRef(undefined);

  useEffect(() => {
    timerRef.current = setInterval(() => setTick(Date.now()), intervalMs);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [intervalMs]);

  return tick;
}
