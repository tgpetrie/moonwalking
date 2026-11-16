import { afterEach, describe, expect, it, vi } from "vitest";
import { API_ENDPOINTS, fetchMacroCycleScan, normalizeScanSymbols } from "./api.js";

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

  it("asks for the cycle view by name", () => {
    const parsed = new URL(API_ENDPOINTS.chartRead("THETA", null, "cycle"), "http://localhost");
    expect(parsed.searchParams.get("horizon")).toBe("cycle");
  });
});

describe("macro cycle scan helper", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("builds the bare endpoint with no symbols", () => {
    const parsed = new URL(API_ENDPOINTS.macroCycleScan(), "http://localhost");
    expect(parsed.pathname).toMatch(/\/api\/macro-cycle-scan$/);
    expect(parsed.search).toBe("");
  });

  it("adds the watchlist as clean, sorted, de-duplicated base symbols", () => {
    const parsed = new URL(API_ENDPOINTS.macroCycleScan(["render-usd", "FET", { symbol: "Theta" }, "RENDER", "bad symbol!", ""]), "http://localhost");
    expect(parsed.searchParams.get("symbols")).toBe("FET,RENDER,THETA");
  });

  it("caps the request at the 30 symbols the server accepts", () => {
    const many = Array.from({ length: 45 }, (_, i) => `C${String(i).padStart(2, "0")}`);
    expect(normalizeScanSymbols(many)).toHaveLength(30);
    expect(normalizeScanSymbols("RENDER")).toEqual([]);
  });

  it("returns the scan payload as sent, including a warming answer", async () => {
    const warming = { status: "warming", industry: { available: false, reason: "warming" }, breadth: null, buckets: {}, coins: [] };
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => warming,
    }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchMacroCycleScan(["ZZTOP"])).resolves.toEqual(warming);
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/api\/macro-cycle-scan\?symbols=ZZTOP$/);
  });

  it("rejects an answer that is not a scan object", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ["not", "a", "scan"],
    })));

    await expect(fetchMacroCycleScan(["ZZBAD"])).rejects.toThrow(/Unexpected macro cycle scan response/);
  });
});
