import { describe, expect, it } from "vitest";
import { humanizeError, AlertApiError } from "./alertRulesApi.js";

describe("humanizeError", () => {
  it("keeps the server's human-written validation messages", () => {
    const msg = "That target is already at or below the current price ($100.00).";
    expect(humanizeError(msg, 400)).toBe(msg);
    expect(humanizeError("Time window must be one of: 1h, 4h, 24h", 400)).toContain(
      "Time window"
    );
  });

  it("never surfaces machine tokens as UI copy", () => {
    // Regression: the dev proxy returns {"error":"backend_unreachable"}, which
    // was rendering verbatim as the empty-state heading.
    for (const token of ["backend_unreachable", "rule_expired", "no_price", "ECONNREFUSED"]) {
      const out = humanizeError(token, 502);
      expect(out).not.toBe(token);
      expect(out).toBe("Could not reach the server.");
    }
  });

  it("falls back sensibly for empty or missing messages", () => {
    expect(humanizeError(null, 0)).toBe("Could not reach the server.");
    expect(humanizeError("", 500)).toBe("Could not reach the server.");
    expect(humanizeError(undefined, 400)).toBe("That didn't work.");
  });
});

describe("AlertApiError", () => {
  it("flags 401 as an auth state rather than a failure", () => {
    expect(new AlertApiError("Sign in", 401).isAuthRequired).toBe(true);
    expect(new AlertApiError("Nope", 400).isAuthRequired).toBe(false);
    expect(new AlertApiError("Nope", 0).isAuthRequired).toBe(false);
  });
});
