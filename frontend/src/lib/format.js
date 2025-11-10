// frontend/src/lib/format.js

export function formatPrice(value) {
  if (value == null || Number.isNaN(value)) return "--";
  const n = Number(value);
  if (n >= 1000)
    return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  if (n >= 1) return `$${n.toFixed(2)}`;
  return `$${n.toFixed(4)}`;
}

export function formatPct(value) {
  if (value == null || Number.isNaN(value)) return "--";
  const n = Number(value);
  const abs = Math.abs(n);
  if (abs < 1) return `${n.toFixed(3)}%`;
  return `${n.toFixed(2)}%`;
}

