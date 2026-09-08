import React from "react";
import { render, screen, fireEvent, waitFor, within, cleanup } from "@testing-library/react";
import { vi, beforeEach, afterEach, expect, test } from "vitest";
import { WatchlistsPage, buildMarketBySymbol } from "./MvpApp.jsx";

vi.mock("../context/DataContext.jsx", () => ({ DataProvider: ({ children }) => children, useData: () => ({
  connectionStatus: "LIVE", loading: false,
  data: { latest_by_symbol: {
    BTC: { price: 100, pct_1m: 0, pct_3m: 2, pct_1h: -3, sample_ts: Date.now()/1000, live_score: 80 },
    ETH: { price: 50, pct_1m: -1, pct_3m: null, pct_1h: 4, sample_ts: Date.now()/1000, live_score: 40 },
  } },
}) }));

const items = ["BTC", "ETH", "MISSING"].map((symbol, position) => ({ id: symbol, itemKey: symbol, title: symbol, notes: "Auto-added from portfolio", position }));
const props = () => ({ watchlists: [{ id: "one", name: "Main", items }, { id: "two", name: "Short term", items: [] }], selectedWatchlistId: "one", setSelectedWatchlistId: vi.fn(), onCreateWatchlist: vi.fn(), onAddItem: vi.fn(), onRemoveItem: vi.fn(), onRenameWatchlist: vi.fn(), onDeleteWatchlist: vi.fn(), onUpdateItemNotes: vi.fn(), onUpdateWatchlistNotes: vi.fn() });
beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ updated_at: Date.now()/1000, stale: false, products: { "BTC-USD": { price: 100, pct_24h: 5 }, "ETH-USD": { price: 50, pct_24h: -8 } } }) }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const card = (symbol) => screen.getByRole("heading", { name: symbol, exact: true }).closest("article");
const order = () => [...document.querySelectorAll(".mw-watchlist-asset h3")].map((node) => node.textContent);

test("normalizes canonical payload and preserves null versus real zero", () => {
  const result = buildMarketBySymbol({ data: { latest_by_symbol: { BTC: { price: null, pct_1m: 0, pct_3m: null } } } });
  expect(result.get("BTC").price).toBeNull();
  expect(result.get("BTC").changes).toMatchObject({ "1m": 0, "3m": null });
});

test("each period displays its own change and All displays all four", async () => {
  render(<WatchlistsPage {...props()} />);
  await waitFor(() => expect(card("BTC").textContent).toContain("+5.00%"));
  for (const [label, value] of [["1 min", "0.00%"], ["3 min", "+2.00%"], ["60 min", "-3.00%"]]) {
    fireEvent.click(screen.getByRole("button", { name: label, exact: true }));
    expect(card("BTC").textContent).toContain(value);
  }
  fireEvent.click(screen.getByRole("button", { name: "All", exact: true }));
  expect(card("BTC").querySelectorAll(".mw-market-move")).toHaveLength(4);
  expect(card("ETH").textContent).toContain("Unavailable");
  expect(screen.queryByText("Crypto", { exact: true })).toBeNull();
  expect(document.body.textContent).not.toContain("Auto-added from portfolio");
});

test("performance sorting keeps missing data last for both directions", async () => {
  render(<WatchlistsPage {...props()} />);
  await waitFor(() => expect(card("BTC").textContent).toContain("+5.00%"));
  expect(order()).toEqual(["BTC", "ETH", "MISSING"]);
  fireEvent.click(screen.getByRole("button", { name: "Top losers" }));
  expect(order()).toEqual(["ETH", "BTC", "MISSING"]);
  fireEvent.click(screen.getByRole("button", { name: "Biggest moves" }));
  expect(order()).toEqual(["ETH", "BTC", "MISSING"]);
});

test("view settings remain specific to each list and selected coins can form a new list", async () => {
  const handlers = props();
  const page = render(<WatchlistsPage {...handlers} />);
  fireEvent.click(screen.getByRole("button", { name: "List", exact: true }));
  expect(document.querySelector(".mw-watchlist-grid--list")).not.toBeNull();
  fireEvent.click(screen.getByRole("checkbox", { name: "Select BTC" }));
  fireEvent.click(screen.getByRole("button", { name: "Create list from selection" }));
  await waitFor(() => expect(handlers.onCreateWatchlist).toHaveBeenCalledWith(["BTC"]));
  page.rerender(<WatchlistsPage {...handlers} selectedWatchlistId="two" />);
  expect(screen.getByRole("button", { name: "Cards", exact: true }).getAttribute("aria-pressed")).toBe("true");
  page.rerender(<WatchlistsPage {...handlers} />);
  expect(screen.getByRole("button", { name: "List", exact: true }).getAttribute("aria-pressed")).toBe("true");
});
