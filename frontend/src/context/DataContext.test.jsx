import { render, screen, waitFor } from "@testing-library/react";
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
});
