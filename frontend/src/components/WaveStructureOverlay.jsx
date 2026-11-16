import React from 'react';

// SVG overlay for the backend `wave_analysis` payload (elliott_wave_engine),
// drawn in plain words: (1) the prior move, (2) the shaded pullback zone,
// (3) the recovery target, and the dashed line where the setup breaks.
// Wave letters and ratios stay out of the picture; they are on hover only.
// Descriptive only.

export const WAVE_COLOR = '#8fc7ff';
export const WAVE_BREAK_COLOR = '#ff6b8a';
export const WAVE_ADVANCE_COLOR = '#5fdbad';
export const WAVE_DECLINE_COLOR = '#ff9fb0';
const INK = '#0c1119';

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const positive = (value) => finite(value) && value > 0;
const validPoint = (point) => point && finite(point.ts) && positive(point.price);

// Same rounding as the backend story text, so the chart and the cards agree.
export function plainPrice(value) {
  if (!positive(value)) return '';
  if (value >= 1000) return `$${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
  if (value >= 1) return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return `$${Number(value.toPrecision(4))}`;
}

const defaultPriceText = plainPrice;

const PATTERN_LABEL = {
  abc_complete: 'A-B-C correction · complete',
  abc_in_progress: 'A-B-C correction · wave C underway',
  impulse_complete: 'Five-wave move · complete',
  impulse_in_progress: 'Five-wave move · in progress',
};

// Technical (Elliott) name of the read. Shown only under "Technical details".
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

// Which parts of the picture are on a chart that starts at `firstTime`. A
// caption should only describe what the reader can actually see.
export function waveVisibleParts(wave, firstTime = -Infinity) {
  if (!waveIsDrawable(wave)) return { priorMove: false, zone: false, target: false, breaks: false };
  const points = wavePointsInView(wave, firstTime);
  const labels = new Set(points.map((point) => point.label));
  const correction = String(wave.active_pattern || '').startsWith('abc');
  const confirmed = points.filter((point) => point.confirmed !== false);
  return {
    priorMove: correction ? labels.has('start') && labels.has('0') : confirmed.length >= 2,
    zone: Boolean(waveZone(wave)),
    target: correction && positive(wave.target_price),
    breaks: positive(wave.invalidation_price),
  };
}

// Prices the y-scale must cover for the overlay to stay on the chart.
export function wavePrices(wave, firstTime = -Infinity) {
  if (!waveIsDrawable(wave)) return [];
  const zone = waveZone(wave);
  return [
    ...wavePointsInView(wave, firstTime).map((point) => point.price),
    ...(zone ? [zone.low, zone.high] : []),
    ...(positive(wave.invalidation_price) ? [wave.invalidation_price] : []),
    ...(positive(wave.target_price) ? [wave.target_price] : []),
  ];
}

// Plain names for the parts of the picture, from the backend story when it is
// there and from the read's direction otherwise.
export function wavePlainLabels(wave) {
  const up = wave?.bias !== 'bearish';
  const steps = Object.fromEntries((wave?.story?.steps || []).map((step) => [step.key, step]));
  const correction = String(wave?.active_pattern || '').startsWith('abc');
  return {
    up,
    correction,
    side: up ? 'below' : 'above',
    priorMove: steps.prior_move?.title || (correction ? (up ? 'Prior advance' : 'Prior decline') : 'Run so far'),
    zone: steps.zone?.short_title || (up ? 'Dip zone' : 'Bounce zone'),
    target: steps.target?.title || (up ? 'Recovery target' : 'Downside target'),
  };
}

const HOVER_NAME = {
  start: 'Start of the prior move',
  0: 'End of the prior move',
  A: 'First swing of the pullback (wave A)',
  B: 'Counter-swing (wave B)',
  C: 'Second swing of the pullback (wave C)',
};

function StepBadge({ n, cx, cy, color }) {
  return (
    <g aria-hidden="true">
      <circle cx={cx} cy={cy} r="7" fill={color} stroke={INK} strokeWidth="1.5" />
      <text x={cx} y={cy + 3.4} fill={INK} fontSize="9.5" fontWeight="800" textAnchor="middle">{n}</text>
    </g>
  );
}

export default function WaveStructureOverlay({
  wave, x, y, xMin, xMax, firstTime = -Infinity, priceText = defaultPriceText, compact = false,
}) {
  if (!waveIsDrawable(wave)) return null;
  const names = wavePlainLabels(wave);
  const points = wavePointsInView(wave, firstTime);
  const confirmed = points.filter((point) => point.confirmed !== false);
  const open = points.find((point) => point.confirmed === false);
  const lastConfirmed = confirmed[confirmed.length - 1];
  const byLabel = Object.fromEntries(points.map((point) => [point.label, point]));
  const zone = waveZone(wave);
  const zoneX = byLabel.B ? Math.max(xMin, x(byLabel.B.ts)) : xMin;
  const complete = wave.active_pattern === 'abc_complete';
  const breakPrice = positive(wave.invalidation_price) ? wave.invalidation_price : null;
  const targetPrice = names.correction && positive(wave.target_price) ? wave.target_price : null;
  const moveColor = names.up ? WAVE_ADVANCE_COLOR : WAVE_DECLINE_COLOR;
  // The prior move is the first leg of a correction; a run is one move throughout.
  const priorLeg = names.correction && byLabel.start && byLabel[0] ? [byLabel.start, byLabel[0]] : null;
  const pullback = names.correction ? confirmed.filter((point) => point.label !== 'start') : confirmed;
  const fontSize = compact ? 10 : 11;
  const halo = { stroke: INK, strokeWidth: 3, paintOrder: 'stroke' };

  const priorMid = priorLeg && {
    cx: (x(priorLeg[0].ts) + x(priorLeg[1].ts)) / 2,
    cy: (y(priorLeg[0].price) + y(priorLeg[1].price)) / 2,
  };
  // The empty side of a rising leg is its upper left; of a falling leg, its upper right.
  const priorLabelLeft = names.up && priorMid && priorMid.cx - xMin > 96;

  return (
    <g className="wave-overlay" data-testid="wave-overlay" aria-label={`Chart setup: ${wave.story?.headline || wavePatternLabel(wave)}`}>
      {zone && (
        <g data-testid="wave-c-zone">
          <rect x={zoneX} y={y(zone.high)} width={Math.max(1, xMax - zoneX)}
            height={Math.max(1, y(zone.low) - y(zone.high))} fill={WAVE_COLOR} opacity={complete ? 0.08 : 0.15}>
            <title>{`${names.zone}: ${priceText(zone.low)} to ${priceText(zone.high)}. Pullbacks like this one commonly end in this band (0.618 to 1.618 of the first swing).`}</title>
          </rect>
          <line x1={zoneX} x2={xMax} y1={y(zone.high)} y2={y(zone.high)} stroke={WAVE_COLOR} strokeOpacity="0.4" />
          <line x1={zoneX} x2={xMax} y1={y(zone.low)} y2={y(zone.low)} stroke={WAVE_COLOR} strokeOpacity="0.4" />
          {compact ? (
            // The numbered story cards name this band; the chart only points at it.
            <StepBadge n="2" cx={(zoneX + xMax) / 2} cy={(y(zone.high) + y(zone.low)) / 2} color={WAVE_COLOR} />
          ) : (
            <>
              <StepBadge n="2" cx={zoneX + 11} cy={y(zone.high) + 12} color={WAVE_COLOR} />
              <text data-testid="wave-zone-label" x={zoneX + 22} y={y(zone.high) + 15.5} fill={WAVE_COLOR} fontSize={fontSize} fontWeight="700" {...halo}>
                {`${names.zone} · ${priceText(zone.low)} to ${priceText(zone.high)}`}
              </text>
            </>
          )}
        </g>
      )}
      {targetPrice && (
        <g data-testid="wave-target">
          <line x1={zoneX} x2={xMax} y1={y(targetPrice)} y2={y(targetPrice)} stroke={WAVE_COLOR} strokeWidth="1.2" strokeDasharray="2 4">
            <title>{`${names.target}: ${priceText(targetPrice)}, the ${names.up ? 'high' : 'low'} of the last counter-swing (wave B)`}</title>
          </line>
          {compact ? (
            <StepBadge n="3" cx={xMax - 9} cy={y(targetPrice)} color={WAVE_COLOR} />
          ) : (
            <>
              <text x={xMax - 4} y={y(targetPrice) - 5} fill={WAVE_COLOR} fontSize={fontSize} fontWeight="700" textAnchor="end" {...halo}>
                {`${names.target} ${priceText(targetPrice)}`}
              </text>
              <StepBadge n="3" cx={xMax - 12 - (`${names.target} ${priceText(targetPrice)}`.length * fontSize * 0.56)} cy={y(targetPrice) - 9} color={WAVE_COLOR} />
            </>
          )}
        </g>
      )}
      {breakPrice && (
        <g data-testid="wave-invalidation">
          <line x1={xMin} x2={xMax} y1={y(breakPrice)} y2={y(breakPrice)} stroke={WAVE_BREAK_COLOR} strokeWidth="1.2" strokeDasharray="6 4">
            <title>{`This read no longer applies if price trades ${names.side} ${priceText(breakPrice)}`}</title>
          </line>
          <text x={xMin + 4} y={y(breakPrice) + (names.up ? 13 : -5)} fill={WAVE_BREAK_COLOR} fontSize={fontSize} fontWeight="700" {...halo}>
            {`Setup breaks ${names.side} ${priceText(breakPrice)}`}
          </text>
        </g>
      )}
      {priorLeg && (
        <g data-testid="wave-prior-move">
          <line x1={x(priorLeg[0].ts)} y1={y(priorLeg[0].price)} x2={x(priorLeg[1].ts)} y2={y(priorLeg[1].price)}
            stroke={moveColor} strokeWidth="2.6" strokeLinecap="round">
            <title>{`${names.priorMove}: ${priceText(priorLeg[0].price)} to ${priceText(priorLeg[1].price)}`}</title>
          </line>
          <StepBadge n="1" cx={priorMid.cx} cy={priorMid.cy} color={moveColor} />
          {!compact && (
            <text x={priorMid.cx + (priorLabelLeft ? -11 : 11)} y={priorMid.cy - 6} fill={moveColor} fontSize={fontSize} fontWeight="700"
              textAnchor={priorLabelLeft ? 'end' : 'start'} {...halo}>{names.priorMove}</text>
          )}
        </g>
      )}
      {!names.correction && confirmed.length >= 2 && (
        // A run is one move: its first leg carries the "1" that the step card uses.
        <g data-testid="wave-run-label">
          <StepBadge n="1" cx={(x(confirmed[0].ts) + x(confirmed[1].ts)) / 2} cy={(y(confirmed[0].price) + y(confirmed[1].price)) / 2} color={moveColor} />
          {!compact && (
            <text x={(x(confirmed[0].ts) + x(confirmed[1].ts)) / 2 + 11} y={(y(confirmed[0].price) + y(confirmed[1].price)) / 2 - 6}
              fill={moveColor} fontSize={fontSize} fontWeight="700" {...halo}>{names.priorMove}</text>
          )}
        </g>
      )}
      {pullback.length >= 2 && (
        <polyline data-testid="wave-polyline" fill="none" stroke={names.correction ? WAVE_COLOR : moveColor} strokeWidth="1.8" strokeLinejoin="round"
          points={pullback.map((point) => `${x(point.ts)},${y(point.price)}`).join(' ')} />
      )}
      {open && lastConfirmed && (
        <line data-testid="wave-open-leg" x1={x(lastConfirmed.ts)} y1={y(lastConfirmed.price)} x2={x(open.ts)} y2={y(open.price)}
          stroke={names.correction ? WAVE_COLOR : moveColor} strokeWidth="1.6" strokeDasharray="4 4" />
      )}
      {points.map((point) => {
        const isOpen = point.confirmed === false;
        const color = names.correction && point.label !== 'start' ? WAVE_COLOR : moveColor;
        const hover = names.correction
          ? HOVER_NAME[point.label] || `Wave ${point.label}`
          : (point.label === '0' ? 'Start of the run' : `Swing ${point.label} of the run (wave ${point.label})`);
        return (
          <g key={`${point.label}-${point.ts}`} data-testid={`wave-node-${point.label}`}>
            <title>{`${hover}${isOpen ? ', still forming' : ''} · ${priceText(point.price)}`}</title>
            <circle cx={x(point.ts)} cy={y(point.price)} r="3.2" fill={isOpen ? INK : color} stroke={color} strokeWidth="1.4" />
          </g>
        );
      })}
    </g>
  );
}
