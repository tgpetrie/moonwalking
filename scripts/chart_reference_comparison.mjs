// Offline diagnostic: compare nearby observations across daily and weekly scopes.
// This does not choose a future peak or alter the chart/installed worker.
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { buildEvidencePacket } from './chart_evidence_packet.mjs';
import { DAY, WEEK, parseHistory, chartAt, confirmedPivots } from '../frontend/src/utils/macroChart.js';
import { recentSwingSequence } from '../frontend/src/utils/chartStructure.js';
import { nextRunMap } from '../frontend/src/utils/nextRunMap.js';
import { historyFreshness } from '../frontend/src/utils/chartFreshness.js';

const date = (t) => new Date(t * 1000).toISOString().slice(0, 10);
const distance = (price, close) => (price / close - 1) * 100;

function describe(p, reference) {
  return { type: p.type, price: p.price, extreme_date_utc: date(p.extreme_time ?? p.time),
    confirmed_at_utc: new Date(p.confirmed_at * 1000).toISOString(),
    distance_percent_from_daily_close: distance(p.price, reference.close),
    inside_latest_daily_range: reference.low <= p.price && p.price <= reference.high };
}

function scopedPivots(candles, interval, cutoff, lookbackDays, confirmation) {
  const detected = confirmedPivots(candles, { left: confirmation, right: confirmation, interval });
  const eligible = detected.pivots.filter((p) => p.time >= cutoff - lookbackDays * DAY && p.confirmed_at <= cutoff);
  // Match the chart's equal-price rule: retain the latest confirmed occurrence.
  const unique = (type) => [...new Map(eligible.filter((p) => p.type === type)
    .sort((a, b) => a.confirmed_at - b.confirmed_at).map((p) => [p.price, p])).values()];
  return { eligible, highs: unique('high').sort((a, b) => a.price - b.price),
    lows: unique('low').sort((a, b) => b.price - a.price) };
}

export function compareReferenceScopes(bytes, { asOf, confirmation = 2 } = {}) {
  const packet = buildEvidencePacket(bytes, { asOf, interval: '1d', confirmation });
  const history = parseHistory(JSON.parse(bytes.toString()));
  const cutoff = Date.parse(packet.settings.effective_cutoff_exclusive_utc) / 1000;
  const daily = chartAt(history, '1d', cutoff);
  const weekly = chartAt(history, '1w', cutoff);
  const reference = daily.candles.at(-1);
  if (!reference) throw new Error('A completed daily candle is required for the comparison.');
  const dailyPivots = scopedPivots(daily.candles, DAY, reference.end, 365, confirmation);
  const weeklyPivots = scopedPivots(weekly.candles, WEEK, weekly.as_of, 365, confirmation);
  const nearest = (pivots) => ({
    above: pivots.highs.filter((p) => p.price > reference.close).slice(0, 3).map((p) => describe(p, reference)),
    below: pivots.lows.filter((p) => p.price < reference.close).slice(0, 3).map((p) => describe(p, reference)),
  });
  const outsideRange = (pivots) => ({
    above: pivots.highs.filter((p) => p.price > reference.high).slice(0, 3).map((p) => describe(p, reference)),
    below: pivots.lows.filter((p) => p.price < reference.low).slice(0, 3).map((p) => describe(p, reference)),
  });
  return {
    schema_version: 'moonwalking.chart-reference-comparison/v1', instrument: packet.instrument,
    source: { sha256: packet.source.sha256, fetched_at: history.source?.fetched_at ?? null,
      scope: 'Retrospective Coinbase product history; video-feed parity and historical vendor availability are unverified.' },
    cutoff_exclusive_utc: packet.settings.effective_cutoff_exclusive_utc,
    freshness: { ...historyFreshness({ ...history, captured_at: cutoff, candles: daily.candles }),
      analysis_mode: asOf ? 'historical_replay' : 'saved_snapshot',
      note: 'This offline command does not contact the provider or turn a saved file into live data.' },
    daily_reference: { date_utc: date(reference.time), close: reference.close, low: reference.low, high: reference.high },
    weekly_reference: weekly.candles.length ? { date_utc: date(weekly.candles.at(-1).end - 1),
      close: weekly.candles.at(-1).close } : null,
    settings: { confirmation_bars_each_side: confirmation, distances_use: 'latest completed daily close',
      weekly_lookback_days: 365, daily_turn_sequence_lookback_days: 90 },
    coverage: { daily_candles: daily.candles.length, complete_weeks: weekly.candles.length,
      missing_daily_intervals: daily.missing_days, excluded_incomplete_weeks: weekly.excluded_weeks },
    daily_scopes: Object.fromEntries([90, 365].map((lookbackDays) => {
      const map = nextRunMap(daily.candles, { asOf: cutoff, confirmation, lookbackDays });
      return [lookbackDays, { above: map.above.map((p) => describe(p, reference)),
        below: map.below.map((p) => describe(p, reference)),
        outside_latest_range: outsideRange(scopedPivots(daily.candles, DAY, reference.end, lookbackDays, confirmation)) }];
    })),
    weekly_nearby_references: nearest(weeklyPivots),
    recent_daily_turns: recentSwingSequence(dailyPivots.eligible.filter((p) => p.time >= reference.end - 90 * DAY),
      { asOf: cutoff }).map((p) => describe(p, reference)),
    recent_weekly_turns: recentSwingSequence(weeklyPivots.eligible, { asOf: weekly.as_of }).map((p) => describe(p, reference)),
    old_macro_half_recovery: packet.evidence.macro_levels.find((p) => p.ratio === 0.5) ?? null,
    limitations: [
      'Nearest by price is not necessarily recent in time or relevant to the next swing.',
      'Inside the latest daily range means that day already spanned the price; it gives no intraday order or execution evidence.',
      'References outside that range are not fresh or untested levels, and need not be reached next.',
      'Neither scope nor these observations establishes a peak, arrival date, probability or profitable rule.',
    ],
  };
}

export function runCli(args) {
  let asOf;
  const inputs = [];
  for (let i = 0; i < args.length; i += 1) {
    if (args[i] === '--as-of' && asOf === undefined && args[i + 1]) asOf = args[++i];
    else if (args[i].startsWith('--')) throw new Error('Only --as-of YYYY-MM-DD is supported.');
    else inputs.push(args[i]);
  }
  if (!inputs.length) throw new Error('Provide one or more chart-history JSON files.');
  return inputs.map((input) => compareReferenceScopes(readFileSync(input), { asOf }));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try { process.stdout.write(`${JSON.stringify(runCli(process.argv.slice(2)), null, 2)}\n`); }
  catch (error) { process.stderr.write(`${error.message}\n`); process.exitCode = 1; }
}
