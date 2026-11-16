import React from 'react';
import { plainPrice } from './WaveStructureOverlay.jsx';

// Markers for every confirmed swing in the backend `swing_history`: a small
// arrow under each low and over each high, coloured by whether it came in
// higher or lower than the one before, plus a dotted line through the current
// run of higher lows ("rising floor") or lower highs ("falling ceiling").
// It shows why a read is watching for the next dip to hold. Descriptive only.

export const SWING_UP_COLOR = '#5fdbad';
export const SWING_DOWN_COLOR = '#ff829a';
export const SWING_FLAT_COLOR = '#a3acb9';
const INK = '#0c1119';

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const valid = (point) => point && finite(point.ts) && finite(point.price) && point.price > 0;

const defaultPriceText = plainPrice;

// One higher low is a start, not a floor: a run is drawn from two in a row.
export const MIN_RUN = 2;

export function swingsInView(history, firstTime = -Infinity) {
  return (history?.swings || []).filter((swing) => valid(swing) && swing.ts >= firstTime);
}

export function swingColor(swing) {
  if (swing.relation === 'first') return SWING_FLAT_COLOR;
  if (swing.kind === 'low') return swing.relation === 'lower' ? SWING_DOWN_COLOR : SWING_UP_COLOR;
  if (swing.relation === 'higher') return SWING_UP_COLOR;
  return swing.relation === 'lower' ? SWING_DOWN_COLOR : SWING_FLAT_COLOR;
}

// "2 higher lows" / "1 lower high": the label on the dotted run line.
export function runLabel(line) {
  if (!line || !finite(line.count) || line.count < 1) return '';
  const noun = line.kind === 'rising_floor' ? 'higher low' : 'lower high';
  return `${line.count} ${noun}${line.count === 1 ? '' : 's'}`;
}

function RunLine({ line, x, y, firstTime, xMax, compact }) {
  const points = (line?.points || []).filter((point) => valid(point) && point.ts >= firstTime);
  if (points.length < 2 || !(line.count >= MIN_RUN)) return null;
  const floor = line.kind === 'rising_floor';
  const color = floor ? SWING_UP_COLOR : SWING_DOWN_COLOR;
  const offset = floor ? 16 : -16;
  const coords = points.map((point) => `${x(point.ts)},${y(point.price) + offset}`).join(' ');
  const text = `${floor ? 'Rising floor' : 'Falling ceiling'} · ${runLabel(line)}`;
  const fontSize = compact ? 9.5 : 10.5;
  // The label sits at the start of the run, on the side the line moves away
  // from (under a rising floor, over a falling ceiling), so the two never cross.
  const first = points[0];
  const startX = x(first.ts);
  const anchorEnd = startX + text.length * fontSize * 0.58 > xMax;
  const labelY = Math.max(12, y(first.price) + offset + (floor ? 13 : -7));
  return (
    <g data-testid={floor ? 'swing-floor' : 'swing-ceiling'} opacity={line.intact === false ? 0.45 : 1}>
      <polyline fill="none" stroke={color} strokeWidth="1.4" strokeDasharray="1 4" strokeLinecap="round" points={coords}>
        <title>{`${floor ? 'Rising floor' : 'Falling ceiling'}: ${runLabel(line)} in a row${line.intact === false ? ' (price has since moved through the last one)' : ''}`}</title>
      </polyline>
      <text x={anchorEnd ? x(points[points.length - 1].ts) : startX} y={labelY} fill={color}
        fontSize={fontSize} fontWeight="700" textAnchor={anchorEnd ? 'end' : 'start'}
        stroke={INK} strokeWidth="3" paintOrder="stroke">
        {text}
      </text>
    </g>
  );
}

export default function SwingHistoryOverlay({
  history, x, y, firstTime = -Infinity, xMax = Infinity, priceText = defaultPriceText, compact = false,
}) {
  const swings = swingsInView(history, firstTime);
  if (!swings.length) return null;
  const size = compact ? 3.4 : 4.2;
  return (
    <g className="swing-history" data-testid="swing-history" aria-label={history.headline || 'Earlier swing highs and lows'}>
      <RunLine line={history.floor} x={x} y={y} firstTime={firstTime} xMax={xMax} compact={compact} />
      <RunLine line={history.ceiling} x={x} y={y} firstTime={firstTime} xMax={xMax} compact={compact} />
      {swings.map((swing) => {
        const cx = x(swing.ts);
        const low = swing.kind === 'low';
        // Arrow sits just outside the candle: under a low, over a high.
        const tip = y(swing.price) + (low ? 7 : -7);
        const base = tip + (low ? size * 1.7 : -size * 1.7);
        return (
          <path key={`${swing.kind}-${swing.ts}`} data-testid="swing-marker" data-relation={`${swing.relation}-${swing.kind}`}
            d={`M${cx} ${tip} L${cx - size} ${base} L${cx + size} ${base} Z`} fill={swingColor(swing)} stroke={INK} strokeWidth="0.8">
            <title>{`${swing.label} · ${priceText(swing.price)}`}</title>
          </path>
        );
      })}
    </g>
  );
}
