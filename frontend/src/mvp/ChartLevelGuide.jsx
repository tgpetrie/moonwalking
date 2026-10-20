import { UiButton, UiCard } from '../components/ui/DesignSystem.jsx';
import { dateText, priceText } from '../utils/macroChart.js';
import disclosures from '../utils/chartDisclosures.json';

export function distanceText(price, close) {
  if (![price, close].every((p) => Number.isFinite(p) && p > 0)) return 'Distance unavailable';
  const percent = (price / close - 1) * 100;
  if (Math.abs(percent) < 0.05) return 'At the reference close (within 0.05%)';
  return `${percent > 0 ? '+' : '−'}${Math.abs(percent).toLocaleString('en-US', { maximumFractionDigits: 1, minimumFractionDigits: 1 })}% · ${percent > 0 ? 'above' : 'below'} reference close`;
}

export function guideEvidence(macro, recent, historical, nextRun, weeklyRun) {
  const observed = recent.map((p) => ({ id: `recent:${p.id}`, title: `Recent ${p.type}`, price: p.price, anchors: [p], kind: 'observed' }));
  const anchors = historical.map((p) => ({ id: `anchor:${p.id}`, title: `Historical ${p.label}`, price: p.price, anchors: [p], kind: 'observed' }));
  const calculated = macro.error ? [] : [0.5, 0.618, 0.786, 1, 1.618].map((ratio) => ({
    id: `ratio:${ratio}`, ratio, kind: 'calculated', anchors: macro.anchors,
    title: ratio === 1 ? 'Selected swing high' : ratio > 1 ? 'Beyond-high extension' : `${(ratio * 100).toFixed(1)}% recovery`,
    price: macro.levels.find((p) => p.ratio === ratio).price,
  }));
  const nearby = [...(nextRun?.above || []), ...(nextRun?.below || [])].map((p) => ({
    id: `next:${p.id}`, title: p.display_label, price: p.price,
    anchors: [p], kind: 'observed', scope: 'next_run', baseline: nextRun.reference.close,
  }));
  nearby.push(...[...(weeklyRun?.above || []), ...(weeklyRun?.below || [])].map((p) => ({
    id: `weekly:${p.id}`, title: `Weekly ${p.display_label.toLowerCase()}`, price: p.price,
    anchors: [p], kind: 'observed', scope: 'weekly_run', baseline: weeklyRun.reference.close,
  })));
  return { nearby, observed, anchors, calculated };
}

export default function ChartLevelGuide({ macro, nextRun, weeklyRun, evidence, latest, currency, interval, selectedId, onSelect, onInspect, focusRange }) {
  const format = (p) => priceText(p, currency);
  const all = [...evidence.nearby, ...evidence.observed, ...evidence.anchors, ...evidence.calculated];
  const selected = all.find((p) => p.id === selectedId);
  const row = (p) => <div className="macro-guide-row" key={p.id}>
    <div><strong>{format(p.price)}</strong><span>{p.title}</span><small>{distanceText(p.price, p.baseline ?? latest.close)}</small>{['next_run', 'weekly_run'].includes(p.scope) && <><small>Turn {dateText(p.anchors[0].extreme_time ?? p.anchors[0].time)} · Confirmed {dateText(p.anchors[0].confirmed_at)} UTC</small>{nextRun.reference && nextRun.reference.low <= p.price && p.price <= nextRun.reference.high && <small>Already inside the latest completed daily range</small>}</>}</div>
    <UiButton size="sm" variant={selectedId === p.id ? 'primary' : 'secondary'} aria-label={`Explain ${p.title}`} aria-pressed={selectedId === p.id} aria-controls="macro-level-explanation" onClick={() => onSelect(p.id)}>Explain</UiButton>
  </div>;
  return <UiCard className="macro-reading macro-level-guide" tone="subtle" id="macro-future">
    <span className="macro-label">Daily swing and weekly cycle</span><h2>Nearby references for the current move</h2>
    <p>These are observed checkpoints above and below price, sorted by price distance. They do not predict the run’s peak, a guaranteed pullback, or when a level will be reached.</p>
    <p>{disclosures.daily_pivot_study} <a className="macro-timing-link" href={disclosures.study_source} target="_blank" rel="noreferrer">Study scope and limitations</a></p>
    {nextRun.reference && <>
      <h3>Daily swing · recent 90-day structure</h3>
      <p className="next-run-baseline">Daily close {format(nextRun.reference.close)} · Completed through {dateText(nextRun.reference.end - 1)} UTC. Not a live quote.</p>
      <p>Latest completed daily range: {format(nextRun.reference.low)}–{format(nextRun.reference.high)}. Prices inside this range have already been spanned by that candle.</p>
      <p>{nextRun.outside_range.above.length ? `Prior highs beyond that daily high: ${nextRun.outside_range.above.map((p) => `${format(p.price)} (${dateText(p.extreme_time ?? p.time)})`).join(', ')}.` : 'No confirmed daily high above that candle’s high exists in the recent 90-day scope. The latest high is still a candle observation; no future peak is established.'}</p>
      <p>Scope: {dateText(nextRun.start)}–{dateText(nextRun.end - 1)} UTC · Up to {nextRun.lookback_days} days · {nextRun.confirmation} completed daily candles each side to confirm a turn. This scope is a display choice, not a tested edge. Older macro levels are separate below.</p>
      <div className="macro-scenario-grid macro-next-run-grid">
        <div><h3>Prior highs above the close</h3><p>Prior high 1 (H1 in the Daily chart view) is the closest confirmed daily high above the dated close in this scope. Prior highs 2 and 3 are farther observations, not a promised sequence.</p>{evidence.nearby.filter((p) => p.scope === 'next_run' && p.anchors[0].type === 'high').map(row)}{!nextRun.above.length && <p>No confirmed daily high above the close in this scope. No next-run upside level is established; we do not substitute an old cycle calculation.</p>}</div>
        <div><h3>Prior lows below the close</h3><p>Prior low 1 (L1 in the Daily chart view) is the closest confirmed daily low below the dated close. Prior lows 2 and 3 are farther observations, not proven floors.</p>{evidence.nearby.filter((p) => p.scope === 'next_run' && p.anchors[0].type === 'low').map(row)}{!nextRun.below.length && <p>No confirmed daily low below the close in this scope. No downside reference is available.</p>}</div>
      </div>
      {nextRun.at.length > 0 && <p>{nextRun.at.length} confirmed turning reference(s) equal the dated close; they have no above/below distance and are excluded from the high/low ranking.</p>}
    </>}
    {weeklyRun?.reference && <section aria-label="Weekly cycle references">
      <h3>Weekly cycle · separate from the daily swing</h3>
      <p>Weekly close {format(weeklyRun.reference.close)} · Completed through {dateText(weeklyRun.reference.end - 1)} UTC. Distances below use this weekly close. Scope: {dateText(weeklyRun.start)}–{dateText(weeklyRun.end - 1)} UTC; {weeklyRun.confirmation} complete weeks each side to confirm a turn. A weekly reference can already be inside the later daily range.</p>
      <p>{disclosures.weekly_level_study}</p>
      <div className="macro-scenario-grid">
        <div><h3>Weekly highs above the weekly close</h3>{evidence.nearby.filter((p) => p.scope === 'weekly_run' && p.anchors[0].type === 'high').map(row)}{!weeklyRun.above.length && <p>No confirmed weekly high above this weekly close in the one-year scope.</p>}</div>
        <div><h3>Weekly lows below the weekly close</h3>{evidence.nearby.filter((p) => p.scope === 'weekly_run' && p.anchors[0].type === 'low').map(row)}{!weeklyRun.below.length && <p>No confirmed weekly low below this weekly close in the one-year scope.</p>}</div>
      </div>
    </section>}
    <details className="macro-advanced macro-long-range"><summary>Long-range macro calculations (separate from the next run)</summary>
    <p>These measure the selected historical decline. They are not next-run targets. A large distance from today’s price does not become plausible simply because a Fibonacci ratio produces it.</p>
    <p className="macro-guide-baseline">Distances use {format(latest.close)} · {interval === 604800 ? 'weekly' : 'daily'} candle completed through {dateText(latest.end - 1)} UTC. This is the analysis close, not a live quote.</p>
    <div className="macro-scenario-grid">
      <div><h3>Recent turning levels</h3><p>Recent does not necessarily mean close to the current price.</p>{evidence.observed.length ? evidence.observed.map(row) : <p>No confirmed recent turns in this view.</p>}</div>
      <div><h3>Calculated recovery references</h3><p>These measure part of the selected historical decline. Their distance may be substantial.</p>{evidence.calculated.filter((p) => p.ratio < 1).map(row)}{macro.error && <p>Unavailable: a confirmed high followed by a lower confirmed low is needed.</p>}</div>
      <div><h3>Selected high and extension</h3><p>Returning to a selected swing high differs from setting a new high across the available history.</p>{evidence.calculated.filter((p) => p.ratio >= 1).map(row)}{!macro.error && <p>The macro low the calculation is anchored to: <strong>{format(macro.anchors[1].price)}</strong> ({distanceText(macro.anchors[1].price, latest.close)}). {latest.close < macro.anchors[1].price ? 'The analysis close is already below this historical low.' : 'This is a historical anchor, not a proven floor.'}</p>}</div>
    </div>
    <div className="macro-guide-anchors" role="group" aria-label="Explain historical anchors">
      {evidence.anchors.map((p) => <UiButton key={p.id} size="sm" variant={selectedId === p.id ? 'primary' : 'secondary'} aria-pressed={selectedId === p.id} aria-controls="macro-level-explanation" onClick={() => onSelect(p.id)}>Explain {p.title}</UiButton>)}
    </div>
    </details>
    <div id="macro-level-explanation" className="macro-level-explanation" aria-live="polite">
      {selected ? <>
        <h3>{selected.title} · {format(selected.price)}</h3><p>{distanceText(selected.price, selected.baseline ?? latest.close)}</p>
        {selected.kind === 'calculated' ? <>
          <p>Calculation: {format(selected.anchors[1].price)} + {selected.ratio} × ({format(selected.anchors[0].price)} − {format(selected.anchors[1].price)}) = {format(selected.price)}. Arithmetic uses unrounded prices on a linear price scale, even when the chart display is logarithmic.</p>
          <p>{selected.ratio > 1 ? 'This extends beyond the selected high. It does not establish that a breakout will occur.' : 'This measures recovery of the old decline, not the percentage return from the current close.'} Nearby price action must be assessed separately; this level is not confirmed resistance.</p>
        </> : <p>This is an observed confirmed {selected.anchors[0].type}, not a predicted destination or a proven support/resistance level.</p>}
        <div className="macro-guide-sources">{selected.anchors.map((p) => <p key={p.id}><strong>{p.type === 'high' ? 'High' : 'Low'} {format(p.price)}</strong> · Actual extreme {dateText(p.extreme_time ?? p.time)} UTC · Candle begins {dateText(p.time)} UTC · Confirmed {dateText(p.confirmed_at)} UTC</p>)}</div>
        <p>The turn could be identified by this confirmation rule only from its confirmation time, not on the earlier extreme date.</p>
        <p>{selected.kind === 'observed' ? ((selected.baseline ?? latest.close) < selected.price ? 'The dated close is below this historical observation.' : (selected.baseline ?? latest.close) > selected.price ? 'The dated close is above this historical observation.' : 'The dated close equals this historical observation.') : 'The calculation uses the selected macro low. A recovery reference can be below the current close if price has already passed it.'} No probability or arrival date is established.</p>
        <UiButton size="sm" onClick={() => onInspect(Math.min(...selected.anchors.map((p) => p.extreme_time ?? p.time)), Math.max(...selected.anchors.map((p) => p.extreme_time ?? p.time)))}>View source candles</UiButton>
      </> : <p>Select Explain on a level or historical letter to see its source dates, calculation and conditions. Selected source candles are highlighted on the chart.</p>}
    </div>
    {focusRange && <p>Future levels remain listed while you inspect the past. Fit history returns to the full history without enabling long-range overlays. Inspection does not change the analysis interval or replay cutoff.</p>}
    <a className="macro-timing-link" href="#macro-timing">Explore historical dates, durations and reactions</a>
  </UiCard>;
}
