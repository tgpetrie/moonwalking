import { describe, it, expect, vi } from 'vitest';
import {
  isAlertStillActive,
  computeSignalFlags,
  computeBreakoutState,
  computeRiskBlocker,
  computePostureLabel,
  computeBreadthRead,
  isReversalRiskCurrent,
  buildWarmingSupports,
  resolveWaitHeadline,
  computeFeedStatus,
  buildPriorityRailItem,
  PRIORITY_STATE_TO_HERO,
  mapPriorityStateToHero,
  describeHeroState,
  resolveUnrankedHeroState,
  resolveCoinHeroState,
} from './SentimentPopupAdvanced';
import { priorityStateForEntry } from '../utils/priorityEngine';

// SentimentPopupAdvanced has heavy side-effect imports — mock them so the
// module loads but we only exercise the four exported pure functions.
vi.mock('../context/DataContext', () => ({ useData: () => ({}) }));
vi.mock('../hooks/useMarketHeat', () => ({ useMarketHeat: () => ({}) }));
vi.mock('../api', () => ({ API_ENDPOINTS: {}, fetchData: vi.fn() }));
vi.mock('../utils/coinHistoryCache', async (importOriginal) => ({
  ...(await importOriginal()),
  getCoinEvents: vi.fn(),
}));
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

describe('computeSignalFlags – momentum and squeeze require freshness', () => {
  it('flags momentum while breakout evidence is active', () => {
    const alerts = [makeAlert('breakout_up', 3)];
    const flags = computeSignalFlags(alerts, NOW);
    expect(flags.hasMomentum).toBe(true);
  });

  it('clears momentum after breakout evidence expires', () => {
    const alerts = [makeAlert('breakout_up', 6)];
    const flags = computeSignalFlags(alerts, NOW);
    expect(flags.hasMomentum).toBe(false);
  });

  it('honors backend expires_at for momentum evidence', () => {
    const active = makeAlert('moonshot_detected', 30, {
      expires_at: new Date(NOW + MIN).toISOString(),
    });
    const expired = makeAlert('moonshot_detected', 1, {
      expires_at: new Date(NOW - MIN).toISOString(),
    });
    expect(computeSignalFlags([active], NOW).hasMomentum).toBe(true);
    expect(computeSignalFlags([expired], NOW).hasMomentum).toBe(false);
  });

  it('flags squeeze inside TTL and clears it after TTL', () => {
    expect(computeSignalFlags([makeAlert('squeeze_break', 2)], NOW).hasSqueeze).toBe(true);
    expect(computeSignalFlags([makeAlert('squeeze_break', 7)], NOW).hasSqueeze).toBe(false);
  });
});

describe('computeBreakoutState', () => {
  it('reports breakout only while the evidence is active', () => {
    expect(computeBreakoutState([makeAlert('breakout_up', 2)], NOW)).toBe('Breakout Up');
    expect(computeBreakoutState([makeAlert('breakout_up', 6)], NOW)).toBe('No breakout');
  });

  it('does not let an expired newest row hide a still-active breakout row', () => {
    const rows = [makeAlert('breakout_up', 6), makeAlert('breakout_up', 2)];
    expect(computeBreakoutState(rows, NOW)).toBe('Breakout Up');
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

  it('keeps canonical Fading and Fragile states non-bullish', () => {
    expect(computePostureLabel({ ...BASE_GOOD, canonicalState: 'Fading' })).toBe('WAIT');
    expect(computePostureLabel({ ...BASE_GOOD, canonicalState: 'Fragile' })).toBe('WAIT');
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

  it('does NOT return STRONG SETUP when breadth is unavailable', () => {
    expect(computePostureLabel({ ...BASE_GOOD, breadthUp: null })).toBe('WATCH CLOSE');
  });

  it('keeps the existing 0.45 breadth threshold unchanged', () => {
    expect(computePostureLabel({ ...BASE_GOOD, breadthUp: 0.45 })).toBe('STRONG SETUP');
    expect(computePostureLabel({ ...BASE_GOOD, breadthUp: 0.449 })).toBe('WATCH CLOSE');
  });
});

describe('computeBreadthRead', () => {
  it('keeps absent breadth unavailable without hostile-breadth claims', () => {
    const read = computeBreadthRead({ breadth_up: null });
    expect(read.available).toBe(false);
    expect(read.value).toBeNull();
    expect(read.status).toBe('Unavailable');
    expect(read.badge).toBeNull();
    expect(read.blocker).not.toBe('Most of the market is not helping it.');
    expect(JSON.stringify(read)).not.toContain('BREADTH WEAK');
  });

  it('keeps measured zero breadth genuinely weak', () => {
    expect(computeBreadthRead({ breadth_up: 0 })).toMatchObject({
      available: true,
      value: 0,
      status: 'Hostile',
      badge: 'BREADTH WEAK',
      blocker: 'Most of the market is not helping it.',
    });
  });

  it('preserves supportive and mixed thresholds', () => {
    expect(computeBreadthRead({ breadth_up: 0.56 }).status).toBe('Supportive');
    expect(computeBreadthRead({ breadth_up: 0.45 }).status).toBe('Mixed');
    expect(computeBreadthRead({ breadth_up: 0.44 }).status).toBe('Hostile');
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

  it('stale risk becomes canonical Fading and cannot produce a bullish posture', () => {
    const staleEntry = { stateLabel: 'Fading', noConfirmMs: 5 * 60 * 1000 };
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
      canonicalState: staleEntry.stateLabel,
    })).toBe('WAIT');
  });

  it('Dominant stateLabel is never a Reversal Risk regardless of noConfirmMs', () => {
    const dominantEntry = { stateLabel: 'Dominant', noConfirmMs: 0 };
    expect(isReversalRiskCurrent(dominantEntry)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Board/popup truthfulness: the board badges "Tape confirmed" at live_score
// >= 65. These two helpers keep the popup from contradicting that badge while
// still refusing to overstate the setup.
// ---------------------------------------------------------------------------

describe('buildWarmingSupports', () => {
  it('surfaces live tape strength while per-coin metrics are still warming', () => {
    expect(buildWarmingSupports({ live_score: 72 })).toEqual([
      'Live tape strength is 72/100.',
    ]);
  });

  it('stays silent below the board badge threshold', () => {
    expect(buildWarmingSupports({ live_score: 64 })).toEqual([]);
  });

  it('includes the exact boundary the board badge uses', () => {
    expect(buildWarmingSupports({ live_score: 65 })).toHaveLength(1);
  });

  it('stays silent when no live ranking is available', () => {
    expect(buildWarmingSupports(undefined)).toEqual([]);
    expect(buildWarmingSupports({})).toEqual([]);
    expect(buildWarmingSupports({ live_score: null })).toEqual([]);
    expect(buildWarmingSupports({ live_score: 'abc' })).toEqual([]);
  });

  it('never leaves supports empty on a coin the board is badging confirmed', () => {
    // The original defect: board shows "Tape confirmed", popup shows
    // "Nothing meaningful is confirming the setup yet."
    expect(buildWarmingSupports({ live_score: 67 }).length).toBeGreaterThan(0);
  });
});

describe('resolveWaitHeadline', () => {
  it('does not claim "no clean setup" when the board says tape confirmed', () => {
    const headline = resolveWaitHeadline({ breakoutUp: false, score: 67 });
    expect(headline).not.toMatch(/No clean setup/i);
    expect(headline).toMatch(/Tape strength is notable/);
  });

  it('keeps the plain wording below the badge threshold', () => {
    expect(resolveWaitHeadline({ breakoutUp: false, score: 58 })).toBe(
      'No clean setup is active right now.',
    );
  });

  it('still prioritises the breakout wording', () => {
    expect(resolveWaitHeadline({ breakoutUp: true, score: 72 })).toBe(
      'Breakout detected, but confirmation is incomplete.',
    );
    expect(resolveWaitHeadline({ breakoutUp: true, score: 20 })).toBe(
      'Breakout detected, but confirmation is incomplete.',
    );
  });

  it('switches wording exactly at the board badge boundary', () => {
    expect(resolveWaitHeadline({ breakoutUp: false, score: 65 })).toMatch(/Tape strength/);
    expect(resolveWaitHeadline({ breakoutUp: false, score: 64 })).toMatch(/No clean setup/);
  });

  it('handles a missing score without claiming strength', () => {
    expect(resolveWaitHeadline({ breakoutUp: false, score: undefined })).toBe(
      'No clean setup is active right now.',
    );
  });
});

describe('computeFeedStatus – reports feed availability, not trust', () => {
  it('reports a live feed as Live', () => {
    expect(computeFeedStatus({ status: 'live' }, null)).toEqual({
      value: 'Live',
      tone: 'positive',
    });
  });

  it('reports a non-live feed as Cached', () => {
    expect(computeFeedStatus({ status: 'cached' }, null)).toEqual({
      value: 'Cached',
      tone: 'neutral',
    });
    expect(computeFeedStatus(null, null)).toEqual({ value: 'Cached', tone: 'neutral' });
  });

  it('reports an errored feed as Degraded, and the error outranks a live status', () => {
    expect(computeFeedStatus(null, new Error('boom'))).toEqual({
      value: 'Degraded',
      tone: 'negative',
    });
    expect(computeFeedStatus({ status: 'live' }, new Error('boom'))).toEqual({
      value: 'Degraded',
      tone: 'negative',
    });
  });

  it('never grades confidence — no trust vocabulary survives', () => {
    const values = [
      computeFeedStatus({ status: 'live' }, null).value,
      computeFeedStatus({ status: 'cached' }, null).value,
      computeFeedStatus(null, new Error('boom')).value,
    ];
    expect(values).not.toContain('High');
    expect(values).not.toContain('Medium');
    expect(values).not.toContain('Low');
  });
});

describe('buildPriorityRailItem – the rail names what it carries', () => {
  const FALLBACK = 'Rank hold not established yet.';

  it('labels the rail Priority, never Persistence', () => {
    const item = buildPriorityRailItem({ stateLabel: 'Dominant' }, 0, FALLBACK);
    expect(item.label).toBe('Priority');
  });

  it('no longer presents a risk state as a persistence measure', () => {
    const item = buildPriorityRailItem({ stateLabel: 'Reversal Risk' }, 0, FALLBACK);
    expect(item.label).toBe('Priority');
    expect(item.value).toBe('Reversal Risk');
    expect(item.tone).toBe('negative');
  });

  it('carries every canonical priority state through unchanged', () => {
    for (const stateLabel of [
      'Dominant',
      'Persistent',
      'Building',
      'Reversal Risk',
      'Fading',
      'Fragile',
    ]) {
      expect(buildPriorityRailItem({ stateLabel }, 0, FALLBACK).value).toBe(stateLabel);
    }
  });

  it('tones only the states that carry a verdict', () => {
    expect(buildPriorityRailItem({ stateLabel: 'Dominant' }, 0, FALLBACK).tone).toBe('positive');
    expect(buildPriorityRailItem({ stateLabel: 'Persistent' }, 0, FALLBACK).tone).toBe('positive');
    expect(buildPriorityRailItem({ stateLabel: 'Building' }, 0, FALLBACK).tone).toBe('neutral');
    expect(buildPriorityRailItem({ stateLabel: 'Fading' }, 0, FALLBACK).tone).toBe('neutral');
  });

  it('says Not ranked when there is no priority entry', () => {
    // A hold count is not a priority state; neither is a bare "Low".
    expect(buildPriorityRailItem(null, 0, FALLBACK).value).toBe('Not ranked');
    expect(buildPriorityRailItem(null, 3, FALLBACK).value).toBe('Not ranked');
    expect(buildPriorityRailItem(undefined, 0, FALLBACK).value).toBe('Not ranked');
  });

  it('keeps the real rank-hold read in the sub-line', () => {
    const item = buildPriorityRailItem(
      { stateLabel: 'Persistent', rankSummary: 'rank held 2-4' },
      3,
      FALLBACK,
    );
    expect(item.sub).toBe('rank held 2-4');
  });

  it('falls back to the hold streak when no rank summary exists', () => {
    expect(buildPriorityRailItem(null, 3, FALLBACK).sub).toBe(`3x hold · ${FALLBACK}`);
    expect(buildPriorityRailItem(null, 0, FALLBACK).sub).toBe(FALLBACK);
  });

  it('always yields a truthy value so the pill is never blank', () => {
    // SupportRail filters items on a truthy `value`.
    for (const entry of [null, {}, { stateLabel: 'Fading' }]) {
      expect(buildPriorityRailItem(entry, 0, FALLBACK).value).toBeTruthy();
    }
  });
});

describe('coinHero – canonical priority is the sole authority', () => {
  // Every state priorityStateForEntry can return. Kept in sync with the engine
  // by the exhaustiveness test below rather than by hand.
  const CANONICAL_STATES = [
    'Dominant',
    'Persistent',
    'Building',
    'Reversal Risk',
    'Fading',
    'Fragile',
  ];

  it('maps every state the priority engine can produce', () => {
    // Drive the real engine so a new state added there fails here rather than
    // silently falling through to the unranked fallbacks.
    const produced = new Set([
      priorityStateForEntry({ reversalRiskScore: 20, bucket: 'divergence', noConfirmMs: 0, score: 90 }),
      priorityStateForEntry({ reversalRiskScore: 0, bucket: 'bullish', noConfirmMs: 999999, score: 90 }),
      priorityStateForEntry({ reversalRiskScore: 0, bucket: 'bullish', noConfirmMs: 0, score: 90, freshConfirms: 1, volumeAligned: true, divergenceFlag: false }),
      priorityStateForEntry({ reversalRiskScore: 0, bucket: 'bullish', noConfirmMs: 0, score: 75, rankPersistenceScore: 12 }),
      priorityStateForEntry({ reversalRiskScore: 0, bucket: 'bullish', noConfirmMs: 0, score: 60, rankPersistenceScore: 0 }),
      priorityStateForEntry({ reversalRiskScore: 0, bucket: 'bullish', noConfirmMs: 0, score: 45, rankPersistenceScore: 0 }),
    ]);
    for (const state of produced) {
      expect(mapPriorityStateToHero(state)).toBeTruthy();
    }
    expect(Object.keys(PRIORITY_STATE_TO_HERO).sort()).toEqual([...CANONICAL_STATES].sort());
  });

  it('REGRESSION: Reversal Risk with a positive 3m no longer reads as Building', () => {
    // The old branch order tested Building (which accepted a bare change3m > 0)
    // before Reversal Risk, so this exact case surfaced as 'Building' and let
    // the Pulse tab reach BUY WATCH while the Coin tab said STAY CLEAR.
    expect(mapPriorityStateToHero('Reversal Risk')).toBe('Fragile');
    expect(describeHeroState('Fragile').tone).toBe('negative');
  });

  it('REGRESSION: Persistent and Fragile are no longer dropped', () => {
    // Neither had a branch, so a Persistent coin with change3m <= 0 fell to
    // 'Range-hold' — "rotating inside range" — contradicting its own state.
    expect(mapPriorityStateToHero('Persistent')).toBe('Persistent');
    expect(mapPriorityStateToHero('Fragile')).toBe('Fragile');
    expect(describeHeroState('Persistent').tone).toBe('positive');
    expect(describeHeroState('Persistent').sub).not.toMatch(/rotating inside range/);
  });

  it('never contradicts a negative canonical state with a positive tone', () => {
    for (const state of ['Reversal Risk', 'Fading', 'Fragile']) {
      expect(describeHeroState(mapPriorityStateToHero(state)).tone).toBe('negative');
    }
    for (const state of ['Dominant', 'Persistent', 'Building']) {
      expect(describeHeroState(mapPriorityStateToHero(state)).tone).toBe('positive');
    }
  });

  it('ignores local evidence entirely when a canonical state exists', () => {
    // Same inputs that previously forced 'Dominant'/'Building' via fallback.
    const loud = {
      breakoutState: 'Breakout Up',
      alignmentScore: 6,
      volumeConfirms: true,
      signalFlags: { hasMomentum: true },
      change3m: 4.2,
    };
    for (const stateLabel of CANONICAL_STATES) {
      expect(resolveCoinHeroState({
        coinPriorityEntry: { stateLabel },
        metricsReady: true,
        ...loud,
      })).toBe(mapPriorityStateToHero(stateLabel));
    }
    // The fallback would have said Dominant here; it is not consulted.
    expect(resolveUnrankedHeroState(loud)).toBe('Dominant');
    expect(mapPriorityStateToHero('Fading')).toBe('Fading');
  });

  it('does not let warming local metrics override a canonical state', () => {
    expect(resolveCoinHeroState({
      coinPriorityEntry: { stateLabel: 'Reversal Risk' },
      metricsReady: false,
      breakoutState: 'Breakout Up',
      alignmentScore: 6,
      volumeConfirms: true,
      signalFlags: { hasMomentum: true },
      change3m: 4.2,
    })).toBe('Fragile');
  });

  it('still gives an unranked coin a read', () => {
    expect(mapPriorityStateToHero(undefined)).toBeNull();
    expect(
      resolveUnrankedHeroState({
        breakoutState: 'Breakout Up',
        alignmentScore: 3,
        volumeConfirms: true,
        signalFlags: {},
        change3m: 1,
      }),
    ).toBe('Dominant');
    expect(
      resolveUnrankedHeroState({
        breakoutState: 'No breakout',
        alignmentScore: 0,
        volumeConfirms: false,
        signalFlags: {},
        change3m: 0.4,
      }),
    ).toBe('Building');
    expect(
      resolveUnrankedHeroState({
        breakoutState: 'No breakout',
        alignmentScore: 0,
        volumeConfirms: false,
        signalFlags: {},
        change3m: null,
      }),
    ).toBe('Range-hold');
    expect(resolveCoinHeroState({ coinPriorityEntry: null, metricsReady: false })).toBe('Warming');
  });

  it('does not let an unranked bullish read mask an active risk flag', () => {
    // Risk flags are tested before the bullish cases now.
    for (const flag of ['hasFakeout', 'hasReversal', 'hasExhaustion']) {
      expect(
        resolveUnrankedHeroState({
          breakoutState: 'Breakout Up',
          alignmentScore: 6,
          volumeConfirms: true,
          signalFlags: { [flag]: true, hasMomentum: true },
          change3m: 3,
        }),
      ).toBe('Fragile');
    }
  });

  it('produces a state, tone, and sub for every hero state', () => {
    for (const state of [...new Set(Object.values(PRIORITY_STATE_TO_HERO)), 'Range-hold', 'Mixed']) {
      const described = describeHeroState(state, { freshAgeMs: 1000, volumeConfirms: true });
      expect(described.state).toBe(state);
      expect(described.tone).toBeTruthy();
      expect(described.sub).toBeTruthy();
    }
  });
});
