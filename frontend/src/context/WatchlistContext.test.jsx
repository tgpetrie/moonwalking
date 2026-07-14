import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const STORAGE_KEY = "mw_watchlist";
const LEGACY_STORAGE_KEY = "bhabit_watchlist_v2";

describe("WatchlistContext", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("falls back to guest localStorage items when no authenticated session exists", async () => {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify([
        {
          product_id: "BTC-USD",
          symbol: "BTC",
          added_price: 100000,
          added_ts_ms: 123,
        },
      ])
    );

    const fetchMock = vi.fn(async (url) => {
      if (String(url).includes("/api/auth/session")) {
        return {
          ok: false,
          status: 401,
          headers: { get: () => "application/json" },
          json: async () => ({ error: "Authentication required" }),
        };
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    vi.stubGlobal("fetch", fetchMock);

    const { WatchlistProvider, useWatchlist } = await import("./WatchlistContext.jsx");

    function Probe() {
      const { items, mode, ready } = useWatchlist();
      return (
        <div>
          <div>{ready ? "ready" : "loading"}</div>
          <div>{mode}</div>
          <div>{items.map((item) => item.symbol).join(",")}</div>
        </div>
      );
    }

    render(
      <WatchlistProvider>
        <Probe />
      </WatchlistProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("ready")).toBeInTheDocument();
    });

    expect(screen.getByText("guest")).toBeInTheDocument();
    expect(screen.getByText("BTC")).toBeInTheDocument();
  });

  it("hydrates from authenticated backend watchlists when a session exists", async () => {
    const fetchMock = vi.fn(async (url) => {
      if (String(url).includes("/api/auth/session")) {
        return {
          ok: true,
          status: 200,
          headers: { get: () => "application/json" },
          json: async () => ({
            authenticated: true,
            user: {
              id: 1,
              email: "board@example.com",
              name: "Board User",
              username: "board-user",
              plan: "Free Account",
            },
            watchlists: [
              {
                id: "watchlist-1",
                name: "My Watchlist",
                items: [
                  {
                    id: "item-1",
                    itemKey: "ETH",
                    addedPrice: 2500,
                    addedAt: "2026-03-11T15:00:00Z",
                  },
                ],
              },
            ],
          }),
        };
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    vi.stubGlobal("fetch", fetchMock);

    const { WatchlistProvider, useWatchlist } = await import("./WatchlistContext.jsx");

    function Probe() {
      const { items, mode, isAuthenticated, activeWatchlistId } = useWatchlist();
      return (
        <div>
          <div>{mode}</div>
          <div>{isAuthenticated ? "auth" : "anon"}</div>
          <div>{activeWatchlistId}</div>
          <div>{items[0]?.symbol || ""}</div>
          <div>{String(items[0]?.addedPrice || "")}</div>
        </div>
      );
    }

    render(
      <WatchlistProvider>
        <Probe />
      </WatchlistProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("authenticated")).toBeInTheDocument();
    });

    expect(screen.getByText("auth")).toBeInTheDocument();
    expect(screen.getByText("watchlist-1")).toBeInTheDocument();
    expect(screen.getByText("ETH")).toBeInTheDocument();
    expect(screen.getByText("2500")).toBeInTheDocument();
  });

  it("syncs canonical local watchlist items into the authenticated backend watchlist", async () => {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify([
        {
          product_id: "BTC-USD",
          symbol: "BTC",
          added_price: 100000,
          added_ts_ms: 123,
        },
      ])
    );

    const fetchMock = vi.fn(async (url, options = {}) => {
      if (String(url).includes("/api/auth/session")) {
        return {
          ok: true,
          status: 200,
          headers: { get: () => "application/json" },
          json: async () => ({
            authenticated: true,
            user: {
              id: 1,
              email: "board@example.com",
              name: "Board User",
              username: "board-user",
              plan: "Free Account",
            },
            watchlists: [
              {
                id: "watchlist-1",
                name: "My Watchlist",
                items: [
                  {
                    id: "item-1",
                    itemKey: "ETH",
                    addedPrice: 2500,
                    addedAt: "2026-03-11T15:00:00Z",
                  },
                ],
              },
            ],
          }),
        };
      }

      if (
        String(url).includes("/api/watchlists/watchlist-1/items") &&
        options.method === "POST"
      ) {
        const body = JSON.parse(options.body);
        expect(body.itemKey).toBe("BTC-USD");
        expect(body.addedPrice).toBe(100000);
        return {
          ok: true,
          status: 201,
          headers: { get: () => "application/json" },
          json: async () => ({
            watchlist: {
              id: "watchlist-1",
              name: "My Watchlist",
              items: [
                {
                  id: "item-1",
                  itemKey: "ETH",
                  addedPrice: 2500,
                  addedAt: "2026-03-11T15:00:00Z",
                },
                {
                  id: "item-2",
                  itemKey: "BTC",
                  addedPrice: 100000,
                  addedAt: "2026-03-11T15:01:00Z",
                },
              ],
            },
          }),
        };
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    vi.stubGlobal("fetch", fetchMock);

    const { WatchlistProvider, useWatchlist } = await import("./WatchlistContext.jsx");

    function Probe() {
      const { items, mode } = useWatchlist();
      return (
        <div>
          <div>{mode}</div>
          <div>{items.map((item) => item.symbol).sort().join(",")}</div>
        </div>
      );
    }

    render(
      <WatchlistProvider>
        <Probe />
      </WatchlistProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("authenticated")).toBeInTheDocument();
      expect(screen.getByText("BTC,ETH")).toBeInTheDocument();
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("[]");
  });

  it("migrates the old guest key without losing saved items", async () => {
    window.localStorage.setItem(
      LEGACY_STORAGE_KEY,
      JSON.stringify([{ symbol: "SOL", addedPrice: 75, addedAt: 456 }])
    );

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        headers: { get: () => "application/json" },
        json: async () => ({ authenticated: false, user: null, watchlists: [] }),
      }))
    );

    const { WatchlistProvider, useWatchlist } = await import("./WatchlistContext.jsx");

    function Probe() {
      const { items, ready } = useWatchlist();
      return <div>{ready ? items.map((item) => item.productId).join(",") : "loading"}</div>;
    }

    render(
      <WatchlistProvider>
        <Probe />
      </WatchlistProvider>
    );

    await waitFor(() => expect(screen.getByText("SOL-USD")).toBeInTheDocument());

    expect(window.localStorage.getItem(LEGACY_STORAGE_KEY)).toBeNull();
    expect(JSON.parse(window.localStorage.getItem(STORAGE_KEY))).toEqual([
      {
        product_id: "SOL-USD",
        symbol: "SOL",
        added_price: 75,
        added_ts_ms: 456,
      },
    ]);
  });
});
