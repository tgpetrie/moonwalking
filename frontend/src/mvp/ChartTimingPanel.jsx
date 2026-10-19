import { useState } from 'react';
import { UiButton, UiCard } from '../components/ui/DesignSystem.jsx';
import { dateText, priceText } from '../utils/macroChart.js';
import { historicalLegs, levelEpisodes } from '../utils/chartTiming.js';

const percent = (n) => `${n > 0 ? '+' : ''}${n.toFixed(1)}%`;
const EXIT = { above: 'Next daily candle entirely above the band', below: 'Next daily candle entirely below the band',
  gap: 'Next daily candle missing; exit unknown', pending: 'Next daily candle not yet available' };

export default function ChartTimingPanel({ macroAnchors, recentAnchors, levels, dailyCandles, asOf, currency, onFocus }) {
  const [width, setWidth] = useState(1);
  const groups = [{ name: 'Larger historical moves', anchors: macroAnchors }, { name: 'Recent historical moves', anchors: recentAnchors }];
  return <UiCard id="macro-timing" className="macro-timing-panel">
    <span className="macro-label">Dates, durations & reactions</span><h2>When to look, and what to look for</h2>
    <p>Past moves give timing context. They do not set a deadline for the next move. Use a date range below to bring that part of the chart into view.</p>
    <div className="macro-timing-moves">{groups.map(({ name, anchors }) => {
      const legs = historicalLegs(anchors, asOf);
      return <div key={name} role="group" aria-label={name}><h3>{name}</h3>{legs.length ? legs.map((leg) => <div className="macro-timing-leg" key={leg.label}>
        <div><strong>{leg.label} · {Math.round(leg.days)} days · {percent(leg.change_percent)}</strong>
          <p>{dateText(leg.start)} → {dateText(leg.end)} UTC</p><small>{priceText(leg.from, currency)} → {priceText(leg.to, currency)} · Both turns confirmed by {dateText(leg.available_at)}</small></div>
        <UiButton size="sm" onClick={() => onFocus(leg.focus_start, leg.focus_end)}>View {leg.label}</UiButton>
      </div>) : <p>Not enough confirmed turns in this view.</p>}</div>;
    })}</div>
    <div className="macro-timing-heading"><h3>What happened around the recent levels?</h3><label className="macro-select">Near-level inspection width
      <select aria-label="Near-level inspection width" value={width} onChange={(e) => setWidth(Number(e.target.value))}>
        {[0.5, 1, 2].map((n) => <option key={n} value={n}>Within ±{n}%</option>)}
      </select></label></div>
    <p>These checks use completed daily candles through {dateText(asOf - 1)} UTC, after each level became confirmable. “Near” is an adjustable inspection band, not a tested support/resistance rule. A candle touching a band does not mean price stayed there all day.</p>
    <div className="macro-timing-reactions">{levels.map((p) => {
      const result = levelEpisodes(dailyCandles, p, { asOf, widthPercent: width });
      const episodes = result.episodes.slice(-3);
      const latest = dailyCandles.at(-1);
      const distance = latest ? (p.price / latest.close - 1) * 100 : null;
      return <div className="macro-timing-level" key={p.type}>
        <h3>{p.label} · {priceText(p.price, currency)}</h3>
        <p>Turn date {dateText(p.extreme_time ?? p.time)} · Confirmable {dateText(p.confirmed_at)}</p>
        {result.error ? <p>{result.error}</p> : <>
          <p>Watch {priceText(result.lower, currency)}–{priceText(result.upper, currency)}.{distance !== null && ` The level is ${Math.abs(distance).toFixed(1)}% ${distance >= 0 ? 'above' : 'below'} the latest daily close.`}</p>
          <small>{result.episodes.length} distinct date ranges touched this band after confirmation.{result.episodes.length > 3 && ' Showing the latest three.'}</small>
          {result.missing_days > 0 && <p>{result.missing_days} daily intervals are missing after confirmation; the visit record may be incomplete.</p>}
          {!episodes.length && <p>No later daily candle has revisited this band in the available history. Watch for a first touch, then whether the next daily candle is above or below it.</p>}
          {episodes.map((event) => <div className="macro-timing-event" key={event.start}>
            <strong>{dateText(event.start)}{event.touch_days > 1 ? ` → ${dateText(event.last_touch)}` : ''} · {event.touch_days} daily candle{event.touch_days === 1 ? '' : 's'} touched</strong>
            <p>{event.approach !== 'unknown' ? `Prior candle ${event.approach} the band. ` : ''}{EXIT[event.exit] || 'Exit unresolved'}{event.exit_time !== null ? ` on ${dateText(event.exit_time)}` : ''}.</p>
            {event.next_day_close !== null && <p>Next daily close: {priceText(event.next_day_close, currency)}.</p>}
            <p>{event.followup_status === 'complete' ? `Seven days after the last touch candle closed: ${percent(event.return_7d_percent)} close-to-close.`
              : event.followup_status === 'gap' ? 'The seven-day comparison has missing candles; no return is calculated.'
                : `Seven-day review checkpoint: ${dateText(event.followup_at)} UTC. ${event.followup_at > asOf ? 'That checkpoint is after this replay cutoff.' : 'The required daily candles are not all available.'}`}</p>
            <UiButton size="sm" onClick={() => onFocus(event.focus_start, event.focus_end)}>View touch {dateText(event.start)}</UiButton>
          </div>)}
        </>}
      </div>;
    })}</div>
    <p className="macro-timing-limit">Future arrival window: not estimated from this map yet. Historical leg durations and seven-day reviews are reference points, not independent trade results or a promise of when a reference price will be reached. Daily candles cannot establish intraday touch order or continuous time spent near a level.</p>
  </UiCard>;
}
