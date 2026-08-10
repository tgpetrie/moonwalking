import { describe, it, expect, vi } from 'vitest';
import {
  isAlertStillActive,
  computeSignalFlags,
  computeRiskBlocker,
  computePostureLabel,
  isReversalRiskCurrent,
} from './SentimentPopupAdvanced';

// SentimentPopupAdvanced has heavy side-effect imports — mock them so the
// module loads but we only exercise the four exported pure functions.
vi.mock('../context/DataContext', () => ({ useData: () => ({}) }));
vi.mock('../hooks/useMarketHeat', () => ({ useMarketHeat: () => ({}) }));
vi.mock('../api', () => ({ API_ENDPOINTS: {}, fetchData: vi.fn() }));
vi.mock('../utils/coinHistoryCache', () => ({ getCoinEvents: vi.fn() }));
vi.mock('../utils/marketPressure', () => ({ getMarketPressure: vi.fn() }));
vi.mock('../utils/coinbaseUrl', () => ({ coinbaseSpotUrl: vi.fn() }));
vi.mock('./CoinPositioning.jsx', () => ({ default: () => null }));
vi.mock('./AlertsTab', () => ({ default: () => null }));
vi.mock('./ChartReadPanel.jsx', () => ({ default: () => null }));
vi.mock('../config/api.js', () => ({ getBackendBase: () => '' }));
vi.mock('../mvp/portfolioSignals.js', () => ({
  describeEvidenceTier: () => ({ key: 'none', label: 'No history yet' }),
}));
vi.mock('../styles/sentiment-popup-advanced.css', () => ({}));

// ---------------------------------------------------------------------------
// Test clock anchor: "now" is an arbitrary fixed ms timestamp.
const NOW = 1_700_100_000_000;
const MIN = 60_000;

// ---------------------------------------------------------------------------
// isAlertStillActive
// ---------------------------------------------------------------------------

describe('isAlertStillActive', () => {
  it('returns false for an alert whose ts_ms is older than 5 minutes', () => {
    const stale = { ts_ms: NOW - 6 * MIN };
    expect(isAlertStillActive(stale, NOW)).toBe(false);
  });

  it('returns true for an alert whose ts_ms is within 5 minutes', () => {
    const fresh = { ts_ms: NOW - 3 * MIN };
    expect(isAlertStillActive(fresh, NOW)).toBe(true);
  });

  it('uses expires_at (ISO string) over ts_ms when present', () => {
    const futureExpiry = new Date(NOW + 2 * MIN).toISOString();
    const alert = { ts_ms: NOW - 10 * MIN, expires_at: futureExpiry };
    expect(isAlertStillActive(alert, NOW)).toBe(true);
  });

  it('returns false when expires_at is in the past even if ts_ms is recent', () => {
    const pastExpiry = new Date(NOW - 1 * MIN).toISOString();
    const alert = { ts_ms: NOW - 30_000, expires_at: pastExpiry };
    expect(isAlertStillActive(alert, NOW)).toBe(false);
  });

  it('returns false for a null alert', () => {
    expect(isAlertStillActive(null, NOW)).toBe(false);
  });

  it('falls back to event_ts_ms when ts_ms is absent', () => {
    const fresh = { event_ts_ms: NOW - 2 * MIN };
    expect(isAlertStillActive(fresh, NOW)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// computeSignalFlags
// ---------------------------------------------------------------------------

function makeAlert(type, ageMins, overrides = {}) {
  return { type_key: type, ts_ms: NOW - ageMins * MIN, ...overrides };
}

describe('computeSignalFlags – risk types require freshness', () => {
  it('does NOT flag hasReversal for a stale reversal alert (8 min old)', () => {
    const alerts = [makeAlert('reversal_warning', 8)];
    const flags = computeSignalFlags(alerts, NOW);
    expect(flags.hasReversal).toBe(false);
  });

  it('flags hasReversal for a fresh reversal alert (2 min old)', () => {
    const alerts = [makeAlert('reversal_warning', 2)];
    const flags = computeSignalFlags(alerts, NOW);
    expect(flags.hasReversal).toBe(true);
  });

  it('does NOT flag hasFakeout for a stale fakeout alert (7 min old)', () => {
    const alerts = [makeAlert('fakeout_detected', 7)];
    const flags = computeSignalFlags(alerts, NOW);
    expect(flags.hasFakeout).toBe(false);
  });

  it('does NOT flag hasExhaustion for a stale exhaustion alert (6 min old)', () => {
    const alerts = [makeAlert('exhaustion_signal', 6)];
    const flags = computeSignalFlags(alerts, NOW);
    expect(flags.hasExhaustion).toBe(false);
  });

  it('flags hasReversal via trend_break type key', () => {
    const alerts = [makeAlert('trend_break', 1)];
    const flags = computeSignalFlags(alerts, NOW);
    expect(flags.hasReversal).toBe(true);
  });

  it('flags hasFakeout for a fresh fakeout alert', () => {
    const alerts = [makeAlert('fakeout_detected', 3)];
    const flags = computeSignalFlags(alerts, NOW);
    expect(flags.hasFakeout).toBe(true);
  });
});

describe('computeSignalFlags – momentum is unaged', () => {
  it('flags hasMomentum for an old breakout alert (30 min old)', () => {
    const alerts = [makeAlert('breakout_up', 30)];
    const flags = computeSignalFlags(alerts, NOW);
    expect(flags.hasMomentum).toBe(true);
  });

  it('flags hasMomentum via moonshot type key regardless of age', () => {
    const alerts = [makeAlert('moonshot_detected', 15)];
    const flags = computeSignalFlags(alerts, NOW);
    expect(flags.hasMomentum).toBe(true);
  });
});

describe('computeSignalFlags – edge cases', () => {
  it('returns all false for an empty array', () => {
    const flags = computeSignalFlags([], NOW);
    expect(flags).toEqual({
      hasReversal: false,
      hasFakeout: false,
      hasSqueeze: false,
      hasExhaustion: false,
      hasMomentum: false,
    });
  });

  it('returns all false for null input', () => {
    const flags = computeSignalFlags(null, NOW);
    expect(flags).toEqual({
      hasReversal: false,
      hasFakeout: false,
      hasSqueeze: false,
      hasExhaustion: false,
      hasMomentum: false,
    });
  });

  it('uses expires_at over ts_ms for risk freshness', () => {
    const futureExpiry = new Date(NOW + 3 * MIN).toISOString();
    // ts_ms is stale but expires_at says it's still live
    const alerts = [{ type_key: 'reversal_warning', ts_ms: NOW - 10 * MIN, expires_at: futureExpiry }];
    const flags = computeSignalFlags(alerts, NOW);
    expect(flags.hasReversal).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// isReversalRiskCurrent
// ---------------------------------------------------------------------------

// PRIORITY_FADING_MS = 3.5 * 60 * 1000 = 210_000 ms
const FADING_MS = 3.5 * 60 * 1000;

describe('isReversalRiskCurrent', () => {
  it('returns false when entry is null', () => {
    expect(isReversalRiskCurrent(null)).toBe(false);
  });

  it('returns false when stateLabel is not Reversal Risk', () => {
    expect(isReversalRiskCurrent({ stateLabel: 'Building', noConfirmMs: 0 })).toBe(false);
  });

  it('returns true when stateLabel is Reversal Risk and noConfirmMs is within PRIORITY_FADING_MS', () => {
    expect(isReversalRiskCurrent({ stateLabel: 'Reversal Risk', noConfirmMs: 2 * 60 * 1000 })).toBe(true);
  });

  it('returns false when stateLabel is Reversal Risk but noConfirmMs >= PRIORITY_FADING_MS (stale)', () => {
    expect(isReversalRiskCurrent({ stateLabel: 'Reversal Risk', noConfirmMs: FADING_MS })).toBe(false);
  });

  it('returns false when stateLabel is Reversal Risk and noConfirmMs is well past threshold', () => {
    expect(isReversalRiskCurrent({ stateLabel: 'Reversal Risk', noConfirmMs: 10 * 60 * 1000 })).toBe(false);
  });

  it('returns false when noConfirmMs is absent (safe default — no veto without data)', () => {
    expect(isReversalRiskCurrent({ stateLabel: 'Reversal Risk' })).toBe(false);
  });

  it('returns true just inside the PRIORITY_FADING_MS boundary', () => {
    expect(isReversalRiskCurrent({ stateLabel: 'Reversal Risk', noConfirmMs: FADING_MS - 1 })).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// computeRiskBlocker
// ---------------------------------------------------------------------------

describe('computeRiskBlocker – specific messages per flag type', () => {
  it('returns fakeout message when hasFakeout is set', () => {
    expect(computeRiskBlocker({ hasFakeout: true, hasReversal: false, hasExhaustion: false }, false))
      .toBe('A recent fakeout warning is still active.');
  });

  it('returns reversal message when hasReversal is set (and no fakeout)', () => {
    expect(computeRiskBlocker({ hasFakeout: false, hasReversal: true, hasExhaustion: false }, false))
      .toBe('Reversal risk is still active.');
  });

  it('returns exhaustion message when hasExhaustion is set (no fakeout/reversal)', () => {
    expect(computeRiskBlocker({ hasFakeout: false, hasReversal: false, hasExhaustion: true }, false))
      .toBe('An exhaustion warning is still active.');
  });

  it('returns state message when reversalRiskCurrent is true and no signal flags', () => {
    expect(computeRiskBlocker({ hasFakeout: false, hasReversal: false, hasExhaustion: false }, true))
      .toBe('Reversal risk pattern is still active.');
  });

  it('fakeout message takes priority over reversal and reversalRiskCurrent when all are set', () => {
    expect(computeRiskBlocker({ hasFakeout: true, hasReversal: true, hasExhaustion: true }, true))
      .toBe('A recent fakeout warning is still active.');
  });

  it('returns null when no flags are set and reversalRiskCurrent is false', () => {
    expect(computeRiskBlocker({ hasFakeout: false, hasReversal: false, hasExhaustion: false }, false))
      .toBeNull();
  });

  it('returns null when signalFlags is null and reversalRiskCurrent is false', () => {
    expect(computeRiskBlocker(null, false)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// computePostureLabel
// ---------------------------------------------------------------------------

const BASE_GOOD = {
  score: 72,
  alignmentLabel: 'Aligned Up',
  volumeConfirms: true,
  persistenceGood: true,
  breadthUp: 0.55,
  historyWeak: false,
  hardRisk: false,
  breakoutUp: true,
  change1m: 0.3,
  change3m: 0.5,
};

describe('computePostureLabel – hard vetoes', () => {
  it('returns STAY CLEAR when hardRisk is true regardless of score', () => {
    expect(computePostureLabel({ ...BASE_GOOD, hardRisk: true })).toBe('STAY CLEAR');
  });

  it('returns STAY CLEAR when alignmentLabel is Aligned Down', () => {
    expect(computePostureLabel({ ...BASE_GOOD, alignmentLabel: 'Aligned Down' })).toBe('STAY CLEAR');
  });

  it('returns STAY CLEAR when score is below 42', () => {
    expect(computePostureLabel({ ...BASE_GOOD, score: 41 })).toBe('STAY CLEAR');
  });
});

describe('computePostureLabel – STRONG SETUP', () => {
  it('returns STRONG SETUP when all quality gates pass', () => {
    expect(computePostureLabel(BASE_GOOD)).toBe('STRONG SETUP');
  });

  it('does NOT return STRONG SETUP when historyWeak is true', () => {
    const result = computePostureLabel({ ...BASE_GOOD, historyWeak: true });
    expect(result).not.toBe('STRONG SETUP');
  });

  it('does NOT return STRONG SETUP when score is below 70', () => {
    const result = computePostureLabel({ ...BASE_GOOD, score: 69 });
    expect(result).not.toBe('STRONG SETUP');
  });
});

describe('computePostureLabel – WATCH CLOSE', () => {
  it('returns WATCH CLOSE when score >= 60, volumeConfirms, alignedUp (no persistence/breadth)', () => {
    expect(computePostureLabel({
      ...BASE_GOOD,
      score: 62,
      persistenceGood: false,
      breadthUp: 0.3,
      historyWeak: true,
    })).toBe('WATCH CLOSE');
  });
});

describe('computePostureLabel – EARLY SETUP', () => {
  it('returns EARLY SETUP when 1m+3m positive, volume confirms, breakout active, 1h not required', () => {
    expect(computePostureLabel({
      ...BASE_GOOD,
      score: 57,
      alignmentLabel: 'Mixed',   // 1h has NOT caught up yet
      volumeConfirms: true,
      breakoutUp: true,
      change1m: 0.4,
      change3m: 0.2,
      persistenceGood: false,
      breadthUp: 0.2,
    })).toBe('EARLY SETUP');
  });

  it('does NOT return EARLY SETUP when 1m is negative (shortTermUp false)', () => {
    expect(computePostureLabel({
      ...BASE_GOOD,
      score: 57,
      alignmentLabel: 'Mixed',
      volumeConfirms: true,
      breakoutUp: true,
      change1m: -0.1,  // negative 1m
      change3m: 0.5,
    })).toBe('WAIT');
  });

  it('does NOT return EARLY SETUP when 3m is negative', () => {
    expect(computePostureLabel({
      ...BASE_GOOD,
      score: 57,
      alignmentLabel: 'Mixed',
      volumeConfirms: true,
      breakoutUp: true,
      change1m: 0.2,
      change3m: -0.1,  // negative 3m
    })).toBe('WAIT');
  });

  it('does NOT return EARLY SETUP when breakoutUp is false', () => {
    expect(computePostureLabel({
      ...BASE_GOOD,
      score: 57,
      alignmentLabel: 'Mixed',
      volumeConfirms: true,
      breakoutUp: false,
      change1m: 0.3,
      change3m: 0.3,
    })).toBe('WAIT');
  });

  it('does NOT return EARLY SETUP when hardRisk is true', () => {
    expect(computePostureLabel({
      ...BASE_GOOD,
      score: 57,
      alignmentLabel: 'Mixed',
      volumeConfirms: true,
      breakoutUp: true,
      change1m: 0.3,
      change3m: 0.3,
      hardRisk: true,
    })).toBe('STAY CLEAR');
  });
});

describe('computePostureLabel – WAIT fallback', () => {
  it('returns WAIT when score is acceptable but no gate fires', () => {
    expect(computePostureLabel({
      score: 55,
      alignmentLabel: 'Mixed',
      volumeConfirms: false,
      persistenceGood: false,
      breadthUp: 0.2,
      historyWeak: false,
      hardRisk: false,
      breakoutUp: false,
      change1m: -0.1,
      change3m: 0.1,
    })).toBe('WAIT');
  });
});

// ---------------------------------------------------------------------------
// Exhaustion is caution, not a hard veto
// ---------------------------------------------------------------------------

// Exhaustion-only scenarios use computeSignalFlags to produce a real flags
// object, then verify computePostureLabel is NOT forced to STAY CLEAR.
// hasExhaustion should appear in the blocker message but must not collapse
// an otherwise valid early setup.

describe('exhaustion – caution not veto', () => {
  it('fresh exhaustion alone does NOT make hardRisk — posture can still be EARLY SETUP', () => {
    // hardRisk = hasFakeout || hasReversal || reversalRiskCurrent
    // hasExhaustion is excluded from hardRisk so this must not STAY CLEAR
    const hardRiskWithExhaustionOnly = false; // exhaustion removed from formula
    expect(computePostureLabel({
      ...BASE_GOOD,
      score: 57,
      alignmentLabel: 'Mixed',
      volumeConfirms: true,
      breakoutUp: true,
      change1m: 0.3,
      change3m: 0.3,
      hardRisk: hardRiskWithExhaustionOnly,
    })).toBe('EARLY SETUP');
  });

  it('fresh exhaustion alert is still flagged by computeSignalFlags', () => {
    const fresh = [makeAlert('exhaustion_signal', 2)];
    const flags = computeSignalFlags(fresh, NOW);
    expect(flags.hasExhaustion).toBe(true);
  });

  it('fresh exhaustion returns an exhaustion blocker message (caution visible in blockers)', () => {
    const flags = { hasFakeout: false, hasReversal: false, hasExhaustion: true };
    expect(computeRiskBlocker(flags, false)).toBe('An exhaustion warning is still active.');
  });

  it('exhaustion + genuine fakeout still causes STAY CLEAR (fakeout is the veto, not exhaustion)', () => {
    expect(computePostureLabel({
      ...BASE_GOOD,
      score: 57,
      alignmentLabel: 'Mixed',
      volumeConfirms: true,
      breakoutUp: true,
      change1m: 0.3,
      change3m: 0.3,
      hardRisk: true, // hasFakeout would drive this
    })).toBe('STAY CLEAR');
  });
});

// ---------------------------------------------------------------------------
// Event Evolution Reversal Risk — currentness gate
// ---------------------------------------------------------------------------

describe('isReversalRiskCurrent – veto when current, pass when stale', () => {
  it('current Reversal Risk (noConfirmMs < PRIORITY_FADING_MS) can reach STAY CLEAR via hardRisk', () => {
    // isReversalRiskCurrent returns true → hardRisk = true → STAY CLEAR
    const currentEntry = { stateLabel: 'Reversal Risk', noConfirmMs: 1 * 60 * 1000 };
    expect(isReversalRiskCurrent(currentEntry)).toBe(true);
    expect(computePostureLabel({
      ...BASE_GOOD,
      score: 57,
      alignmentLabel: 'Mixed',
      volumeConfirms: true,
      breakoutUp: true,
      change1m: 0.3,
      change3m: 0.3,
      hardRisk: isReversalRiskCurrent(currentEntry),
    })).toBe('STAY CLEAR');
  });

  it('stale Reversal Risk (noConfirmMs >= PRIORITY_FADING_MS) does NOT produce hardRisk', () => {
    // isReversalRiskCurrent returns false → hardRisk = false → EARLY SETUP possible
    const staleEntry = { stateLabel: 'Reversal Risk', noConfirmMs: 5 * 60 * 1000 };
    expect(isReversalRiskCurrent(staleEntry)).toBe(false);
    expect(computePostureLabel({
      ...BASE_GOOD,
      score: 57,
      alignmentLabel: 'Mixed',
      volumeConfirms: true,
      breakoutUp: true,
      change1m: 0.3,
      change3m: 0.3,
      hardRisk: isReversalRiskCurrent(staleEntry),
    })).toBe('EARLY SETUP');
  });

  it('Dominant stateLabel is never a Reversal Risk regardless of noConfirmMs', () => {
    const dominantEntry = { stateLabel: 'Dominant', noConfirmMs: 0 };
    expect(isReversalRiskCurrent(dominantEntry)).toBe(false);
  });
});
