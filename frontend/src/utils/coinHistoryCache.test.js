import { beforeEach, describe, expect, it } from 'vitest';
import {
  getCoinEvents,
  isCoinEventActive,
  loadCoinHistory,
  upsertCoinEvents,
} from './coinHistoryCache';
import { computeBreakoutState } from '../components/SentimentPopupAdvanced';

const NOW = 1_700_100_000_000;
const MIN = 60_000;

beforeEach(() => {
  window.localStorage.clear();
});

const event = (overrides = {}) => ({
  id: 'btc-breakout',
  symbol: 'BTC-USD',
  type_key: 'breakout_up',
  message: 'BTC broke out',
  ts_ms: NOW - MIN,
  expires_at: new Date(NOW + MIN).toISOString(),
  ttl_seconds: 300,
  ...overrides,
});

describe('coin history expiry', () => {
  it('prefers backend expires_at and supports ttl_seconds when expiry is absent', () => {
    expect(isCoinEventActive(event({ ts_ms: NOW - 30 * MIN }), NOW)).toBe(true);
    expect(isCoinEventActive(event({ expires_at: new Date(NOW - 1).toISOString() }), NOW)).toBe(false);
    expect(isCoinEventActive(event({ expires_at: null, ts_ms: NOW - 7 * MIN, ttl_seconds: 600 }), NOW)).toBe(true);
    expect(isCoinEventActive(event({ expires_at: null, ts_ms: NOW - 11 * MIN, ttl_seconds: 600 }), NOW)).toBe(false);
  });

  it('preserves expires_at and ttl_seconds through the cache round-trip', () => {
    const incoming = event();
    upsertCoinEvents('BTC', [incoming]);

    expect(getCoinEvents('BTC', NOW)).toEqual([
      expect.objectContaining({
        id: incoming.id,
        expires_at: incoming.expires_at,
        ttl_seconds: 300,
      }),
    ]);
  });

  it('excludes and purges expired cached rows', () => {
    upsertCoinEvents('BTC', [event({ expires_at: new Date(NOW - MIN).toISOString() })]);

    expect(getCoinEvents('BTC', NOW)).toEqual([]);
    expect(loadCoinHistory().BTC).toEqual([]);
  });

  it('prevents an old persisted event without expiry metadata from resurrecting breakout state', () => {
    window.localStorage.setItem('mw_coin_history_v1', JSON.stringify({
      BTC: [{
        id: 'legacy-breakout',
        ts: NOW - 30 * MIN,
        symbol: 'BTC',
        type_key: 'breakout_up',
        message: 'Old breakout',
      }],
    }));

    const cached = getCoinEvents('BTC', NOW);
    expect(cached).toEqual([]);
    expect(computeBreakoutState(cached, NOW)).toBe('No breakout');
  });

  it('keeps current cached evidence active as before', () => {
    upsertCoinEvents('BTC', [event()]);
    const cached = getCoinEvents('BTC', NOW);

    expect(cached).toHaveLength(1);
    expect(computeBreakoutState(cached, NOW)).toBe('Breakout Up');
  });
});
