import React from 'react';
import WaveStructureOverlay, {
  WAVE_BREAK_COLOR, WAVE_COLOR, waveIsDrawable, wavePatternLabel, wavePrices,
} from './WaveStructureOverlay.jsx';

function windowLabel(window_hours, timeframe) {
  const h = Math.round(window_hours || 0);
  if (!h) return null;
  const tfLabel = { '1h': '1-hour candles', '4h': '4-hour candles', '1d': 'daily candles', '15m': '15-min candles' }[timeframe] || `${timeframe} candles`;
  if (h <= 24) return `last ~${h} hours · ${tfLabel}`;
  const d = Math.round(h / 24);
  return `last ~${d} day${d !== 1 ? 's' : ''} · ${tfLabel}`;
}

const DIRECTION_ICON = { up: '↑', down: '↓', sideways: '↔' };
const DIRECTION_COLOR = { up: 'var(--sentiment-pos)', down: 'var(--sentiment-neg)', sideways: 'var(--sentiment-neu)' };
const VOLUME_COLOR = { high: 'var(--sentiment-pos)', normal: 'var(--sentiment-subtext)', low: 'var(--sentiment-neg)' };
const CONFIDENCE_COLOR = { high: 'var(--sentiment-pos)', medium: 'var(--sentiment-neu)', low: 'var(--sentiment-muted)' };

function Chip({ label, color, children }) {
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '0.3rem',
      padding: '0.2rem 0.55rem',
      borderRadius: '0.4rem',
      background: 'rgba(255,255,255,0.05)',
      border: '1px solid rgba(255,255,255,0.08)',
      fontSize: '0.72rem',
      color: color || 'var(--sentiment-subtext)',
      whiteSpace: 'nowrap',
    }}>
      {label && <strong style={{ color }}>{label}</strong>}
      {children}
    </span>
  );
}

function ZoneChip({ label, zone, color }) {
  if (!zone || zone.length < 2) return null;
  const [lo, hi] = zone;
  return (
    <Chip color={color}>
      <strong style={{ color }}>{label}:</strong>
      {' '}${lo}–${hi}
    </Chip>
  );
}

const wavePrice = (value) => (typeof value === 'number' && Number.isFinite(value) && value > 0
  ? `$${value.toLocaleString(undefined, { maximumSignificantDigits: 6 })}` : '—');

const FACTOR_LABEL = {
  higher_tf_trend: 'Higher-timeframe trend',
  rsi_divergence: 'RSI divergence',
  macd_divergence: 'MACD divergence',
  volume_contraction: 'Lighter wave C volume',
  bollinger_reclaim: 'Bollinger reclaim',
  ema_reclaim: 'Fast-EMA reclaim',
  prior_impulse: 'Five waves before it',
};

// Close line of the candles the wave read used, with the wave overlay on top.
function WaveMiniChart({ wave }) {
  const bars = (wave.chart?.candles || []).filter((c) => Array.isArray(c) && c.length >= 5
    && c.slice(0, 5).every(Number.isFinite) && c[1] > 0).sort((a, b) => a[0] - b[0]);
  const pointTimes = (wave.wave_points || []).map((p) => p.ts).filter(Number.isFinite);
  const firstTime = bars.length ? bars[0][0] : Math.min(...pointTimes);
  const lastTime = bars.length ? bars[bars.length - 1][0] : Math.max(...pointTimes);
  const prices = [...bars.flatMap((c) => [c[1], c[2]]), ...wavePrices(wave, firstTime)];
  if (!prices.length || !Number.isFinite(firstTime) || !Number.isFinite(lastTime)) return null;
  const low = Math.min(...prices);
  const high = Math.max(...prices);
  const pad = Math.max((high - low) * 0.1, high * 0.001);
  const floor = Math.max(0, low - pad);
  const ceiling = high + pad;
  const x = (time) => 10 + (time - firstTime) / Math.max(lastTime - firstTime, 1) * 540;
  const y = (price) => 14 + (ceiling - price) / (ceiling - floor) * 172;
  return (
    <svg viewBox="0 0 560 200" style={styles.waveSvg} role="img"
      aria-label={`Wave structure chart: ${wavePatternLabel(wave)}`} data-testid="chart-read-wave-chart">
      {bars.map((c) => <line key={c[0]} x1={x(c[0])} x2={x(c[0])} y1={y(c[2])} y2={y(c[1])} stroke="#ffffff22" />)}
      {bars.length >= 2 && <polyline fill="none" stroke="#e6edf580" strokeWidth="1"
        points={bars.map((c) => `${x(c[0])},${y(c[4])}`).join(' ')} />}
      <WaveStructureOverlay wave={wave} x={x} y={y} xMin={10} xMax={550} firstTime={firstTime} priceText={wavePrice} />
    </svg>
  );
}

function WaveStructureSection({ wave }) {
  if (!waveIsDrawable(wave)) return null;
  const fib = wave.fib_ratios || {};
  const biasColor = wave.bias === 'bullish' ? 'var(--sentiment-pos)' : wave.bias === 'bearish' ? 'var(--sentiment-neg)' : 'var(--sentiment-subtext)';
  const confColor = CONFIDENCE_COLOR[wave.confidence_label] || 'var(--sentiment-subtext)';
  const factors = (wave.confluence_factors || []).filter((f) => f.state === 'present' || f.state === 'opposed');
  const ratio = (value) => (Number.isFinite(value) ? value.toFixed(2) : null);
  return (
    <div style={styles.waveBlock} data-testid="chart-read-wave">
      <p style={styles.watchLabel}>Wave structure · {wavePatternLabel(wave)}</p>
      <WaveMiniChart wave={wave} />
      <p style={styles.summary}>{wave.summary}</p>
      <div style={styles.chips}>
        <Chip color={biasColor}><strong style={{ color: biasColor }}>Structure:</strong>{' '}{wave.bias}</Chip>
        <Chip color={confColor}><strong style={{ color: confColor }}>Wave confidence:</strong>{' '}{wave.confidence_label}</Chip>
        {ratio(fib.b_retrace_of_a) && <Chip><strong>B / A:</strong>{' '}{ratio(fib.b_retrace_of_a)}</Chip>}
        {ratio(fib.c_projection_of_a) && <Chip><strong>C / A:</strong>{' '}{ratio(fib.c_projection_of_a)}</Chip>}
        {wave.invalidation_price ? <Chip color={WAVE_BREAK_COLOR}><strong style={{ color: WAVE_BREAK_COLOR }}>Count breaks:</strong>{' '}{wavePrice(wave.invalidation_price)}</Chip> : null}
        {wave.target_price ? <Chip color={WAVE_COLOR}><strong style={{ color: WAVE_COLOR }}>Wave B level:</strong>{' '}{wavePrice(wave.target_price)}</Chip> : null}
        {factors.map((f) => (
          <Chip key={f.name} color={f.state === 'opposed' ? 'var(--sentiment-neg)' : 'var(--sentiment-pos)'}>
            {f.state === 'opposed' ? '✕' : '✓'} {FACTOR_LABEL[f.name] || f.name}{f.state === 'opposed' ? ' (against)' : ''}
          </Chip>
        ))}
      </div>
      <p style={styles.disclaimer}>Wave counts describe swing structure on {wave.timeframe || 'these'} candles. They are not outcome-validated.</p>
    </div>
  );
}

export default function ChartReadPanel({ data, loading, error }) {
  if (loading) {
    return (
      <div style={styles.wrapper}>
        <div style={styles.header}>
          <span style={styles.title}>Chart Read</span>
        </div>
        <p style={styles.loading}>Reading the chart…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.wrapper}>
        <div style={styles.header}>
          <span style={styles.title}>Chart Read</span>
        </div>
        <p style={styles.errorText}>Chart data temporarily unavailable.</p>
      </div>
    );
  }

  if (!data) return null;

  const { summary, direction, lower_area, upper_area, trading_activity, confidence, watch_next, symbol, timeframe, window_hours, wave_analysis } = data;
  const dirColor = DIRECTION_COLOR[direction?.label] || 'var(--sentiment-subtext)';
  const wLabel = windowLabel(window_hours, timeframe);
  const volColor = VOLUME_COLOR[trading_activity?.label] || 'var(--sentiment-subtext)';
  const confColor = CONFIDENCE_COLOR[confidence] || 'var(--sentiment-subtext)';

  return (
    <div style={styles.wrapper}>
      <div style={styles.header}>
        <span style={styles.title}>Chart Read</span>
        {wLabel && <span style={styles.meta}>{wLabel}</span>}
      </div>

      <p style={styles.summary}>{summary}</p>

      <div style={styles.chips}>
        <Chip color={dirColor}>
          <strong style={{ color: dirColor }}>Direction:</strong>
          {' '}{DIRECTION_ICON[direction?.label]} {direction?.label}
        </Chip>

        <ZoneChip
          label="Lower area"
          zone={lower_area?.zone}
          color="rgba(69,255,179,0.75)"
        />

        <ZoneChip
          label="Upper area"
          zone={upper_area?.zone}
          color="rgba(174,75,245,0.75)"
        />

        <Chip color={volColor}>
          <strong style={{ color: volColor }}>Activity:</strong>
          {' '}{trading_activity?.label}
        </Chip>

        <Chip color={confColor}>
          <strong style={{ color: confColor }}>Confidence:</strong>
          {' '}{confidence}
        </Chip>
      </div>

      {Array.isArray(watch_next) && watch_next.length > 0 && (
        <div style={styles.watchNext}>
          <p style={styles.watchLabel}>What to watch next</p>
          <ul style={styles.watchList}>
            {watch_next.map((item, i) => (
              <li key={i} style={styles.watchItem}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      <WaveStructureSection wave={wave_analysis} />

      <p style={styles.disclaimer}>
        Descriptive only · Not financial advice
      </p>
    </div>
  );
}

const styles = {
  wrapper: {
    marginTop: '0.75rem',
    padding: '0.85rem 1rem',
    background: 'rgba(255,255,255,0.025)',
    border: '1px solid rgba(255,255,255,0.07)',
    borderRadius: '0.6rem',
  },
  header: {
    display: 'flex',
    alignItems: 'baseline',
    gap: '0.6rem',
    marginBottom: '0.5rem',
  },
  title: {
    fontSize: '0.75rem',
    fontWeight: 700,
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
    color: 'var(--sentiment-subtext)',
  },
  meta: {
    fontSize: '0.67rem',
    color: 'var(--sentiment-muted)',
  },
  summary: {
    margin: '0 0 0.65rem',
    fontSize: '0.82rem',
    lineHeight: 1.55,
    color: 'var(--sentiment-text)',
  },
  chips: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '0.35rem',
    marginBottom: '0.65rem',
  },
  watchNext: {
    marginBottom: '0.5rem',
  },
  watchLabel: {
    margin: '0 0 0.3rem',
    fontSize: '0.7rem',
    fontWeight: 600,
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
    color: 'var(--sentiment-muted)',
  },
  watchList: {
    margin: 0,
    padding: '0 0 0 1.1rem',
  },
  watchItem: {
    fontSize: '0.77rem',
    color: 'var(--sentiment-subtext)',
    lineHeight: 1.5,
    marginBottom: '0.2rem',
  },
  waveBlock: {
    margin: '0.25rem 0 0.6rem',
    paddingTop: '0.6rem',
    borderTop: '1px solid rgba(255,255,255,0.07)',
  },
  waveSvg: {
    display: 'block',
    width: '100%',
    height: 'auto',
    margin: '0.2rem 0 0.5rem',
    background: 'rgba(12,17,25,0.6)',
    borderRadius: '0.4rem',
  },
  disclaimer: {
    margin: 0,
    fontSize: '0.63rem',
    color: 'var(--sentiment-muted)',
    opacity: 0.7,
  },
  loading: {
    margin: 0,
    fontSize: '0.78rem',
    color: 'var(--sentiment-muted)',
  },
  errorText: {
    margin: 0,
    fontSize: '0.78rem',
    color: 'var(--sentiment-muted)',
    opacity: 0.7,
  },
};
