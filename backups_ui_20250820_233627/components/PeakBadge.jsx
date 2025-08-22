// src/components/PeakBadge.jsx
// Small badge to display peak info (x2/x3/etc.). Safe no-op if missing.

export default function PeakBadge({ peak, className = '' }) {
  if (peak == null || peak === 0) return null;
  const label = typeof peak === 'number' ? `Peak x${peak}` : (peak.label || `Peak x${peak.mult || peak}`);
  return (
    <span className={`inline-flex items-center rounded-sm px-1.5 py-0.5 text-xs font-semibold tracking-wide ${className}`}>
      {label}
    </span>
  );
}