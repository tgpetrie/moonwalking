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

// ─── multi-year cycle anatomy (PEAK → A → B → C → D → E) ────────────────────
// The backend's chart_structure.cycle_anatomy names the cycle's pivots and the
// accumulation base. These helpers turn it into chart overlays and plain words,
// so every horizon of the Chart Read can show where price sits inside the
// multi-year box. Descriptive only, never a forecast.

export const CYCLE_FLOOR_COLOR = '#5fdbad';
export const CYCLE_CEILING_COLOR = '#f1b43a';
export const CYCLE_TARGET_COLOR = '#c58bff';
export const CYCLE_PIVOT_COLOR = '#8fc7ff';
const DAY_SECONDS = 86400;
const MONTH_SECONDS = 30.44 * DAY_SECONDS;
export const CYCLE_PIVOT_ORDER = ['peak', 'A', 'B', 'C', 'D', 'E'];

export const CYCLE_PIVOT_TEXT = {
  peak: 'The cycle high: the top of the last bull run. Every later move is measured from it.',
  A: 'The first leg down from the peak: the crash that ended the bull run.',
  B: 'A relief rally against the decline that failed well below the peak (a bull trap). Its high is the first upside target once the base breaks out.',
  C: 'The capitulation low: the deepest point of the decline. The accumulation base is built from here.',
  D: 'The strongest rally inside the base. Its high caps the base and sets the breakout ceiling.',
  E: 'The retest of the floor after the wave D rally. It held, which completes the base.',
};

export const CYCLE_LEVEL_TEXT = {
  ceiling: 'Top of the multi-year accumulation base. A daily close back above it is the breakout trigger.',
  wave_b_target: 'The wave B relief-rally high: the first upside target once price breaks out of the base.',
  floor: 'Bottom of the multi-year accumulation base (the wave C / E low). A close below it invalidates the accumulation read.',
};

// What price was doing after each pivot, until the next one.
const CYCLE_LEG_AFTER = {
  peak: 'Wave A Decline',
  A: 'Wave B Relief Rally',
  B: 'Wave C Retreat',
  C: 'Wave D Compression Rally',
  D: 'Wave E Retest',
  E: 'Base complete · awaiting breakout',
};

export const cyclePivotBadge = (key) => (key === 'peak' ? 'PEAK' : key);

export function cyclePivots(anatomy) {
  if (!anatomy?.available) return [];
  return (anatomy.pivots || [])
    .filter((p) => p && CYCLE_PIVOT_ORDER.includes(p.key) && finite(p.timestamp) && positive(p.price))
    .sort((a, b) => a.timestamp - b.timestamp);
}

// The three reference lines, highest first.
export function cycleLevels(anatomy) {
  if (!anatomy?.available) return [];
  const base = anatomy.accumulation_base || {};
  const target = (anatomy.projections || []).find((p) => p?.key === 'target_1');
  return [
    { key: 'ceiling', label: 'Breakout Ceiling', price: base.ceiling, color: CYCLE_CEILING_COLOR },
    { key: 'wave_b_target', label: 'Wave B Target', price: target?.price, color: CYCLE_TARGET_COLOR },
    { key: 'floor', label: 'Accumulation Floor', price: base.floor, color: CYCLE_FLOOR_COLOR },
  ].filter((level) => positive(level.price)).sort((a, b) => b.price - a.price);
}

export function cycleBaseStart(anatomy) {
  const base = anatomy?.accumulation_base || {};
  if (finite(base.start_timestamp)) return base.start_timestamp;
  return cyclePivots(anatomy).find((p) => p.key === 'C')?.timestamp ?? null;
}

// Plain name of the cycle phase a candle at `ts` (closing at `close`) sits in,
// e.g. "Wave C Retreat" or "Month 14 of Accumulation Base".
export function cyclePhaseAt(anatomy, ts, close) {
  const pivots = cyclePivots(anatomy);
  if (!pivots.length || !finite(ts)) return null;
  const base = anatomy.accumulation_base || {};
  const baseStart = cycleBaseStart(anatomy);
  let previous = null;
  for (const pivot of pivots) if (ts >= pivot.timestamp) previous = pivot;
  const leg = previous ? CYCLE_LEG_AFTER[previous.key] : null;
  if (finite(baseStart) && ts >= baseStart) {
    if (positive(base.ceiling) && positive(close) && close > base.ceiling) return 'Breakout above the accumulation base';
    const month = Math.floor((ts - baseStart) / MONTH_SECONDS) + 1;
    const inside = leg && previous.key !== 'E' ? ` · ${leg}` : '';
    return `Month ${month} of Accumulation Base${inside}`;
  }
  if (!previous) return pivots[0].key === 'peak' ? 'Advance into the cycle peak' : 'Before the mapped cycle';
  return leg;
}

// Signed percentage from `from` to `to`, rounded to one decimal.
export function pctFrom(from, to) {
  if (!positive(from) || !positive(to)) return null;
  return Math.round((to / from - 1) * 1000) / 10;
}

export function signedPctText(value) {
  if (!finite(value)) return '';
  return `${value > 0 ? '+' : value < 0 ? '−' : ''}${Math.abs(value).toFixed(1)}%`;
}

// Everything the inspect card says about one pivot or level.
export function cycleInspection(anatomy, item, currentPrice) {
  if (!item) return null;
  if (item.type === 'pivot') {
    const pivots = cyclePivots(anatomy);
    const index = pivots.findIndex((p) => p.key === item.key);
    const pivot = pivots[index];
    if (!pivot) return null;
    const prior = index > 0 ? pivots[index - 1] : null;
    const move = finite(pivot.move_pct) ? pivot.move_pct : prior ? pctFrom(prior.price, pivot.price) : null;
    return {
      type: 'pivot', key: pivot.key, badge: cyclePivotBadge(pivot.key), title: pivot.label || cyclePivotBadge(pivot.key),
      date: pivot.date || new Date(pivot.timestamp * 1000).toISOString().slice(0, 10), price: pivot.price,
      move, moveFrom: prior ? cyclePivotBadge(prior.key) : null,
      fromNow: pctFrom(pivot.price, currentPrice), text: CYCLE_PIVOT_TEXT[pivot.key] || '',
    };
  }
  const level = cycleLevels(anatomy).find((l) => l.key === item.key);
  if (!level) return null;
  const base = anatomy.accumulation_base || {};
  return {
    type: 'level', key: level.key, badge: level.label, title: level.label, color: level.color,
    date: level.key === 'wave_b_target' ? cyclePivots(anatomy).find((p) => p.key === 'B')?.date || null : base.start_date || null,
    price: level.price, move: pctFrom(currentPrice, level.price), moveFrom: 'price now',
    text: CYCLE_LEVEL_TEXT[level.key] || '',
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

function inspectHandlers(item, onInspect, onHover) {
  return {
    role: 'button',
    tabIndex: 0,
    'data-inspect': `${item.type}:${item.key}`,
    style: { cursor: 'pointer', outline: 'none' },
    onClick: (event) => { event.stopPropagation(); onInspect?.(item); },
    onMouseDown: (event) => event.stopPropagation(),
    onMouseEnter: () => onHover?.(item),
    onMouseLeave: () => onHover?.(null),
    onFocus: () => onHover?.(item),
    onBlur: () => onHover?.(null),
    onKeyDown: (event) => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); event.stopPropagation(); onInspect?.(item); }
    },
  };
}

// The multi-year anatomy drawn on any chart: the base's floor and ceiling, the
// wave B target, and the PEAK/A/B/C/D/E pivots that fall inside the plotted
// time range. Levels outside the plotted price range are pinned to the top or
// bottom edge with their distance, so a short-term chart still shows where it
// sits inside the multi-year box. Every pivot and level can be inspected.
export function CycleStructureOverlay({
  anatomy, x, y, xMin, xMax, yTop, yBottom, inView = () => true, priceText = defaultPriceText,
  currentPrice, selected = null, showPivots = true, showLevels = true, onInspect, onHover,
}) {
  const levels = showLevels ? cycleLevels(anatomy) : [];
  const pivots = showPivots ? cyclePivots(anatomy).filter((p) => inView(p.timestamp)) : [];
  if (!levels.length && !pivots.length) return null;
  const isSelected = (type, key) => selected?.type === type && selected?.key === key;
  const above = [];
  const below = [];
  const drawn = [];
  for (const level of levels) {
    const ly = y(level.price);
    if (ly < yTop) above.push(level);
    else if (ly > yBottom) below.push(level);
    else drawn.push({ ...level, ly });
  }
  const halo = { stroke: INK, strokeWidth: 3, paintOrder: 'stroke' };
  const tag = (level, ty, arrow) => {
    const distance = signedPctText(pctFrom(currentPrice, level.price));
    const item = { type: 'level', key: level.key };
    return (
      <g key={level.key} data-testid={`cycle-level-${level.key}`} data-offscale="true" {...inspectHandlers(item, onInspect, onHover)}
        aria-label={`${level.label} ${priceText(level.price)}${distance ? `, ${distance} from price` : ''}. Inspect level.`}>
        <text x={xMax - 4} y={ty} fill={level.color} fontSize="10" fontWeight={isSelected('level', level.key) ? 800 : 700} textAnchor="end" {...halo}>
          {`${arrow} ${level.label} ${priceText(level.price)}${distance ? ` (${distance})` : ''}`}
        </text>
      </g>
    );
  };
  return (
    <g className="cycle-overlay" data-testid="cycle-overlay">
      {drawn.map((level) => {
        const active = isSelected('level', level.key);
        const item = { type: 'level', key: level.key };
        return (
          <g key={level.key} data-testid={`cycle-level-${level.key}`} data-offscale="false" {...inspectHandlers(item, onInspect, onHover)}
            aria-label={`${level.label} ${priceText(level.price)}. Inspect level.`}>
            <line x1={xMin} x2={xMax} y1={level.ly} y2={level.ly} stroke="transparent" strokeWidth="9" />
            <line x1={xMin} x2={xMax} y1={level.ly} y2={level.ly} stroke={level.color} strokeWidth={active ? 2 : 1.1}
              strokeDasharray="6 4" strokeOpacity={active ? 1 : 0.85} />
            <text x={xMin + 4} y={level.ly - 4} fill={level.color} fontSize="10" fontWeight="700" {...halo}>
              {`${level.label} ${priceText(level.price)}`}
            </text>
          </g>
        );
      })}
      {above.map((level, i) => tag(level, yTop + 11 + i * 13, '▲'))}
      {below.map((level, i) => tag(level, yBottom - 5 - (below.length - 1 - i) * 13, '▼'))}
      {pivots.map((pivot) => {
        const high = pivot.kind ? pivot.kind === 'high' : ['peak', 'B', 'D'].includes(pivot.key);
        const px = x(pivot.timestamp);
        const py = y(pivot.price);
        const badge = cyclePivotBadge(pivot.key);
        const width = badge.length * 6.6 + 9;
        const by = Math.min(Math.max(high ? py - 19 : py + 7, yTop), yBottom - 13);
        const active = isSelected('pivot', pivot.key);
        const item = { type: 'pivot', key: pivot.key };
        return (
          <g key={pivot.key} data-testid={`cycle-pivot-${pivot.key}`} {...inspectHandlers(item, onInspect, onHover)}
            aria-label={`${pivot.label || badge}: ${pivot.date || ''} ${priceText(pivot.price)}. Inspect pivot.`}>
            {active && <line x1={px} x2={px} y1={yTop} y2={yBottom} stroke={CYCLE_PIVOT_COLOR} strokeDasharray="2 3" strokeOpacity="0.7" />}
            <line x1={px} x2={px} y1={py} y2={high ? by + 13 : by} stroke={CYCLE_PIVOT_COLOR} strokeOpacity="0.6" />
            <circle cx={px} cy={py} r={active ? 4.6 : 3.4} fill={CYCLE_PIVOT_COLOR} stroke={INK} strokeWidth="1.2" />
            <rect x={px - width / 2} y={by} width={width} height="13" rx="3" fill={active ? CYCLE_PIVOT_COLOR : INK}
              stroke={CYCLE_PIVOT_COLOR} strokeWidth="1" />
            <text x={px} y={by + 9.6} fill={active ? INK : CYCLE_PIVOT_COLOR} fontSize="9.5" fontWeight="800" textAnchor="middle">{badge}</text>
          </g>
        );
      })}
    </g>
  );
}
