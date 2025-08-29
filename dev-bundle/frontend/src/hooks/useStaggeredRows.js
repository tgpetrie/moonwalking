// Lightweight hook to progressively reveal an array of rows with a small delay between each.
// Helps create a "live streaming" feel without hammering layout.
import { useEffect, useRef, useState } from 'react';

/**
 * useStaggeredRows
 * @param {Array<any>} rows - full target rows
 * @param {number} perRowDelay - ms delay between row reveals
 * @param {number} initialDelay - ms initial delay before revealing first row (jitter)
 * @returns {Array<any>} visibleRows - subset currently revealed (eventually === rows)
 */
export function useStaggeredRows(rows, perRowDelay = 35, initialDelay = 0) {
  const [visible, setVisible] = useState([]);
  const timerRef = useRef([]);
  const prevSigRef = useRef('');

  useEffect(() => {
    const signature = rows.map(r => r?.symbol || r?.id || '').join('|');
    if (signature === prevSigRef.current) return; // no structural change
    prevSigRef.current = signature;

    // Clear prior timers
    timerRef.current.forEach(t => clearTimeout(t));
    timerRef.current = [];

    if (!rows || rows.length === 0) {
      setVisible([]);
      return;
    }
    // Start fresh reveal
    setVisible([]);
    rows.forEach((row, idx) => {
      const t = setTimeout(() => {
        setVisible(v => {
          // Avoid duplicates if symbol already present
            if (v.find(existing => (existing.symbol || existing.id) === (row.symbol || row.id))) return v;
            return [...v, row];
        });
      }, initialDelay + perRowDelay * idx);
      timerRef.current.push(t);
    });
    return () => {
      timerRef.current.forEach(t => clearTimeout(t));
    };
  }, [rows, perRowDelay, initialDelay]);

  return visible;
}

/**
 * Diff two numeric values and return direction: 'up' | 'down' | 'flat'
 */
export function diffDirection(next, prev, eps = 1e-9) {
  if (typeof next !== 'number' || typeof prev !== 'number') return 'flat';
  if (next > prev + eps) return 'up';
  if (next < prev - eps) return 'down';
  return 'flat';
}
