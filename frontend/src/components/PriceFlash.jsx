import React, { useEffect, useRef, useState } from 'react';

// Simple hook to keep previous value
function usePrevious(value) {
  const ref = useRef();
  useEffect(() => { ref.current = value; }, [value]);
  return ref.current;
}

// PriceFlash: flashes a subtle color when numeric value changes.
// Props:
// - value: number (required)
// - precision: number of decimals to show (optional)
// - className: extra classes
export default function PriceFlash({ value = 0, precision = 2, className = '' }) {
  const prev = usePrevious(value);
  const [flash, setFlash] = useState('');
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    if (prev === undefined) return; // initial render
    if (value === prev) return;
    const direction = value > prev ? 'up' : 'down';
    setFlash(direction);
    const t = setTimeout(() => { if (mounted.current) setFlash(''); }, 500);
    return () => clearTimeout(t);
  }, [value, prev]);

  const base = 'inline-flex items-center gap-1 px-2 py-0.5 rounded text-sm transition-colors duration-300';
  const flashClass = flash === 'up'
    ? 'bg-green-600/10 text-green-300 ring-1 ring-green-600/20'
    : flash === 'down'
    ? 'bg-red-600/8 text-rose-300 ring-1 ring-rose-600/20'
    : 'text-gray-200';

  // We keep the visual flash but remove arrow glyphs to avoid alignment shifts.
  return (
    <span
      role="status"
      aria-live="polite"
      className={`${base} ${flashClass} ${className}`}
      title={`Price ${flash === 'up' ? 'increased' : flash === 'down' ? 'decreased' : 'stable'}`}>
      <span className="font-medium">{Number(value).toFixed(precision)}</span>
    </span>
  );
}
