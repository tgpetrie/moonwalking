import React from 'react';
import { plainPrice, waveZone } from './WaveStructureOverlay.jsx';

// The one compact strip at the top of the coin modal. It leads with what the
// 1h chart read says, puts the concrete price levels in one row, and keeps the
// live tape as a pill. The tape posture is never dropped: a risk posture shows
// its label on the pill and its reason on a line of its own.

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const positive = (value) => finite(value) && value > 0;

const defaultPlanPrice = (value) => (positive(value)
  ? `$${value.toLocaleString(undefined, { maximumFractionDigits: value >= 1000 ? 2 : value >= 1 ? 4 : value >= 0.01 ? 6 : 8 })}`
  : '—');

const sentence = (text) => String(text || '').trim().replace(/\.$/, '');

/**
 * Everything the strip shows, as plain data.
 *
 * `wave` is the 1h `wave_analysis`, `plan` the risk-levels plan, `posture` the
 * tape posture ({label, tone, headline, supports}), `earlyRead` the fast
 * 1m/3m lean and `liveRanking` the live tape rank.
 */
export function buildCoinStrip({
  wave = null, plan = null, posture = null, earlyRead = null, liveRanking = null,
  chartLoading = false, formatPlanPrice = defaultPlanPrice,
} = {}) {
  const usable = Boolean(wave && wave.available);
  const chartHeadline = usable ? wave.short_headline || null : null;
  const tapeHeadline = posture?.headline ? `${posture.label ? `${posture.label} · ` : ''}${sentence(posture.headline)}` : null;
  let headline = chartHeadline;
  let source = 'chart';
  if (!headline) {
    if (chartLoading) {
      headline = 'Reading the chart…';
      source = 'loading';
    } else {
      // No chart history: the tape posture carries the headline instead.
      headline = tapeHeadline || 'No chart history or live tape for this coin yet.';
      source = 'tape';
    }
  }

  const stop = plan?.available ? plan.stop || {} : {};
  const profit = plan?.available ? plan.profit || {} : {};
  const up = wave?.bias !== 'bearish';
  const correction = usable && String(wave.active_pattern || '').startsWith('abc');
  const zone = correction ? waveZone(wave) : null;
  const target = correction && positive(wave.target_price) ? wave.target_price : null;
  const price = (value) => (positive(value) ? formatPlanPrice(value) : '—');

  const levels = [
    zone
      ? {
        key: 'zone',
        label: up ? 'Dip zone' : 'Bounce zone',
        value: `${plainPrice(zone.low)}–${plainPrice(zone.high)}`,
        title: 'Where pullbacks like this one commonly end, from the 1h chart read.',
      }
      : {
        key: 'support',
        label: 'Support fails',
        value: price(stop.invalidation_price),
        title: 'Recent structural support from the risk plan. An hourly close below it weakens the setup.',
      },
    {
      key: 'stop',
      label: 'Stop / limit (uncal.)',
      value: `${price(stop.trigger_price)} / ${price(stop.limit_price)}`,
      title: 'Suggested stop trigger, then the sell limit. The limit is an uncalibrated placeholder, not a liquidity estimate.',
    },
    target
      ? {
        key: 'target',
        label: `${up ? 'Recovery target' : 'Downside target'} / first trim`,
        value: `${plainPrice(target)} / ${price(profit.first_trim_price)}`,
        title: 'The chart read\'s target (the last counter-swing), then the risk plan\'s first trim area.',
      }
      : {
        key: 'trim',
        label: 'First trim',
        value: price(profit.first_trim_price),
        title: 'The risk plan\'s first trim area.',
      },
  ];

  const rank = liveRanking && finite(Number(liveRanking.live_rank)) && finite(Number(liveRanking.live_score))
    ? `Tape #${liveRanking.live_rank}/${liveRanking.universe_size ?? '—'} · ${liveRanking.live_score}/100`
    : 'Tape warming';
  const postureLabel = posture?.label && posture.label !== 'WAIT' ? posture.label : null;
  const lean = earlyRead && earlyRead.label && earlyRead.label !== 'NEUTRAL'
    ? { label: earlyRead.label, tone: earlyRead.tone || 'neutral', note: earlyRead.note || '' }
    : null;
  const support = !lean && posture?.supports?.length ? sentence(posture.supports[0]) : null;
  const tape = {
    label: postureLabel,
    tone: posture?.tone || 'neutral',
    rank,
    lean,
    support,
    title: [posture?.label, posture?.headline, earlyRead?.note].filter(Boolean).join(' · '),
  };

  // A risk posture is stated outright; it is never left to a hover.
  const risk = posture?.tone === 'negative' && source !== 'tape' ? sentence(posture.headline) : null;

  return { headline, source, levels, tape, risk };
}

const LEAN_COLOR = { positive: '#45ffb3', negative: '#ff6b6b', caution: '#f1b43a', neutral: '#a3a3a3' };

export default function CoinHeaderStrip(props) {
  const strip = buildCoinStrip(props);
  const { tape } = strip;
  return (
    <section className={`cp-strip cp-strip--${tape.tone}`} data-testid="coin-strip" aria-label="Coin summary">
      <div className="cp-strip__top">
        <h2 className="cp-strip__headline" data-testid="coin-strip-headline" data-source={strip.source}>{strip.headline}</h2>
        <div className={`cp-strip__tape cp-strip__tape--${tape.tone}`} data-testid="coin-strip-tape" title={tape.title}>
          {tape.label ? <strong className="cp-strip__posture">{tape.label}</strong> : null}
          <span>{tape.rank}</span>
          {tape.lean ? <span style={{ color: LEAN_COLOR[tape.lean.tone] || LEAN_COLOR.neutral }} title={tape.lean.note}>{tape.lean.label}</span> : null}
          {tape.support ? <span>{tape.support}</span> : null}
        </div>
      </div>
      <dl className="cp-strip__levels" data-testid="coin-strip-levels">
        {strip.levels.map((level) => (
          <div key={level.key} className={`cp-strip__level cp-strip__level--${level.key}`} title={level.title}>
            <dt>{level.label}</dt>
            <dd>{level.value}</dd>
          </div>
        ))}
      </dl>
      {strip.risk ? <p className="cp-strip__risk" data-testid="coin-strip-risk">Tape risk: {strip.risk}.</p> : null}
    </section>
  );
}
