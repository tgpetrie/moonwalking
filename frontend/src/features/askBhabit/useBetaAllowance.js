// Founder-funded beta allowance. No BYOK, no subscription — just a small, honest
// counter of how many real analyses remain. Sample analyses do NOT consume the
// allowance (they're the always-free first-value path); only real questions do.
//
// State is persisted to localStorage so a refresh doesn't reset the trial, and
// degrades gracefully when storage is unavailable (private mode / SSR).

import { useCallback, useMemo, useState } from "react";

export const DEFAULT_BETA_LIMIT = 3;
const STORAGE_KEY = "askBhabit.betaUsed.v1";

function readUsed() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = Number.parseInt(raw ?? "0", 10);
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
  } catch {
    return 0;
  }
}

function writeUsed(value) {
  try {
    window.localStorage.setItem(STORAGE_KEY, String(value));
  } catch {
    /* ignore — allowance still tracked in memory for this session */
  }
}

export function useBetaAllowance(limit = DEFAULT_BETA_LIMIT) {
  const [used, setUsed] = useState(() => (typeof window === "undefined" ? 0 : readUsed()));

  const remaining = Math.max(0, limit - used);
  const exhausted = remaining <= 0;

  const consume = useCallback(() => {
    let didConsume = false;
    setUsed((prev) => {
      if (prev >= limit) return prev;
      didConsume = true;
      const next = prev + 1;
      writeUsed(next);
      return next;
    });
    return didConsume;
  }, [limit]);

  const reset = useCallback(() => {
    writeUsed(0);
    setUsed(0);
  }, []);

  const label = useMemo(
    () =>
      exhausted
        ? "Your beta analysis allowance has been used. More access is coming soon."
        : `${remaining} of ${limit} beta analyses remaining`,
    [exhausted, remaining, limit]
  );

  return { used, remaining, limit, exhausted, label, consume, reset };
}
