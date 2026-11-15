import React from 'react';

// SVG overlay for the backend `wave_analysis` payload (elliott_wave_engine):
// the confirmed swing polyline, labeled wave nodes, the shaded projected
// wave C zone and the dashed line where the count breaks. Descriptive only.

export const WAVE_COLOR = '#8fc7ff';
export const WAVE_BREAK_COLOR = '#ff6b8a';

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const positive = (value) => finite(value) && value > 0;
const validPoint = (point) => point && finite(point.ts) && positive(point.price);

const defaultPriceText = (value) => positive(value)
  ? `$${value.toLocaleString(undefined, { maximumSignificantDigits: 6 })}` : '';

const PATTERN_LABEL = {
  abc_complete: 'A-B-C correction · complete',
  abc_in_progress: 'A-B-C correction · wave C underway',
  impulse_complete: 'Five-wave move · complete',
  impulse_in_progress: 'Five-wave move · in progress',
};

export function wavePatternLabel(wave) {
  if (!wave) return '';
  if (wave.status === 'wave_5_underway') return 'Five-wave move · wave 5 underway';
  if (wave.status === 'wave_4_underway') return 'Five-wave move · wave 4 underway';
  return PATTERN_LABEL[wave.active_pattern] || '';
}

export function waveIsDrawable(wave) {
  return Boolean(wave && wave.available && wave.active_pattern && wave.active_pattern !== 'none'
    && Array.isArray(wave.wave_points) && wave.wave_points.filter(validPoint).length >= 2);
}

export function waveZone(wave) {
  const zone = wave?.projected_c_zone;
  return zone && positive(zone.low) && positive(zone.high) && zone.high > zone.low ? zone : null;
}

// Points at or after `firstTime`; earlier swings are off the left edge of the chart.
export function wavePointsInView(wave, firstTime = -Infinity) {
  return (wave?.wave_points || []).filter((point) => validPoint(point) && point.ts >= firstTime);
}

// Prices the y-scale must cover for the overlay to stay on the chart.
export function wavePrices(wave, firstTime = -Infinity) {
  if (!waveIsDrawable(wave)) return [];
  const zone = waveZone(wave);
  return [
    ...wavePointsInView(wave, firstTime).map((point) => point.price),
    ...(zone ? [zone.low, zone.high] : []),
    ...(positive(wave.invalidation_price) ? [wave.invalidation_price] : []),
  ];
}

export default function WaveStructureOverlay({
  wave, x, y, xMin, xMax, firstTime = -Infinity, priceText = defaultPriceText,
}) {
  if (!waveIsDrawable(wave)) return null;
  const points = wavePointsInView(wave, firstTime);
  const confirmed = points.filter((point) => point.confirmed !== false);
  const open = points.find((point) => point.confirmed === false);
  const lastConfirmed = confirmed[confirmed.length - 1];
  const zone = waveZone(wave);
  const zoneFrom = points.find((point) => point.label === 'B');
  const zoneX = zoneFrom ? Math.max(xMin, x(zoneFrom.ts)) : xMin;
  const complete = wave.active_pattern === 'abc_complete';
  const breakPrice = positive(wave.invalidation_price) ? wave.invalidation_price : null;
  const side = wave.bias === 'bearish' ? 'above' : 'below';

  return (
    <g className="wave-overlay" data-testid="wave-overlay" aria-label={`Wave structure: ${wavePatternLabel(wave)}`}>
      {zone && (
        <g data-testid="wave-c-zone">
          <rect x={zoneX} y={y(zone.high)} width={Math.max(1, xMax - zoneX)}
            height={Math.max(1, y(zone.low) - y(zone.high))} fill={WAVE_COLOR} opacity={complete ? 0.07 : 0.13}>
            <title>{`Projected wave C zone ${priceText(zone.low)} to ${priceText(zone.high)} (0.618 to 1.618 of wave A)`}</title>
          </rect>
          {Object.entries(zone.levels || {}).filter(([, price]) => positive(price)).map(([ratio, price]) => (
            <g key={ratio}>
              <line x1={zoneX} x2={xMax} y1={y(price)} y2={y(price)} stroke={WAVE_COLOR} strokeOpacity="0.35" strokeDasharray="2 4" />
              <text x={xMax - 4} y={y(price) - 3} fill={WAVE_COLOR} fillOpacity="0.8" fontSize="9" textAnchor="end">{`C = ${ratio} × A`}</text>
            </g>
          ))}
        </g>
      )}
      {breakPrice && (
        <g data-testid="wave-invalidation">
          <line x1={xMin} x2={xMax} y1={y(breakPrice)} y2={y(breakPrice)} stroke={WAVE_BREAK_COLOR} strokeWidth="1.2" strokeDasharray="6 4">
            <title>{`The wave count no longer applies ${side} ${priceText(breakPrice)}`}</title>
          </line>
          <text x={xMin + 4} y={y(breakPrice) - 4} fill={WAVE_BREAK_COLOR} fontSize="10">{`Wave count breaks ${side} ${priceText(breakPrice)}`}</text>
        </g>
      )}
      {confirmed.length >= 2 && (
        <polyline data-testid="wave-polyline" fill="none" stroke={WAVE_COLOR} strokeWidth="1.8" strokeLinejoin="round"
          points={confirmed.map((point) => `${x(point.ts)},${y(point.price)}`).join(' ')} />
      )}
      {open && lastConfirmed && (
        <line data-testid="wave-open-leg" x1={x(lastConfirmed.ts)} y1={y(lastConfirmed.price)} x2={x(open.ts)} y2={y(open.price)}
          stroke={WAVE_COLOR} strokeWidth="1.6" strokeDasharray="4 4" />
      )}
      {points.map((point) => {
        const cx = x(point.ts);
        const cy = y(point.price);
        const isOpen = point.confirmed === false;
        const label = point.label === 'start' ? '' : `${point.label}${isOpen ? '?' : ''}`;
        return (
          <g key={`${point.label}-${point.ts}`} data-testid={`wave-node-${point.label}`}>
            <title>{`${point.label === 'start' ? 'Start of the prior move' : `Wave ${point.label}`}${isOpen ? ' (still forming)' : ''} · ${priceText(point.price)}`}</title>
            <circle cx={cx} cy={cy} r="3.6" fill={isOpen ? '#0c1119' : WAVE_COLOR} stroke={WAVE_COLOR} strokeWidth="1.4" />
            {label && (
              <text x={cx} y={point.kind === 'high' ? cy - 8 : cy + 15} fill="#f3f6fa" fontSize="12" fontWeight="700" textAnchor="middle"
                stroke="#0c1119" strokeWidth="3" paintOrder="stroke">{label}</text>
            )}
          </g>
        );
      })}
    </g>
  );
}
