import { act, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { boardSourceTime, deriveFreshness, formatAge } from "../../utils/boardFreshness.js";
import FreshnessStamp from "./FreshnessStamp.jsx";

afterEach(() => vi.useRealTimers());

it.each([
  ["1m", 42, "live"],
  ["1m", 43, "delayed"],
  ["1m", 45, "delayed"],
  ["1m", 46, "stale"],
  ["3m", 52, "live"],
  ["3m", 53, "delayed"],
  ["3m", 60, "delayed"],
  ["3m", 61, "stale"],
])("uses the %s status boundary at %ss", (cadence, age, expected) => {
  const nowMs = age * 1000;
  expect(deriveFreshness({ cadence, sourceMs: 0, lastSuccessMs: nowMs, nowMs }).status)
    .toBe(expected);
});

it("goes offline at 60 seconds without a successful request even on the 3m board", () => {
  expect(deriveFreshness({ cadence: "3m", sourceMs: 0, lastSuccessMs: 0, nowMs: 60000 }).status)
    .toBe("offline");
});

it("keeps source age and time since a successful request separate", () => {
  const lastSuccessMs = 100000;
  const sourceMs = boardSourceTime({ meta: { staleSeconds: 74 } }, lastSuccessMs);
  const result = deriveFreshness({ sourceMs, lastSuccessMs, nowMs: 101000 });
  expect(result).toEqual({ status: "stale", ageSeconds: 75 });
  expect(formatAge(result.ageSeconds)).toBe("1m 15s");
  expect(formatAge(3)).toBe("3s");
  expect(formatAge(3700)).toBe("1h 1m");
});

it("publishes status changes while the visible age updates independently", () => {
  vi.useFakeTimers();
  const now = Date.now();
  const statusChanged = vi.fn();
  render(<FreshnessStamp sourceMs={now} lastSuccessMs={now} onStatusChange={statusChanged} />);

  act(() => vi.advanceTimersByTime(5000));
  expect(screen.getByRole("status")).toHaveTextContent(/^Live$/);
  expect(screen.getByText("5s ago")).toBeInTheDocument();
  expect(statusChanged.mock.calls).toEqual([["live"]]);

  act(() => vi.advanceTimersByTime(38000));
  expect(screen.getByRole("status")).toHaveTextContent(/^Delayed$/);
  expect(statusChanged.mock.calls).toEqual([["live"], ["delayed"]]);
});
