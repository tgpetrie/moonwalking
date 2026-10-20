import { DAY, dateText } from './macroChart.js';

// Shared with the Python worker: allow five minutes after UTC midnight to settle.
export const CANDLE_SETTLEMENT_SECONDS = 300;
export const HISTORY_RECHECK_MS = 60000;
export const expectedDailyEnd = (nowMs = Date.now()) => Math.floor((nowMs / 1000 - CANDLE_SETTLEMENT_SECONDS) / DAY) * DAY;

export function historyFreshness(history, nowMs = Date.now()) {
  const expectedEnd = expectedDailyEnd(nowMs);
  const completed = history.candles.filter((p) => p.complete && p.end <= history.captured_at);
  const latestEnd = completed.reduce((end, p) => Math.max(end, p.end), 0);
  return { current: latestEnd >= expectedEnd && latestEnd <= nowMs / 1000,
    latest_end: latestEnd, through_utc: latestEnd ? dateText(latestEnd - 1) : null,
    expected_through_utc: dateText(expectedEnd - 1), expected_end: expectedEnd,
    checked_at: history.source?.fetched_at ?? history.source?.provenance?.fetched_at ?? null };
}

export function requireCurrentHistory(history, nowMs = Date.now()) {
  const fresh = historyFreshness(history, nowMs);
  if (!fresh.current) throw new Error(`Provider history ends ${fresh.through_utc ?? 'before any completed day'} UTC; expected through ${fresh.expected_through_utc} UTC. Current analysis was not published. Try refreshing again.`);
  return history;
}
