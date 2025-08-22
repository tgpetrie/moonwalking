export const fmtUSD = (n, min=2, max=2) => {
  const v = Number(n);
  if (!isFinite(v)) return '—';
  return new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:min,maximumFractionDigits:max}).format(v);
};
export const fmtPct = (n, digits=2) => {
  const v = Number(n);
  if (!isFinite(v)) return '—';
  return `${v>=0?'+':''}${v.toFixed(digits)}%`;
};
export const clsDelta = (v) => (Number(v) >= 0 ? 'text-gain' : 'text-loss');

// utility: accept 0.05 or 5 and render % correctly
export const asPctAuto = (v, digits = 2) => {
  const n = Number(v);
  if (!isFinite(n)) return '—';
  const pct = Math.abs(n) <= 1 ? n * 100 : n;
  return fmtPct(pct, digits);
};
