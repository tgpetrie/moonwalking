import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("DataProvider", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.restoreAllMocks();
    vi.stubEnv("VITE_PUBLISH_UI_MS", "0");
    vi.stubEnv("VITE_FAST_1M_MS", "8000");
    vi.stubEnv("VITE_ALERTS_POLL_MS", "8000");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("publishes /data snapshots immediately when UI cadence is zero", async () => {
    const fetchMock = vi.fn(async (url) => {
      const href = String(url);

      if (href.includes("/api/alerts")) {
        return {
          ok: true,
          status: 200,
          headers: { get: () => "application/json" },
          json: async () => ({
            active: [],
            recent: [],
            meta: { ok: true },
          }),
        };
      }

      if (href.includes("/data")) {
        return {
          ok: true,
          status: 200,
          headers: { get: () => "application/json" },
          json: async () => ({
            gainers_1m: [{ symbol: "BTC", price: 100000 }],
            gainers_3m: [],
            losers_3m: [],
            banner_1h_price: [],
            banner_1h_volume: [],
            alerts: [],
            updated_at: "2026-03-11T16:00:00.000Z",
            meta: {},
            coverage: {},
          }),
        };
      }

      throw new Error(`Unexpected fetch: ${href}`);
    });

    vi.stubGlobal("fetch", fetchMock);

    const { DataProvider, useData } = await import("./DataContext.jsx");

    function Probe() {
      const { oneMinRows } = useData();
      return <div>{oneMinRows.length}</div>;
    }

    render(
      <DataProvider>
        <Probe />
      </DataProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("1")).toBeInTheDocument();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/data"),
      expect.objectContaining({
        cache: "no-store",
        headers: { Accept: "application/json" },
      })
    );
  });

  it("keeps mover values and order through a stale response and publishes again on recovery", async () => {
    localStorage.clear();
    let now = Date.now();
    vi.spyOn(Date, "now").mockImplementation(() => now);
    const rows = [{ symbol: "SOL", price: 100 }, { symbol: "ETH", price: 200 }];
    const incoming = [{ symbol: "ETH", price: 210 }, { symbol: "SOL", price: 110 }];
    const snapshot = (movers, staleSeconds) => ({
      gainers_1m: movers,
      gainers_3m: movers,
      losers_3m: movers,
      meta: { staleSeconds },
    });
    let payload = snapshot(rows, 26);
    vi.stubGlobal("fetch", vi.fn(async (url) => ({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => String(url).endsWith("/data") ? payload : { active: [], recent: [] },
    })));

    const { DataProvider, useData } = await import("./DataContext.jsx");
    let context;
    function Probe() {
      context = useData();
      return null;
    }
    render(<DataProvider><Probe /></DataProvider>);
    await waitFor(() => expect(context.oneMinRows).toEqual(rows));
    const originalTimes = context.boardSourceTimes;
    expect(context.threeMin).toEqual({ gainers: rows, losers: rows });

    now += 13000;
    payload = snapshot(incoming, 74);
    await act(async () => { await context.refetch(); });
    expect(context.feedSourceMs).toBe(now - 74000);
    expect(context.boardSourceTimes).toEqual(originalTimes);
    expect(context.oneMinRows).toEqual(rows);
    expect(context.threeMin).toEqual({ gainers: rows, losers: rows });

    now += 13000;
    payload = snapshot(incoming, 26);
    await act(async () => { await context.refetch(); });
    expect(context.oneMinRows).toEqual(incoming);
    expect(context.threeMin).toEqual({ gainers: incoming, losers: incoming });
    expect(Object.values(context.boardSourceTimes)).toEqual(Array(3).fill(now - 26000));
  });
});
