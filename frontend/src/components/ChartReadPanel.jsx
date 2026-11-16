import React from 'react';
import WaveStructureOverlay, {
  WAVE_ADVANCE_COLOR, WAVE_BREAK_COLOR, WAVE_COLOR, WAVE_DECLINE_COLOR,
  plainPrice, waveIsDrawable, wavePatternLabel, wavePrices,
} from './WaveStructureOverlay.jsx';
import SwingHistoryOverlay, {
  SWING_DOWN_COLOR, SWING_FLAT_COLOR, SWING_UP_COLOR, swingsInView,
} from './SwingHistoryOverlay.jsx';
import CycleReadSection from './CycleReadSection.jsx';

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

// The three views. The backend sends the same list; this is the fallback.
export const CHART_HORIZONS = [
  { key: 'short', label: 'Short-term', detail: '15-minute candles · ~3 days' },
  { key: 'swing', label: 'Swing', detail: '1-hour candles · ~12 days' },
  { key: 'macro', label: 'Macro', detail: '4-hour candles · ~1 month' },
  { key: 'cycle', label: 'Cycle (Multi-Year)', detail: 'Daily candles · multi-year history' },
];

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

const wavePrice = (value) => plainPrice(value) || '—';

function HorizonSwitcher({ horizons, horizon, onChange, busy }) {
  if (typeof onChange !== 'function') return null;
  const list = Array.isArray(horizons) && horizons.length ? horizons : CHART_HORIZONS;
  const active = list.find((h) => h.key === horizon) || list.find((h) => h.key === 'swing') || list[0];
  return (
    <div style={styles.horizonRow}>
      <div className="mini-toggle" role="group" aria-label="Chart read time horizon" style={{ marginTop: 0 }} data-testid="chart-read-horizons">
        {list.map((h) => (
          <button key={h.key} type="button" className={`mini-toggle-btn ${active.key === h.key ? 'active' : ''}`}
            aria-pressed={active.key === h.key} title={h.detail} onClick={() => onChange(h.key)}>
            {h.key === 'cycle' ? 'Cycle (Multi-Year)' : h.label}
          </button>
        ))}
      </div>
      <span style={styles.meta} data-testid="chart-read-horizon-detail">{busy ? 'Reading this view…' : active.detail}</span>
    </div>
  );
}

// Close line of the candles the read used, with every confirmed swing marked
// and the setup drawn on top.
function StructureChart({ wave }) {
  const bars = (wave.chart?.candles || []).filter((c) => Array.isArray(c) && c.length >= 5
    && c.slice(0, 5).every(Number.isFinite) && c[1] > 0).sort((a, b) => a[0] - b[0]);
  const drawable = waveIsDrawable(wave);
  const history = wave.swing_history;
  const pointTimes = [...(wave.wave_points || []), ...(history?.swings || [])].map((p) => p.ts).filter(Number.isFinite);
  const firstTime = bars.length ? bars[0][0] : Math.min(...pointTimes);
  const lastTime = bars.length ? bars[bars.length - 1][0] : Math.max(...pointTimes);
  const prices = [...bars.flatMap((c) => [c[1], c[2]]), ...wavePrices(wave, firstTime),
    ...swingsInView(history, firstTime).map((s) => s.price)];
  if (!prices.length || !Number.isFinite(firstTime) || !Number.isFinite(lastTime)) return null;
  const low = Math.min(...prices);
  const high = Math.max(...prices);
  const pad = Math.max((high - low) * 0.14, high * 0.001);
  const floor = Math.max(0, low - pad);
  const ceiling = high + pad;
  const x = (time) => 12 + (time - firstTime) / Math.max(lastTime - firstTime, 1) * 616;
  const y = (price) => 18 + (ceiling - price) / (ceiling - floor) * 224;
  const day = (time) => new Date(time * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  return (
    <svg viewBox="0 0 640 276" style={styles.waveSvg} role="img"
      aria-label={`Price chart with the setup drawn on it: ${wave.story?.headline || history?.headline || 'recent swings'}`} data-testid="chart-read-wave-chart">
      {bars.map((c) => <line key={c[0]} x1={x(c[0])} x2={x(c[0])} y1={y(c[2])} y2={y(c[1])} stroke="#ffffff1c" />)}
      {bars.length >= 2 && <polyline fill="none" stroke="#e6edf588" strokeWidth="1.1"
        points={bars.map((c) => `${x(c[0])},${y(c[4])}`).join(' ')} />}
      <SwingHistoryOverlay history={history} x={x} y={y} firstTime={firstTime} xMax={628} priceText={wavePrice} compact />
      {drawable && <WaveStructureOverlay wave={wave} x={x} y={y} xMin={12} xMax={628} firstTime={firstTime} priceText={wavePrice} compact />}
      <text x="12" y="268" fill="#a3acb9" fontSize="10">{day(firstTime)}</text>
      <text x="628" y="268" fill="#a3acb9" fontSize="10" textAnchor="end">{day(lastTime)}</text>
    </svg>
  );
}

function StoryStrip({ story, up }) {
  const steps = story?.steps || [];
  if (!steps.length) return null;
  const moveColor = up ? WAVE_ADVANCE_COLOR : WAVE_DECLINE_COLOR;
  const color = (step) => (step.key === 'breaks' ? WAVE_BREAK_COLOR : step.key === 'prior_move' ? moveColor : WAVE_COLOR);
  return (
    <ol style={styles.storyStrip} data-testid="chart-read-story">
      {steps.map((step) => (
        <li key={step.key} style={{ ...styles.storyStep, borderTopColor: color(step) }} data-testid={`chart-read-step-${step.key}`}>
          <span style={styles.storyTitle}>
            <span style={{ ...styles.storyNumber, background: color(step) }} aria-hidden="true">{step.number || '!'}</span>
            <strong style={{ color: color(step) }}>{step.title}</strong>
          </span>
          <span style={styles.storyText}>{step.text}</span>
        </li>
      ))}
    </ol>
  );
}

function WhyItMatters({ items }) {
  if (!items?.length) return null;
  return (
    <div style={styles.whyBlock} data-testid="chart-read-why">
      <p style={styles.watchLabel}>Why this matters</p>
      <div style={styles.chips}>
        {items.map((item) => {
          const against = item.state === 'opposed';
          const color = against ? 'var(--sentiment-neg)' : 'var(--sentiment-pos)';
          return (
            <span key={item.name} style={{ ...styles.whyBadge, borderColor: against ? 'rgba(255,107,138,0.3)' : 'rgba(69,255,179,0.22)' }}
              title={item.detail || item.technical}>
              <span style={{ color, fontWeight: 700 }}>{against ? '✕' : '✓'} {item.plain}</span>
              <span style={styles.whyTechnical} data-technical="true">{item.technical}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

function TechnicalDetails({ wave }) {
  if (!waveIsDrawable(wave)) return null;
  const fib = wave.fib_ratios || {};
  const ratio = (value) => (Number.isFinite(value) ? value.toFixed(2) : null);
  const points = (wave.wave_points || []).filter((p) => p.label !== 'start')
    .map((p) => `${p.label}${p.confirmed === false ? ' (forming)' : ''} ${wavePrice(p.price)}`).join(' · ');
  return (
    <details style={styles.technical} data-testid="chart-read-technical">
      <summary style={styles.technicalSummary}>Technical details</summary>
      <ul style={styles.technicalList}>
        <li>Elliott wave label: {wavePatternLabel(wave)}</li>
        {points && <li>Wave points: {points}</li>}
        {ratio(fib.b_retrace_of_a) && <li>B / A: {ratio(fib.b_retrace_of_a)} (the counter-swing gave back this share of the first swing)</li>}
        {ratio(fib.c_projection_of_a) && <li>C / A: {ratio(fib.c_projection_of_a)} (size of the second swing against the first)</li>}
        {wave.projected_c_zone && <li>The shaded zone spans 0.618 to 1.618 of wave A, measured from wave B.</li>}
        {wave.summary && <li>{wave.summary}</li>}
      </ul>
    </details>
  );
}

function ChartLegend({ history }) {
  if (!swingsInView(history).length) return null;
  const item = (color, glyph, text) => (
    <span style={styles.legendItem}><span style={{ color }} aria-hidden="true">{glyph}</span>{text}</span>
  );
  return (
    <p style={styles.legend} data-testid="chart-read-legend">
      {item(SWING_UP_COLOR, '▲', 'dip that held higher')}
      {item(SWING_DOWN_COLOR, '▲', 'dip that went lower')}
      {item(SWING_UP_COLOR, '▼', 'peak that went higher')}
      {item(SWING_DOWN_COLOR, '▼', 'peak that fell short')}
      {item(SWING_FLAT_COLOR, '▲▼', 'level with the last one, or the first shown')}
    </p>
  );
}

function StructureSection({ wave }) {
  if (!wave || !wave.available) return null;
  const drawable = waveIsDrawable(wave);
  const history = wave.swing_history;
  const hasHistory = swingsInView(history).length > 0;
  if (!drawable && !hasHistory) return null;
  const story = wave.story || {};
  const up = wave.bias !== 'bearish';
  const confColor = CONFIDENCE_COLOR[wave.confidence_label] || 'var(--sentiment-subtext)';
  return (
    <div style={styles.waveBlock} data-testid="chart-read-wave">
      <p style={styles.watchLabel}>The setup in plain English</p>
      <p style={styles.headline} data-testid="chart-read-headline">
        {drawable ? story.headline || wave.summary : 'No clear setup in the recent swings.'}
      </p>
      {drawable && <StoryStrip story={story} up={up} />}
      {/* On a wide modal the chart and the reasons for the read sit side by side,
          so both are on screen without scrolling (see .chart-read__split). */}
      <div className="chart-read__split">
        <div className="chart-read__chart">
          <StructureChart wave={wave} />
          <ChartLegend history={history} />
        </div>
        <div className="chart-read__context">
          {hasHistory && history.headline && (
            <div style={styles.historyBlock} data-testid="chart-read-history">
              <p style={styles.watchLabel}>The bigger picture</p>
              <p style={styles.summary}><strong>{history.headline}</strong>{history.why ? ` ${history.why}` : ''}</p>
            </div>
          )}
          {drawable && <WhyItMatters items={story.why_it_matters} />}
          {drawable && (
            <div style={styles.chips}>
              <Chip color={confColor}><strong style={{ color: confColor }}>Read strength:</strong>{' '}{wave.confidence_label}</Chip>
            </div>
          )}
        </div>
      </div>
      <TechnicalDetails wave={wave} />
      <p style={styles.disclaimer}>This describes the shape of recent swings on {wave.timeframe || 'these'} candles. It has not been tested against outcomes.</p>
    </div>
  );
}

// `afterSetup` is rendered between the setup block and the range read, so the
// caller can keep something (the sell-side price row) right under the chart.
export default function ChartReadPanel({ data, loading, error, horizon, onHorizonChange, afterSetup = null }) {
  // Title and time-horizon switcher share one row to keep the chart high on screen.
  const head = (
    <div style={styles.header}>
      <span style={styles.title}>Chart Read</span>
      <HorizonSwitcher horizons={data?.horizons} horizon={horizon || data?.horizon} onChange={onHorizonChange} busy={Boolean(loading)} />
    </div>
  );

  if (loading && !data) {
    return (
      <div style={styles.wrapper}>
        {head}
        <p style={styles.loading}>Reading the chart…</p>
        {afterSetup}
      </div>
    );
  }

  if (error && !loading) {
    return (
      <div style={styles.wrapper}>
        {head}
        <p style={styles.errorText}>Chart data temporarily unavailable.</p>
        {afterSetup}
      </div>
    );
  }

  if (!data) return afterSetup;

  const { summary, direction, lower_area, upper_area, trading_activity, confidence, watch_next, timeframe, window_hours, wave_analysis } = data;
  const dirColor = DIRECTION_COLOR[direction?.label] || 'var(--sentiment-subtext)';
  const wLabel = windowLabel(window_hours, timeframe);
  const volColor = VOLUME_COLOR[trading_activity?.label] || 'var(--sentiment-subtext)';
  const confColor = CONFIDENCE_COLOR[confidence] || 'var(--sentiment-subtext)';
  const dim = { opacity: loading ? 0.55 : 1, transition: 'opacity 160ms ease' };

  return (
    <div style={styles.wrapper}>
      {head}

      {/* A view that is still loading keeps the previous read on screen, dimmed.
          The setup, its chart and the bigger picture lead; the range read follows. */}
      <div style={dim} aria-busy={Boolean(loading)}>
        <StructureSection wave={wave_analysis} />
        {(data.horizon === 'swing' || data.horizon === 'cycle') && data.top_down_confluence?.available ? (
          <div data-testid="top-down-confluence">
            <p style={styles.watchLabel}>Multi-degree context</p>
            <p style={styles.summary}>
              {data.top_down_confluence.at_multi_year_support ? 'At observed multi-year support' : 'Outside observed multi-year support'}
            </p>
            <div style={styles.chips}>
              {data.top_down_confluence.macro_log_support_box ? <Chip>Macro log support: {wavePrice(data.top_down_confluence.macro_log_support_box.low)}–{wavePrice(data.top_down_confluence.macro_log_support_box.high)}</Chip> : null}
              {data.top_down_confluence.micro_support_box ? <Chip>{data.top_down_confluence.micro_timeframe} support: {wavePrice(data.top_down_confluence.micro_support_box.low)}–{wavePrice(data.top_down_confluence.micro_support_box.high)}</Chip> : null}
              {Number.isFinite(data.top_down_confluence.micro_breakout_pivot) ? <Chip>Wave B pivot: {wavePrice(data.top_down_confluence.micro_breakout_pivot)}</Chip> : null}
            </div>
            {data.multi_year_context?.log_fib_retracements ? (
              <details style={styles.technical}>
                <summary style={styles.technicalSummary}>Cycle log Fibonacci levels</summary>
                <div style={styles.chips}>
                  {Object.entries(data.multi_year_context.log_fib_retracements).map(([ratio, value]) => (
                    <Chip key={ratio}>{ratio}: {wavePrice(value)}</Chip>
                  ))}
                </div>
              </details>
            ) : null}
          </div>
        ) : null}
        {/* Cycle view only: the gate, momentum regimes, SMA ladder, confirmation
            and invalidation levels, and the two target tiers. */}
        {data.horizon === 'cycle' ? (
          <CycleReadSection context={data.multi_year_context} top={data.top_down_confluence} regime={data.macro_industry_regime} />
        ) : null}
      </div>

      {afterSetup}

      <div style={dim}>
        <p style={styles.watchLabel} data-testid="chart-read-range-label">
          Recent range{wLabel ? <span style={styles.rangeMeta}> · {wLabel}</span> : null}
        </p>
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
      </div>

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
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: '0.4rem 0.75rem',
    marginBottom: '0.6rem',
  },
  rangeMeta: {
    fontWeight: 400,
    letterSpacing: '0.02em',
    textTransform: 'none',
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
  horizonRow: {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: '0.6rem',
    margin: 0,
  },
  summary: {
    margin: '0 0 0.65rem',
    fontSize: '0.82rem',
    lineHeight: 1.55,
    color: 'var(--sentiment-text)',
  },
  headline: {
    margin: '0 0 0.6rem',
    fontSize: '0.95rem',
    fontWeight: 700,
    lineHeight: 1.35,
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
    margin: '0 0 0.75rem',
    paddingBottom: '0.7rem',
    borderBottom: '1px solid rgba(255,255,255,0.07)',
  },
  storyStrip: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
    gap: '0.4rem',
    listStyle: 'none',
    margin: '0 0 0.55rem',
    padding: 0,
  },
  storyStep: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.25rem',
    padding: '0.5rem 0.6rem',
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.07)',
    borderTop: '2px solid',
    borderRadius: '0.45rem',
  },
  storyTitle: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
    fontSize: '0.74rem',
    lineHeight: 1.25,
  },
  storyNumber: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    flex: '0 0 auto',
    width: '1.05rem',
    height: '1.05rem',
    borderRadius: '50%',
    color: '#0c1119',
    fontSize: '0.64rem',
    fontWeight: 800,
  },
  storyText: {
    fontSize: '0.72rem',
    lineHeight: 1.45,
    color: 'var(--sentiment-subtext)',
  },
  waveSvg: {
    display: 'block',
    width: '100%',
    height: 'auto',
    margin: '0.2rem 0 0.35rem',
    background: 'rgba(12,17,25,0.6)',
    borderRadius: '0.4rem',
  },
  legend: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '0.25rem 0.8rem',
    margin: '0 0 0.6rem',
    fontSize: '0.64rem',
    color: 'var(--sentiment-muted)',
  },
  legendItem: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.25rem',
  },
  historyBlock: {
    marginBottom: '0.2rem',
  },
  whyBlock: {
    marginBottom: '0.1rem',
  },
  whyBadge: {
    display: 'inline-flex',
    flexDirection: 'column',
    gap: '0.1rem',
    padding: '0.3rem 0.6rem',
    borderRadius: '0.45rem',
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid',
    fontSize: '0.72rem',
    lineHeight: 1.25,
  },
  whyTechnical: {
    fontSize: '0.6rem',
    letterSpacing: '0.03em',
    color: 'var(--sentiment-muted)',
  },
  technical: {
    margin: '0 0 0.55rem',
  },
  technicalSummary: {
    cursor: 'pointer',
    fontSize: '0.68rem',
    color: 'var(--sentiment-muted)',
  },
  technicalList: {
    margin: '0.35rem 0 0',
    padding: '0 0 0 1.1rem',
    fontSize: '0.7rem',
    lineHeight: 1.5,
    color: 'var(--sentiment-subtext)',
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
