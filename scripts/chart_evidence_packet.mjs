// Offline evidence producer; no model, network, credentials or trading actions.
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { DAY, parseHistory, chartAt, confirmedPivots } from '../frontend/src/utils/macroChart.js';
import { defaultMacroAnchors, macroRange, historicalMacro, recentSwingSequence } from '../frontend/src/utils/chartStructure.js';
import { historicalLegs, levelEpisodes } from '../frontend/src/utils/chartTiming.js';

const iso = (seconds) => new Date(seconds * 1000).toISOString();
const datedAnchor = (p) => ({ ...p, bucket_start_utc: iso(p.time),
  extreme_date_utc: iso(p.extreme_time ?? p.time).slice(0, 10), confirmed_at_utc: iso(p.confirmed_at) });

export function inclusiveCutoff(date) {
  if (typeof date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new Error('--as-of requires YYYY-MM-DD');
  const ms = Date.parse(`${date}T00:00:00Z`);
  if (!Number.isFinite(ms) || new Date(ms).toISOString().slice(0, 10) !== date) throw new Error('Invalid UTC date');
  return ms / 1000 + DAY;
}

export function buildEvidencePacket(bytes, { asOf, interval = '1w', confirmation = 2 } = {}) {
  if (!['1d', '1w'].includes(interval)) throw new Error('--interval must be 1d or 1w');
  if (!Number.isInteger(confirmation) || confirmation < 1 || confirmation > 4) throw new Error('--confirmation must be 1–4');
  const history = parseHistory(JSON.parse(bytes.toString()));
  const requested = asOf === undefined ? history.captured_at : inclusiveCutoff(asOf);
  const chart = chartAt(history, interval, requested);
  const daily = chartAt(history, '1d', requested);
  const { pivots, ambiguous } = confirmedPivots(chart.candles, { left: confirmation, right: confirmation, interval: chart.interval_seconds });
  const close = chart.candles.at(-1);
  const ids = defaultMacroAnchors(pivots);
  const range = macroRange(...ids.map((id) => pivots.find((p) => p.id === id)), { asOf: chart.as_of });
  const macro = historicalMacro(pivots, range, { asOf: chart.as_of });
  const recent = recentSwingSequence(pivots, { asOf: chart.as_of });
  const distance = (price) => close ? (price / close.close - 1) * 100 : null;
  const references = ['low', 'high'].flatMap((type) => {
    const anchor = pivots.filter((p) => p.type === type).at(-1);
    if (!anchor) return [];
    const reactions = levelEpisodes(daily.candles, anchor, { asOf: chart.as_of });
    return [{ ...datedAnchor(anchor), distance_percent_from_reference_close: distance(anchor.price), reactions }];
  });
  return {
    schema_version: 'moonwalking.chart-evidence/v1', producer: 'offline-deterministic-cli/v1',
    source: { sha256: createHash('sha256').update(bytes).digest('hex'), metadata: history.source,
      metadata_scope: 'Source-file metadata describes the supplied export; it is not inferred point-in-time knowledge.' },
    instrument: history.instrument,
    settings: { interval, confirmation_bars_each_side: confirmation, requested_as_of_inclusive_utc: asOf ?? null,
      requested_cutoff_exclusive_utc: iso(requested), effective_cutoff_exclusive_utc: iso(chart.as_of) },
    reference_close: close ? { price: close.close, period_start_utc: iso(close.time), period_end_exclusive_utc: iso(close.end), interval } : null,
    coverage: { completed_analysis_candles: chart.candles.length, completed_daily_candles: daily.candles.length,
      internal_missing_daily_intervals: chart.missing_days, excluded_incomplete_weeks: chart.excluded_weeks,
      ambiguous_pivots_excluded: ambiguous, scope: 'Missing intervals are measured between first and last retained complete daily candles.' },
    evidence: { pivots: pivots.map(datedAnchor), recent_sequence: recent.map(datedAnchor), recent_references: references,
      historical_legs: historicalLegs(recent, chart.as_of), macro_anchors: macro.anchors.map(datedAnchor),
      macro_unavailable_reason: range.error ?? null,
      macro_levels: range.error ? [] : range.levels.map((p) => ({ id: `macro-${p.ratio}`, ...p,
        distance_percent_from_reference_close: distance(p.price), anchor_ids: ids, available_at_utc: iso(range.available_at) })) },
    blocked_claims: { arrival_dates: null, probabilities: null, trading_profitability: null, executable_fills: null,
      all_time_extrema: null, validated_wave_count: null, model_or_live_agent_integration: false,
      reason: 'Geometry and historical observations do not establish these claims. Reactions can overlap and are not independent trades.' },
  };
}

export function runCli(args) {
  const [input, ...flags] = args;
  if (!input || input.startsWith('--')) throw new Error('Usage: node scripts/chart_evidence_packet.mjs HISTORY.json [--as-of YYYY-MM-DD] [--interval 1w|1d] [--confirmation 1–4] [--output NEW.json]');
  const options = {};
  const seen = new Set();
  for (let i = 0; i < flags.length; i += 2) {
    const key = flags[i]; const value = flags[i + 1];
    if (!['--as-of', '--interval', '--confirmation', '--output'].includes(key) || !value || value.startsWith('--') || seen.has(key)) throw new Error('Unknown, repeated or incomplete option');
    seen.add(key); options[key] = value;
  }
  const packet = buildEvidencePacket(readFileSync(input), { asOf: options['--as-of'], interval: options['--interval'],
    confirmation: options['--confirmation'] === undefined ? 2 : Number(options['--confirmation']) });
  const json = `${JSON.stringify(packet, null, 2)}\n`;
  if (options['--output']) writeFileSync(options['--output'], json, { flag: 'wx' });
  else process.stdout.write(json);
  return packet;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try { runCli(process.argv.slice(2)); } catch (error) { process.stderr.write(`${error.message}\n`); process.exitCode = 1; }
}
