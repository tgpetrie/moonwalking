import React, { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import WaveStructureOverlay, {
  CycleStructureOverlay, cycleInspection, cycleLevels, cyclePhaseAt, cyclePivotBadge, cyclePivots,
  pctFrom, plainPrice, signedPctText, waveIsDrawable, wavePrices,
} from './WaveStructureOverlay.jsx';
import SwingHistoryOverlay, { swingsInView } from './SwingHistoryOverlay.jsx';
import { getBrowserTimeZone } from '../utils/browserTimeZone.js';
import '../styles/chart-read-chart.css';

/*
 * ChartReadChart
 * --------------
 * The one interactive chart of the Chart Read. It stays mounted across the
 * Short-term / Swing / Macro / Cycle switch, so the reader never loses the
 * picture: the candles change, the multi-year structure (accumulation floor,
 * breakout ceiling, wave B target, PEAK→E pivots) stays drawn on every view.
 *
 *   - candlesticks or an area line, with a volume histogram underneath
 *   - a crosshair that snaps to each candle and a HUD with the candle's
 *     date, O/H/L/C, % change, volume, cycle phase and distance to the base
 *   - click or hover any pivot badge or level line to inspect it
 *   - drag to pan, scroll (or the +/− buttons) to zoom, arrow keys to step
 *
 * Descriptive only.
 */

export const UP_COLOR = '#5fdbad';
export const DOWN_COLOR = '#ff829a';
const INK = '#0c1119';
const GRID = '#ffffff10';
const AXIS_TEXT = '#a3acb9';

// viewBox geometry
const W = 720;
const H = 330;
const PLOT_L = 8;
const PLOT_R = 652;
const PRICE_T = 12;
const PRICE_B = 244;
const VOL_T = 254;
const VOL_B = 304;
const AXIS_Y = 320;
const MIN_BARS = 12;

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const positive = (value) => finite(value) && value > 0;
const priceText = (value) => plainPrice(value) || '—';

function validBar(bar) {
  return bar && finite(bar.t) && positive(bar.o) && positive(bar.h) && positive(bar.l) && positive(bar.c)
    && bar.h >= bar.l;
}

function sortUnique(bars) {
  const byTime = new Map();
  for (const bar of bars) if (validBar(bar)) byTime.set(bar.t, bar);
  return [...byTime.values()].sort((a, b) => a.t - b.t);
}

// One candle list for the chart from whatever the read carries: the complete
// OHLCV series (`candles`), the wave read's own candles, or, on the cycle view
// only, the anatomy's close line.
export function chartCandles(data, anatomy) {
  const num = (value) => (value === null || value === undefined || value === '' ? NaN : Number(value));
  const full = sortUnique((Array.isArray(data?.candles) ? data.candles : []).map((bar) => bar && ({
    t: num(bar.timestamp), o: num(bar.open), h: num(bar.high), l: num(bar.low), c: num(bar.close), v: num(bar.volume),
  })));
  if (full.length >= 2) return full;
  const wave = sortUnique((data?.wave_analysis?.chart?.candles || []).filter(Array.isArray).map((c) => ({
    t: num(c[0]), l: num(c[1]), h: num(c[2]), o: num(c[3]), c: num(c[4]), v: num(c[5]),
  })));
  if (wave.length >= 2) return wave;
  const closes = sortUnique((anatomy?.chart_closes || []).filter((p) => Array.isArray(p) && p.length >= 2).map(([t, c]) => ({
    t: num(t), o: num(c), h: num(c), l: num(c), c: num(c), v: NaN, closeOnly: true,
  })));
  return closes.length >= 2 ? closes : [];
}

function barStep(candles, fallback) {
  if (positive(fallback)) return fallback;
  const gaps = [];
  for (let i = 1; i < candles.length && gaps.length < 50; i += 1) gaps.push(candles[i].t - candles[i - 1].t);
  gaps.sort((a, b) => a - b);
  return gaps.length ? Math.max(1, gaps[Math.floor(gaps.length / 2)]) : 3600;
}

function formatWhen(ts, step, timeZone) {
  const date = new Date(ts * 1000);
  if (step >= 86400) {
    return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', timeZone });
  }
  return date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZone });
}

function axisWhen(ts, step, spanSeconds, timeZone) {
  const date = new Date(ts * 1000);
  if (spanSeconds > 200 * 86400) return date.toLocaleDateString(undefined, { month: 'short', year: 'numeric', timeZone });
  if (step >= 86400 || spanSeconds > 6 * 86400) return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone });
  return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', timeZone });
}

export function volumeText(value) {
  if (!finite(value) || value < 0) return '—';
  if (value >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toFixed(value >= 10 ? 0 : 2);
}

function clampView(lo, hi, n) {
  const span = Math.min(n, Math.max(Math.min(MIN_BARS, n), hi - lo + 1));
  let start = Math.round(lo);
  start = Math.max(0, Math.min(start, n - span));
  return { lo: start, hi: start + span - 1 };
}

function ToggleButton({ active, onClick, children, label, testId }) {
  return (
    <button type="button" className={`mini-toggle-btn ${active ? 'active' : ''}`} aria-pressed={active}
      aria-label={label} onClick={onClick} data-testid={testId}>
      {children}
    </button>
  );
}

function Hud({ bar, prev, latest, anatomy, step, timeZone }) {
  if (!bar) return null;
  const levels = cycleLevels(anatomy);
  const ceiling = levels.find((l) => l.key === 'ceiling');
  const floor = levels.find((l) => l.key === 'floor');
  const change = pctFrom(prev ? prev.c : bar.o, bar.c);
  const phase = cyclePhaseAt(anatomy, bar.t, bar.c);
  const up = bar.c >= bar.o;
  const basePos = ceiling && floor && ceiling.price > floor.price
    ? Math.round((bar.c - floor.price) / (ceiling.price - floor.price) * 100) : null;
  const cell = (label, value, testId, color) => (
    <span className="chart-hud__cell" data-testid={testId}>
      <span className="chart-hud__label">{label}</span>
      <span className="chart-hud__value" style={color ? { color } : undefined}>{value}</span>
    </span>
  );
  return (
    <div className="chart-hud" data-testid="chart-hud" data-latest={latest ? 'true' : 'false'} aria-live="polite">
      <span className="chart-hud__cell chart-hud__when" data-testid="chart-hud-date">
        <span className="chart-hud__label">{latest ? 'Latest' : 'Candle'}</span>
        <span className="chart-hud__value">{formatWhen(bar.t, step, timeZone)}</span>
      </span>
      {bar.closeOnly ? cell('Close', priceText(bar.c), 'chart-hud-ohlc') : (
        <span className="chart-hud__cell" data-testid="chart-hud-ohlc">
          <span className="chart-hud__label">O / H / L / C</span>
          <span className="chart-hud__value" style={{ color: up ? UP_COLOR : DOWN_COLOR }}>
            {`${priceText(bar.o)} / ${priceText(bar.h)} / ${priceText(bar.l)} / ${priceText(bar.c)}`}
          </span>
        </span>
      )}
      {cell('Change', signedPctText(change) || '—', 'chart-hud-change', finite(change) ? (change >= 0 ? UP_COLOR : DOWN_COLOR) : undefined)}
      {bar.closeOnly ? null : cell('Volume', volumeText(bar.v), 'chart-hud-volume')}
      {phase ? cell('Cycle phase', phase, 'chart-hud-phase') : null}
      {ceiling ? cell('To breakout ceiling', signedPctText(pctFrom(bar.c, ceiling.price)), 'chart-hud-ceiling', ceiling.color) : null}
      {floor ? cell('To support floor', signedPctText(pctFrom(bar.c, floor.price)), 'chart-hud-floor', floor.color) : null}
      {finite(basePos) ? cell('In base range', `${basePos}%`, 'chart-hud-base-position') : null}
    </div>
  );
}

function InspectCard({ info, pinned, onClose }) {
  if (!info) {
    return (
      <p className="chart-inspect chart-inspect--hint" data-testid="chart-inspect-hint">
        Hover or click a PEAK–E badge or a level line to inspect it · drag to pan · scroll or use +/− to zoom · arrow keys step through candles
      </p>
    );
  }
  const moveLabel = info.type === 'pivot'
    ? (info.moveFrom ? `${signedPctText(info.move)} from ${info.moveFrom}` : 'First mapped pivot')
    : `${signedPctText(info.move)} from price now`;
  return (
    <div className="chart-inspect" data-testid="chart-inspect" data-kind={info.type} data-key={info.key}>
      <div className="chart-inspect__head">
        <span className="chart-inspect__badge" style={info.color ? { borderColor: info.color, color: info.color } : undefined}>{info.badge}</span>
        <strong className="chart-inspect__title">{info.title}</strong>
        {pinned ? (
          <button type="button" className="chart-inspect__close" onClick={onClose} aria-label="Close inspector">×</button>
        ) : null}
      </div>
      <dl className="chart-inspect__facts">
        {info.date ? <div><dt>Date</dt><dd data-testid="chart-inspect-date">{info.date}</dd></div> : null}
        <div><dt>Price</dt><dd data-testid="chart-inspect-price">{priceText(info.price)}</dd></div>
        {finite(info.move) || info.type === 'pivot' ? (
          <div><dt>{info.type === 'pivot' ? 'Move' : 'Distance'}</dt><dd data-testid="chart-inspect-move">{finite(info.move) ? moveLabel : 'First mapped pivot'}</dd></div>
        ) : null}
        {info.type === 'pivot' && finite(info.fromNow) ? (
          <div><dt>Price now vs this</dt><dd>{signedPctText(info.fromNow)}</dd></div>
        ) : null}
      </dl>
      <p className="chart-inspect__text" data-testid="chart-inspect-text">{info.text}</p>
    </div>
  );
}

export default function ChartReadChart({
  data, anatomy, horizon, busy = false, busyLabel = 'Loading this view…',
}) {
  const candles = useMemo(() => chartCandles(data, horizon === 'cycle' ? anatomy : null), [data, anatomy, horizon]);
  const timeZone = getBrowserTimeZone();
  const n = candles.length;
  const closeOnly = Boolean(candles[0]?.closeOnly);
  const step = useMemo(() => barStep(candles, data?.wave_analysis?.chart?.granularity_seconds), [candles, data]);
  const wave = data?.wave_analysis;
  const drawable = waveIsDrawable(wave);
  const history = wave?.swing_history;
  const hasAnatomy = Boolean(anatomy?.available);

  // Display preferences survive horizon switches; the zoom resets per series.
  const [mode, setMode] = useState('candles');
  const [showLevels, setShowLevels] = useState(true);
  const [fitBox, setFitBox] = useState(null); // null = automatic (on for the cycle view)
  const [logScale, setLogScale] = useState(null); // null = automatic (on for the cycle view)
  const fitLevels = fitBox ?? horizon === 'cycle';
  const useLog = logScale ?? horizon === 'cycle';
  const effectiveMode = closeOnly ? 'line' : mode;

  const seriesKey = `${horizon || ''}|${n ? candles[0].t : ''}|${n}`;
  const [view, setView] = useState(() => ({ lo: 0, hi: Math.max(0, n - 1) }));
  const [viewKey, setViewKey] = useState(seriesKey);
  if (viewKey !== seriesKey) {
    setViewKey(seriesKey);
    setView({ lo: 0, hi: Math.max(0, n - 1) });
  }
  const { lo, hi } = n ? clampView(view.lo, view.hi, n) : { lo: 0, hi: -1 };
  const span = Math.max(1, hi - lo + 1);
  const slot = (PLOT_R - PLOT_L) / span;

  const [hoverIndex, setHoverIndex] = useState(null);
  const [selected, setSelected] = useState(null);
  const [hoverItem, setHoverItem] = useState(null);
  const uid = useId().replace(/:/g, '');
  const clipId = `chart-read-plot-${uid}`;
  const areaId = `chart-read-area-${uid}`;
  const svgRef = useRef(null);
  const dragRef = useRef(null);
  const viewRef = useRef({ lo, hi, n });
  viewRef.current = { lo, hi, n };

  // Fractional candle index of a timestamp; outside the series it extrapolates
  // by the bar step, so a multi-year pivot lands far off a short-term chart.
  const indexOf = useCallback((ts) => {
    if (!n || !finite(ts)) return NaN;
    if (ts <= candles[0].t) return (ts - candles[0].t) / step;
    if (ts >= candles[n - 1].t) return n - 1 + (ts - candles[n - 1].t) / step;
    let a = 0;
    let b = n - 1;
    while (b - a > 1) {
      const mid = (a + b) >> 1;
      if (candles[mid].t <= ts) a = mid; else b = mid;
    }
    return a + (ts - candles[a].t) / Math.max(1, candles[b].t - candles[a].t);
  }, [candles, n, step]);

  const x = useCallback((ts) => PLOT_L + (indexOf(ts) - lo + 0.5) * slot, [indexOf, lo, slot]);
  const xi = useCallback((i) => PLOT_L + (i - lo + 0.5) * slot, [lo, slot]);
  const inView = useCallback((ts) => {
    const i = indexOf(ts);
    return finite(i) && i >= lo - 0.5 && i <= hi + 0.5;
  }, [indexOf, lo, hi]);

  const visible = useMemo(() => candles.slice(lo, hi + 1), [candles, lo, hi]);
  const firstTime = visible[0]?.t ?? -Infinity;
  const lastBar = n ? candles[n - 1] : null;
  const levels = useMemo(() => (hasAnatomy ? cycleLevels(anatomy) : []), [anatomy, hasAnatomy]);

  // Price scale: the visible candles, the setup overlay, and, when "Fit box"
  // is on, the multi-year levels.
  const scale = useMemo(() => {
    const prices = visible.flatMap((bar) => [bar.l, bar.h]);
    if (drawable) prices.push(...wavePrices(wave, firstTime));
    prices.push(...swingsInView(history, firstTime).map((s) => s.price));
    if (fitLevels && showLevels) prices.push(...levels.map((l) => l.price));
    const valid = prices.filter(positive);
    if (!valid.length) return null;
    const tf = (p) => (useLog ? Math.log(p) : p);
    let tmin = Math.min(...valid.map(tf));
    let tmax = Math.max(...valid.map(tf));
    if (tmax - tmin < 1e-9) { tmin -= useLog ? 0.01 : Math.abs(tmin) * 0.01 || 1; tmax += useLog ? 0.01 : Math.abs(tmax) * 0.01 || 1; }
    const pad = (tmax - tmin) * 0.07;
    tmin -= pad;
    tmax += pad;
    if (!useLog) tmin = Math.max(tmin, 0);
    const y = (p) => PRICE_T + (tmax - tf(Math.max(p, 1e-12))) / (tmax - tmin) * (PRICE_B - PRICE_T);
    const inv = (t) => (useLog ? Math.exp(t) : t);
    const ticks = Array.from({ length: 5 }, (_, i) => inv(tmax - (tmax - tmin) * ((i + 0.5) / 5)));
    const volMax = Math.max(0, ...visible.map((bar) => (finite(bar.v) ? bar.v : 0)));
    return { y, ticks, volMax };
  }, [visible, drawable, wave, firstTime, history, fitLevels, showLevels, levels, useLog]);

  const zoomBy = useCallback((factor, anchor = 0.5) => {
    const { lo: l, hi: h, n: count } = viewRef.current;
    if (!count) return false;
    const current = h - l + 1;
    const next = Math.min(count, Math.max(Math.min(MIN_BARS, count), Math.round(current * factor)));
    if (next === current) return false;
    const pivot = l + anchor * current;
    setView(clampView(pivot - anchor * next, pivot - anchor * next + next - 1, count));
    return true;
  }, []);
  const panBy = useCallback((bars) => {
    const { lo: l, hi: h, n: count } = viewRef.current;
    if (!count || !bars) return;
    setView(clampView(l + bars, h + bars, count));
  }, []);
  const resetView = useCallback(() => setView({ lo: 0, hi: Math.max(0, viewRef.current.n - 1) }), []);

  // Pointer position in viewBox units (falls back to raw client units when the
  // element has no layout, as in tests).
  const toViewBox = (event) => {
    const svg = svgRef.current;
    const rect = svg?.getBoundingClientRect?.();
    if (!rect || !rect.width) return { vx: event.clientX, vy: event.clientY };
    return { vx: (event.clientX - rect.left) * W / rect.width, vy: (event.clientY - rect.top) * H / rect.height };
  };
  const indexAt = (vx) => {
    if (vx < PLOT_L || vx > PLOT_R) return null;
    return Math.min(hi, Math.max(lo, lo + Math.floor((vx - PLOT_L) / slot)));
  };

  // Wheel zoom needs a non-passive listener to keep the modal from scrolling.
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return undefined;
    const onWheel = (event) => {
      if (!event.deltaY) return;
      const rect = svg.getBoundingClientRect();
      const vx = rect.width ? (event.clientX - rect.left) * W / rect.width : event.clientX;
      const anchor = Math.min(1, Math.max(0, (vx - PLOT_L) / (PLOT_R - PLOT_L)));
      if (zoomBy(event.deltaY > 0 ? 1.2 : 1 / 1.2, anchor)) event.preventDefault();
    };
    svg.addEventListener('wheel', onWheel, { passive: false });
    return () => svg.removeEventListener('wheel', onWheel);
  }, [zoomBy, n]);

  const onMouseDown = (event) => {
    if (event.button !== 0 || !n) return;
    const { vx } = toViewBox(event);
    dragRef.current = { vx, lo, hi, moved: false };
  };
  const onMouseMove = (event) => {
    if (!n) return;
    const { vx, vy } = toViewBox(event);
    const drag = dragRef.current;
    if (drag) {
      const dx = vx - drag.vx;
      if (Math.abs(dx) > 3) drag.moved = true;
      if (drag.moved) {
        const shift = Math.round(-dx / slot);
        setView(clampView(drag.lo + shift, drag.hi + shift, n));
      }
    }
    setHoverIndex(vy > VOL_B + 4 ? null : indexAt(vx));
  };
  const endDrag = () => { dragRef.current = null; };
  const onMouseLeave = () => { endDrag(); setHoverIndex(null); };
  const onTouch = (event) => {
    const touch = event.touches?.[0];
    if (touch) setHoverIndex(indexAt(toViewBox(touch).vx));
  };
  const onKeyDown = (event) => {
    if (!n) return;
    const keys = {
      ArrowLeft: () => setHoverIndex((i) => Math.max(lo, (i ?? hi) - 1)),
      ArrowRight: () => setHoverIndex((i) => Math.min(hi, (i ?? hi) + 1)),
      Home: () => setHoverIndex(lo),
      End: () => setHoverIndex(hi),
      '+': () => zoomBy(1 / 1.25),
      '=': () => zoomBy(1 / 1.25),
      '-': () => zoomBy(1.25),
      0: resetView,
      Escape: () => { setSelected(null); setHoverIndex(null); },
    };
    const action = keys[event.key];
    if (action) { event.preventDefault(); action(); }
  };

  const inspect = useCallback((item) => {
    setSelected((current) => (current && item && current.type === item.type && current.key === item.key ? null : item));
  }, []);
  // Chips also bring a pivot that is inside the series into view.
  const inspectAndReveal = (item) => {
    inspect(item);
    if (item.type !== 'pivot') return;
    const pivot = cyclePivots(anatomy).find((p) => p.key === item.key);
    const i = pivot ? indexOf(pivot.timestamp) : NaN;
    if (!finite(i) || i < 0 || i > n - 1 || (i >= lo && i <= hi)) return;
    setView(clampView(Math.round(i - span / 2), Math.round(i - span / 2) + span - 1, n));
  };

  const hoverBar = hoverIndex !== null && hoverIndex >= lo && hoverIndex <= hi ? candles[hoverIndex] : null;
  const hudIndex = hoverBar ? hoverIndex : n - 1;
  const hudBar = n ? candles[hudIndex] : null;
  const hudPrev = hudIndex > 0 ? candles[hudIndex - 1] : null;
  const currentPrice = lastBar?.c;
  const inspected = hoverItem || selected;
  const info = hasAnatomy ? cycleInspection(anatomy, inspected, currentPrice) : null;
  const zoomed = n > 0 && (lo > 0 || hi < n - 1);

  // The candle and volume layers only change with the view, not the cursor.
  const series = useMemo(() => {
    if (!scale || !visible.length) return null;
    const { y, volMax } = scale;
    const body = Math.max(1, Math.min(14, slot * 0.64));
    const volH = VOL_B - VOL_T;
    const volumes = volMax > 0 ? visible.map((bar, k) => {
      if (!finite(bar.v) || bar.v <= 0) return null;
      const h = Math.max(0.6, bar.v / volMax * volH);
      const up = bar.c >= bar.o;
      return <rect key={bar.t} x={xi(lo + k) - body / 2} y={VOL_B - h} width={body} height={h} fill={up ? UP_COLOR : DOWN_COLOR} opacity="0.32" />;
    }) : null;
    let price;
    if (effectiveMode === 'line') {
      const pts = visible.map((bar, k) => `${xi(lo + k).toFixed(2)},${y(bar.c).toFixed(2)}`);
      const area = `${xi(lo).toFixed(2)},${PRICE_B} ${pts.join(' ')} ${xi(hi).toFixed(2)},${PRICE_B}`;
      price = (
        <g data-testid="chart-line">
          <polygon points={area} fill={`url(#${areaId})`} />
          <polyline points={pts.join(' ')} fill="none" stroke="#e6edf5" strokeWidth="1.5" strokeLinejoin="round" />
        </g>
      );
    } else {
      price = (
        <g data-testid="chart-candles">
          {visible.map((bar, k) => {
            const cx = xi(lo + k);
            const up = bar.c >= bar.o;
            const color = up ? UP_COLOR : DOWN_COLOR;
            const top = y(Math.max(bar.o, bar.c));
            const bottom = y(Math.min(bar.o, bar.c));
            return (
              <g key={bar.t} data-testid="chart-candle">
                <line x1={cx} x2={cx} y1={y(bar.h)} y2={y(bar.l)} stroke={color} strokeWidth="1" />
                {slot >= 2.4 ? (
                  <rect x={cx - body / 2} y={top} width={body} height={Math.max(1, bottom - top)} fill={color} fillOpacity={up ? 0.85 : 0.95} />
                ) : null}
              </g>
            );
          })}
        </g>
      );
    }
    return (
      <>
        <g data-testid="chart-volume">{volumes}</g>
        {price}
      </>
    );
  }, [scale, visible, slot, xi, lo, hi, effectiveMode, areaId]);

  const levelChips = hasAnatomy ? levels : [];
  const pivotChips = hasAnatomy ? cyclePivots(anatomy) : [];
  const spanSeconds = visible.length > 1 ? visible[visible.length - 1].t - visible[0].t : step;
  const timeTicks = visible.length ? [...new Set(Array.from({ length: 5 }, (_, i) => lo + Math.round((span - 1) * (i + 0.5) / 5)))] : [];

  return (
    <div className="chart-read-chart" data-testid="chart-read-chart-frame" data-horizon={horizon || ''} aria-busy={busy}>
      <div className="chart-read-chart__toolbar" role="toolbar" aria-label="Chart display">
        <div className="mini-toggle" role="group" aria-label="Chart type" style={{ marginTop: 0 }}>
          <ToggleButton active={effectiveMode === 'candles'} onClick={() => setMode('candles')} label="Candlesticks" testId="chart-mode-candles">Candles</ToggleButton>
          <ToggleButton active={effectiveMode === 'line'} onClick={() => setMode('line')} label="Area line" testId="chart-mode-line">Line</ToggleButton>
        </div>
        <div className="mini-toggle" role="group" aria-label="Chart overlays" style={{ marginTop: 0 }}>
          {hasAnatomy ? (
            <ToggleButton active={showLevels} onClick={() => setShowLevels((v) => !v)} label="Show multi-year cycle levels" testId="chart-toggle-levels">Cycle levels</ToggleButton>
          ) : null}
          {hasAnatomy ? (
            <ToggleButton active={fitLevels} onClick={() => setFitBox(!fitLevels)} label="Fit the multi-year box in view" testId="chart-toggle-fit">Fit box</ToggleButton>
          ) : null}
          <ToggleButton active={useLog} onClick={() => setLogScale(!useLog)} label="Log price scale" testId="chart-toggle-log">Log</ToggleButton>
        </div>
        <div className="mini-toggle" role="group" aria-label="Zoom" style={{ marginTop: 0 }}>
          <button type="button" className="mini-toggle-btn" onClick={() => zoomBy(1.25)} aria-label="Zoom out" data-testid="chart-zoom-out">−</button>
          <button type="button" className="mini-toggle-btn" onClick={() => zoomBy(1 / 1.25)} aria-label="Zoom in" data-testid="chart-zoom-in">+</button>
          <button type="button" className="mini-toggle-btn" onClick={() => panBy(-Math.max(1, Math.round(span / 4)))} aria-label="Pan back in time" disabled={!zoomed || lo === 0}>‹</button>
          <button type="button" className="mini-toggle-btn" onClick={() => panBy(Math.max(1, Math.round(span / 4)))} aria-label="Pan forward in time" disabled={!zoomed || hi === n - 1}>›</button>
          <button type="button" className="mini-toggle-btn" onClick={resetView} aria-label="Reset zoom" disabled={!zoomed} data-testid="chart-zoom-reset">Reset</button>
        </div>
        <span className="chart-read-chart__meta" data-testid="chart-read-chart-range">
          {busy ? busyLabel : n ? `${span} of ${n} candles${zoomed ? ' · zoomed' : ''}` : 'No candles for this view yet'}
        </span>
      </div>

      <Hud bar={hudBar} prev={hudPrev} latest={!hoverBar} anatomy={hasAnatomy ? anatomy : null} step={step} timeZone={timeZone} />

      <div className="chart-read-chart__stage" style={{ opacity: busy ? 0.55 : 1 }}>
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="chart-read-chart__svg" role="group" aria-roledescription="interactive chart" tabIndex={0}
          aria-label={`Interactive ${closeOnly ? 'line' : effectiveMode === 'line' ? 'area line' : 'candlestick'} chart${hasAnatomy ? ' with the multi-year cycle structure' : ''}: ${wave?.story?.headline || anatomy?.accumulation_base?.stage_label || 'recent price'}`}
          data-testid="chart-read-chart" data-mode={effectiveMode}
          onMouseDown={onMouseDown} onMouseMove={onMouseMove} onMouseUp={endDrag} onMouseLeave={onMouseLeave}
          onTouchStart={onTouch} onTouchMove={onTouch} onKeyDown={onKeyDown}
          style={{ cursor: dragRef.current?.moved ? 'grabbing' : 'crosshair' }}>
          <defs>
            <clipPath id={clipId}><rect x={PLOT_L} y={0} width={PLOT_R - PLOT_L} height={VOL_B} /></clipPath>
            <linearGradient id={areaId} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#8fc7ff" stopOpacity="0.32" />
              <stop offset="100%" stopColor="#8fc7ff" stopOpacity="0.02" />
            </linearGradient>
          </defs>
          <rect x="0" y="0" width={W} height={H} fill="rgba(12,17,25,0.6)" rx="6" />
          {scale ? scale.ticks.map((p, i) => (
            <g key={i}>
              <line x1={PLOT_L} x2={PLOT_R} y1={scale.y(p)} y2={scale.y(p)} stroke={GRID} />
              <text x={PLOT_R + 6} y={scale.y(p) + 3.5} fill={AXIS_TEXT} fontSize="9.5">{priceText(p)}</text>
            </g>
          )) : null}
          <line x1={PLOT_L} x2={PLOT_R} y1={VOL_T - 4} y2={VOL_T - 4} stroke={GRID} />
          {timeTicks.map((i) => (
            <text key={i} x={xi(i)} y={AXIS_Y} fill={AXIS_TEXT} fontSize="9.5" textAnchor="middle">{axisWhen(candles[i].t, step, spanSeconds, timeZone)}</text>
          ))}

          <g clipPath={`url(#${clipId})`}>
            {series}
            {scale && lastBar ? (
              <line x1={PLOT_L} x2={PLOT_R} y1={scale.y(lastBar.c)} y2={scale.y(lastBar.c)} stroke="#e6edf5" strokeOpacity="0.35" strokeDasharray="1 3" />
            ) : null}
            {scale ? <SwingHistoryOverlay history={history} x={x} y={scale.y} firstTime={firstTime} xMax={PLOT_R} priceText={priceText} compact /> : null}
            {scale && drawable ? (
              <WaveStructureOverlay wave={wave} x={x} y={scale.y} xMin={PLOT_L} xMax={PLOT_R} firstTime={firstTime} priceText={priceText} compact />
            ) : null}
          </g>
          {scale && lastBar ? (
            <g aria-hidden="true">
              <rect x={PLOT_R + 2} y={scale.y(lastBar.c) - 7} width={W - PLOT_R - 4} height="14" rx="3" fill="#e6edf5" />
              <text x={PLOT_R + 6} y={scale.y(lastBar.c) + 3.5} fill={INK} fontSize="9.5" fontWeight="700">{priceText(lastBar.c)}</text>
            </g>
          ) : null}

          {hoverBar && scale ? (
            <g data-testid="chart-crosshair" pointerEvents="none">
              <line x1={xi(hoverIndex)} x2={xi(hoverIndex)} y1={PRICE_T - 6} y2={VOL_B} stroke="#e6edf5" strokeOpacity="0.45" strokeDasharray="3 3" />
              <line x1={PLOT_L} x2={PLOT_R} y1={scale.y(hoverBar.c)} y2={scale.y(hoverBar.c)} stroke="#e6edf5" strokeOpacity="0.45" strokeDasharray="3 3" />
              <circle cx={xi(hoverIndex)} cy={scale.y(hoverBar.c)} r="3" fill="#e6edf5" />
              <rect x={PLOT_R + 2} y={scale.y(hoverBar.c) - 7} width={W - PLOT_R - 4} height="14" rx="3" fill="#8fc7ff" />
              <text x={PLOT_R + 6} y={scale.y(hoverBar.c) + 3.5} fill={INK} fontSize="9.5" fontWeight="700">{priceText(hoverBar.c)}</text>
            </g>
          ) : null}

          {scale && hasAnatomy ? (
            <CycleStructureOverlay anatomy={anatomy} x={x} y={scale.y} xMin={PLOT_L} xMax={PLOT_R} yTop={PRICE_T} yBottom={PRICE_B}
              inView={inView} priceText={priceText} currentPrice={currentPrice} selected={inspected}
              showLevels={showLevels} showPivots={showLevels} onInspect={inspect} onHover={setHoverItem} />
          ) : null}

          {!n ? (
            <text x={W / 2} y={PRICE_B / 2} fill={AXIS_TEXT} fontSize="12" textAnchor="middle">
              {busy ? busyLabel : 'No candles for this view yet'}
            </text>
          ) : null}
        </svg>
        {busy ? <span className="chart-read-chart__busy" data-testid="chart-read-chart-busy">{busyLabel}</span> : null}
      </div>

      {hasAnatomy && showLevels && (pivotChips.length || levelChips.length) ? (
        <div className="chart-read-chart__chips" data-testid="chart-pivot-chips" role="group" aria-label="Cycle pivots and levels">
          {pivotChips.map((pivot) => {
            const onChart = inView(pivot.timestamp);
            const active = inspected?.type === 'pivot' && inspected.key === pivot.key;
            return (
              <button key={pivot.key} type="button" className={`chart-chip${active ? ' is-active' : ''}${onChart ? '' : ' is-offchart'}`}
                aria-pressed={active} data-testid={`chart-chip-${pivot.key}`}
                title={`${pivot.label || cyclePivotBadge(pivot.key)} · ${pivot.date || ''} · ${priceText(pivot.price)}${onChart ? '' : ' · outside this view'}`}
                onClick={() => inspectAndReveal({ type: 'pivot', key: pivot.key })}
                onMouseEnter={() => setHoverItem({ type: 'pivot', key: pivot.key })} onMouseLeave={() => setHoverItem(null)}>
                <strong>{cyclePivotBadge(pivot.key)}</strong> {priceText(pivot.price)}
              </button>
            );
          })}
          {levelChips.map((level) => {
            const active = inspected?.type === 'level' && inspected.key === level.key;
            return (
              <button key={level.key} type="button" className={`chart-chip chart-chip--level${active ? ' is-active' : ''}`}
                aria-pressed={active} data-testid={`chart-chip-${level.key}`} style={{ borderColor: level.color }}
                onClick={() => inspect({ type: 'level', key: level.key })}
                onMouseEnter={() => setHoverItem({ type: 'level', key: level.key })} onMouseLeave={() => setHoverItem(null)}>
                <span style={{ color: level.color }}>{level.label}</span> {priceText(level.price)}
              </button>
            );
          })}
        </div>
      ) : null}

      {hasAnatomy ? <InspectCard info={info} pinned={Boolean(selected) && !hoverItem} onClose={() => setSelected(null)} /> : null}
    </div>
  );
}
