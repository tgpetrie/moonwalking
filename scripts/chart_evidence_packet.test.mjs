import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildEvidencePacket, inclusiveCutoff, runCli } from './chart_evidence_packet.mjs';

// Illustrative synthetic prices, not market data or forecast performance.
const DAY = 86400;
const start = Date.parse('2026-01-01T00:00:00Z') / 1000;
const history = { schema_version: 'bhabit.chart-history.v1',
  instrument: { product_id: 'TEST-USD', symbol: 'TEST', venue: 'illustrative', quote_currency: 'USD' },
  interval_seconds: DAY, captured_at: start + 90 * DAY, source: { illustrative: true },
  candles: Array.from({ length: 90 }, (_, i) => {
    const close = 100 + 20 * Math.sin(i / 4) - i / 3;
    return { start: start + i * DAY, end: start + (i + 1) * DAY,
      open: close, high: close + 1, low: close - 1, close, volume: 100, complete: true };
  }) };
const bytes = (value) => Buffer.from(JSON.stringify(value));

test('packet provides dated provenance, signed distances and explicit blocked claims', () => {
  const p = buildEvidencePacket(bytes(history), { interval: '1d', asOf: '2026-02-20' });
  assert.match(p.source.sha256, /^[0-9a-f]{64}$/);
  assert.equal(p.settings.effective_cutoff_exclusive_utc, '2026-02-21T00:00:00.000Z');
  assert.equal(p.reference_close.period_end_exclusive_utc, p.settings.effective_cutoff_exclusive_utc);
  assert.ok(p.evidence.recent_references.length);
  for (const r of p.evidence.recent_references) {
    assert.equal(r.distance_percent_from_reference_close, (r.price / p.reference_close.price - 1) * 100);
    assert.ok(Date.parse(r.confirmed_at_utc) <= Date.parse(p.settings.effective_cutoff_exclusive_utc));
  }
  assert.equal(p.blocked_claims.probabilities, null);
  assert.equal(p.blocked_claims.model_or_live_agent_integration, false);
  const next = p.evidence.next_run;
  assert.equal(next.reference.close, p.reference_close.price);
  for (const row of [...next.above, ...next.below]) {
    assert.ok(row.confirmed_at <= next.reference.end);
    assert.ok(row.time >= next.start);
    assert.equal(row.distance_percent, (row.price / next.reference.close - 1) * 100);
  }
});

test('physical prefix and future-price poisoning cannot change retained numerical evidence', () => {
  const options = { interval: '1d', asOf: '2026-02-20' };
  const cutoff = inclusiveCutoff(options.asOf);
  const prefix = { ...history, candles: history.candles.filter((c) => c.end <= cutoff) };
  const poisoned = { ...history, candles: history.candles.map((c) => c.end > cutoff
    ? { ...c, low: 1, high: 99999, open: 1000, close: 1000 } : c) };
  const original = buildEvidencePacket(bytes(history), options);
  for (const input of [prefix, poisoned]) {
    const p = buildEvidencePacket(bytes(input), options);
    assert.deepEqual(p.evidence, original.evidence);
    assert.deepEqual(p.reference_close, original.reference_close);
  }
});

test('validates dates, settings and insufficient completed weekly history honestly', () => {
  assert.throws(() => inclusiveCutoff('2026-02-30'));
  assert.throws(() => buildEvidencePacket(bytes(history), { confirmation: 0 }));
  assert.throws(() => buildEvidencePacket(bytes(history), { interval: '1h' }));
  const p = buildEvidencePacket(bytes(history), { asOf: '2026-01-01' });
  assert.equal(p.reference_close, null);
  assert.deepEqual(p.evidence.macro_levels, []);
  assert.ok(p.evidence.macro_unavailable_reason);
});

test('CLI output is create-only and never changes the input', () => {
  const dir = mkdtempSync(join(tmpdir(), 'moonwalking-evidence-test-'));
  try {
    const input = join(dir, 'input.json'); const output = join(dir, 'packet.json');
    const original = bytes(history); writeFileSync(input, original);
    runCli([input, '--interval', '1d', '--output', output]);
    assert.equal(JSON.parse(readFileSync(output)).schema_version, 'moonwalking.chart-evidence/v1');
    assert.throws(() => runCli([input, '--output', output]), /EEXIST/);
    assert.throws(() => runCli([input, '--output', input]), /EEXIST/);
    assert.throws(() => runCli([input, '--interval', '1d', '--interval', '1w']));
    assert.deepEqual(readFileSync(input), original);
  } finally { rmSync(dir, { recursive: true }); }
});
