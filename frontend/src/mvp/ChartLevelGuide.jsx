import { UiButton, UiCard } from '../components/ui/DesignSystem.jsx';
import { dateText, priceText } from '../utils/macroChart.js';

export function distanceText(price, close) {
  if (![price, close].every((p) => Number.isFinite(p) && p > 0)) return 'Distance unavailable';
  const percent = (price / close - 1) * 100;
  if (Math.abs(percent) < 0.05) return 'At the reference close (within 0.05%)';
  return `${percent > 0 ? '+' : '−'}${Math.abs(percent).toLocaleString('en-US', { maximumFractionDigits: 1, minimumFractionDigits: 1 })}% · ${percent > 0 ? 'above' : 'below'} reference close`;
}

export function guideEvidence(macro, recent, historical, nextRun) {
  const observed = recent.map((p) => ({ id: `recent:${p.id}`, title: `Recent ${p.type}`, price: p.price, anchors: [p], kind: 'observed' }));
  const anchors = historical.map((p) => ({ id: `anchor:${p.id}`, title: `Historical ${p.label}`, price: p.price, anchors: [p], kind: 'observed' }));
  const calculated = macro.error ? [] : [0.5, 0.618, 0.786, 1, 1.618].map((ratio) => ({
    id: `ratio:${ratio}`, ratio, kind: 'calculated', anchors: macro.anchors,
    title: ratio === 1 ? 'Selected swing high' : ratio > 1 ? 'Beyond-high extension' : `${(ratio * 100).toFixed(1)}% recovery`,
    price: macro.levels.find((p) => p.ratio === ratio).price,
  }));
  const nearby = [...(nextRun?.above || []), ...(nextRun?.below || [])].map((p) => ({
    id: `next:${p.id}`, title: `${p.label} · Prior daily ${p.type}`, price: p.price,
    anchors: [p], kind: 'observed', scope: 'next_run', baseline: nextRun.reference.close,
  }));
  return { nearby, observed, anchors, calculated };
}

export default function ChartLevelGuide({ macro, nextRun, evidence, latest, currency, interval, selectedId, onSelect, onInspect, focusRange }) {
  const format = (p) => priceText(p, currency);
  const all = [...evidence.nearby, ...evidence.observed, ...evidence.anchors, ...evidence.calculated];
  const selected = all.find((p) => p.id === selectedId);
  const row = (p) => <div className="macro-guide-row" key={p.id}>
    <div><strong>{format(p.price)}</strong><span>{p.title}</span><small>{distanceText(p.price, p.baseline ?? latest.close)}</small>{p.scope === 'next_run' && <small>Turn {dateText(p.anchors[0].extreme_time ?? p.anchors[0].time)} · Confirmed {dateText(p.anchors[0].confirmed_at)} UTC</small>}</div>
    <UiButton size="sm" variant={selectedId === p.id ? 'primary' : 'secondary'} aria-label={`Explain ${p.title}`} aria-pressed={selectedId === p.id} aria-controls="macro-level-explanation" onClick={() => onSelect(p.id)}>Explain</UiButton>
  </div>;
  return <UiCard className="macro-reading macro-level-guide" tone="subtle" id="macro-future">
    <span className="macro-label">Next run · nearby daily structure</span><h2>Levels to watch on the next recovery</h2>
    <p>These are observed checkpoints above and below price, sorted by price distance. They do not predict the run’s peak, a guaranteed pullback, or when a level will be reached.</p>
    {nextRun.reference && <>
      <p className="next-run-baseline">Daily close {format(nextRun.reference.close)} · Completed through {dateText(nextRun.reference.end - 1)} UTC. Not a live quote.</p>
      <p>Scope: {dateText(nextRun.start)}–{dateText(nextRun.end - 1)} UTC · Up to {nextRun.lookback_days} days · {nextRun.confirmation} completed daily candles each side to confirm a turn. This scope is a display choice, not a tested edge. Older macro levels are separate below.</p>
      <div className="macro-scenario-grid macro-next-run-grid">
        <div><h3>If the recovery continues</h3><p>R1 is the closest prior daily high above the dated close in this scope. R2 and R3 are farther references to reassess after lower ones are cleared and held; they are not a promised sequence.</p>{evidence.nearby.filter((p) => p.anchors[0].type === 'high').map(row)}{!nextRun.above.length && <p>No confirmed daily high above the close in this scope. No next-run upside level is established; we do not substitute an old cycle calculation.</p>}</div>
        <div><h3>If price pulls back</h3><p>S1 is the closest prior daily low below the dated close. A daily close below it would put the next lower reference in focus. These are prior lows, not proven floors.</p>{evidence.nearby.filter((p) => p.anchors[0].type === 'low').map(row)}{!nextRun.below.length && <p>No confirmed daily low below the close in this scope. Downside support is unestablished.</p>}</div>
      </div>
      {nextRun.at.length > 0 && <p>{nextRun.at.length} confirmed turning reference(s) equal the dated close; they have no above/below distance and are excluded from R/S ranking.</p>}
    </>}
    <details className="macro-advanced macro-long-range"><summary>Long-range macro calculations (separate from the next run)</summary>
    <p>These measure the selected historical decline. They are not next-run targets. A large distance from today’s price does not become plausible simply because a Fibonacci ratio produces it.</p>
    <p className="macro-guide-baseline">Distances use {format(latest.close)} · {interval === 604800 ? 'weekly' : 'daily'} candle completed through {dateText(latest.end - 1)} UTC. This is the analysis close, not a live quote.</p>
    <div className="macro-scenario-grid">
      <div><h3>Recent turning levels</h3><p>Recent does not necessarily mean close to the current price.</p>{evidence.observed.length ? evidence.observed.map(row) : <p>No confirmed recent turns in this view.</p>}</div>
      <div><h3>Calculated recovery references</h3><p>These measure part of the selected historical decline. Their distance may be substantial.</p>{evidence.calculated.filter((p) => p.ratio < 1).map(row)}{macro.error && <p>Unavailable: a confirmed high followed by a lower confirmed low is needed.</p>}</div>
      <div><h3>Selected high and extension</h3><p>Returning to a selected swing high differs from setting a new high across the available history.</p>{evidence.calculated.filter((p) => p.ratio >= 1).map(row)}{!macro.error && <p>Downside reference: <strong>{format(macro.anchors[1].price)}</strong> ({distanceText(macro.anchors[1].price, latest.close)}). {latest.close < macro.anchors[1].price ? 'The analysis close is already below it; the recovery anchor needs reviewing.' : 'A break below it weakens a recovery anchored there.'}</p>}</div>
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
        <p>{selected.kind === 'observed' ? ((selected.baseline ?? latest.close) < selected.price ? 'Price is below this reference. Watch for a regain, then whether subsequent completed candles hold above it.' : (selected.baseline ?? latest.close) > selected.price ? 'Price is above this reference. Watch whether a pullback holds it or closes below it.' : 'Price is at this reference. Subsequent completed candles can show which side it holds.') : 'A move below the selected low weakens a recovery anchored to that low. A recovery reference can also be below the current close if price has already passed it.'} No probability or arrival date is established.</p>
        <UiButton size="sm" onClick={() => onInspect(Math.min(...selected.anchors.map((p) => p.extreme_time ?? p.time)), Math.max(...selected.anchors.map((p) => p.extreme_time ?? p.time)))}>View source candles</UiButton>
      </> : <p>Select Explain on a level or historical letter to see its source dates, calculation and conditions. Selected source candles are highlighted on the chart.</p>}
    </div>
    {focusRange && <p>Future levels remain listed while you inspect the past. Fit history returns to the full history without enabling long-range overlays. Inspection does not change the analysis interval or replay cutoff.</p>}
    <a className="macro-timing-link" href="#macro-timing">Explore historical dates, durations and reactions</a>
  </UiCard>;
}
