import { describe, expect, it } from "vitest";
import { API_ENDPOINTS } from "./api.js";

describe("chartRead endpoint builder", () => {
  it("adds event context query params when supplied", () => {
    const endpoint = API_ENDPOINTS.chartRead("SOL", {
      type_key: "BREAKOUT",
      evidence: {
        window: "3m",
        price: 148.2,
        pct: 5.8,
      },
    });

    const parsed = new URL(endpoint, "http://localhost");
    expect(parsed.pathname).toContain("/api/chart-read/SOL");
    expect(parsed.searchParams.get("event_type")).toBe("BREAKOUT");
    expect(parsed.searchParams.get("event_window")).toBe("3m");
    expect(parsed.searchParams.get("event_price")).toBe("148.2");
    expect(parsed.searchParams.get("event_pct")).toBe("5.8");
  });

  it("keeps the legacy endpoint shape when no context is supplied", () => {
    const endpoint = API_ENDPOINTS.chartRead("SOL");

    const parsed = new URL(endpoint, "http://localhost");
    expect(parsed.pathname).toContain("/api/chart-read/SOL");
    expect(parsed.search).toBe("");
  });
});
