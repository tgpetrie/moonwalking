export const formatNumber = (value) => {
  if (!Number.isFinite(value)) return 'N/A';
  if (value >= 1) return value.toFixed(2);
  if (value > 0) return value.toFixed(6);
  return '0.000000';
};