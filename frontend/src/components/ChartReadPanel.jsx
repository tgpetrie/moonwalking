import React from 'react';

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

  const { summary, direction, lower_area, upper_area, trading_activity, confidence, watch_next, symbol, timeframe, window_hours } = data;
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
