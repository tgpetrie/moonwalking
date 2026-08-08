import { describe, expect, it } from "vitest";
import {
  buildForYouStream,
  holdingSymbolsFrom,
  normalizeMarketAlert,
  toTsMs,
  KINDS,
  MARKET_MAX_AGE_MS,
  USER_EVENT_MAX_AGE_MS,
} from "./intelligenceEvents.js";

const NOW = 1_800_000_000_000; // fixed ms clock — stream must be deterministic

const userEvent = (over = {}) => ({
  id: "evt_1",
  symbol: "BTC",
  event_type: "price_cross",
  observed_value: 115,
  boundary_value: 110,
  triggered_ts: (NOW - 10 * 60 * 1000) / 1000,
  explanation: "BTC rose above $110.00, reaching $115.00. You created this alert.",
  ...over,
});

const suggestion = (over = {}) => ({
  id: "rec_1",
  symbol: "ETH",
  basis: "portfolio",
  reason: "Because ETH is in your portfolio, Moonwalkings can notify you…",
  created_at: new Date(NOW - 3600_000).toISOString(),
  ...over,
});

const marketAlert = (over = {}) => ({
  id: "mk_1",
  symbol: "SOL",
  type_key: "moonshot",
  severity: "high",
  message: "SOL strong upside move",
  ts: (NOW - 20 * 60 * 1000) / 1000,
  ...over,
});

const build = (over = {}) =>
  buildForYouStream({
    nowMs: NOW,
    isWatchlisted: () => false,
    isHolding: () => false,
    hasRuleFor: () => false,
    ...over,
  });

describe("admission is personal", () => {
  it("excludes market items with no personal tie", () => {
    const stream = build({ marketAlerts: [marketAlert()] });
    expect(stream).toHaveLength(0);
  });

  it("admits watchlisted, held, and rule-tracked symbols with their reason", () => {
    const alerts = [
      marketAlert({ id: "a", symbol: "SOL" }),
      marketAlert({ id: "b", symbol: "ADA", type_key: "dump" }),
      marketAlert({ id: "c", symbol: "DOT", type_key: "whale" }),
    ];
    const stream = build({
      marketAlerts: alerts,
      isWatchlisted: (s) => s === "SOL",
      isHolding: (s) => s === "ADA",
      hasRuleFor: (s) => s === "DOT",
    });
    const bySymbol = Object.fromEntries(stream.map((i) => [i.symbol, i.reason]));
    expect(bySymbol).toEqual({ SOL: "watchlist", ADA: "holding", DOT: "your_rule" });
  });

  it("your own fired alerts are always admitted", () => {
    const stream = build({ userEvents: [userEvent()] });
    expect(stream).toHaveLength(1);
    expect(stream[0].kind).toBe(KINDS.YOUR_ALERT);
    expect(stream[0].reason).toBe("your_rule");
  });
});

describe("ranking", () => {
  it("a fired alert outranks a market signal on the same coin class", () => {
    const stream = build({
      userEvents: [userEvent({ symbol: "BTC" })],
      marketAlerts: [marketAlert({ symbol: "SOL", severity: "critical" })],
      isWatchlisted: () => true,
    });
    expect(stream[0].kind).toBe(KINDS.YOUR_ALERT);
  });

  it("a suggestion outranks ambient market items", () => {
    const stream = build({
      recommendations: [suggestion({ basis: "watchlist" })],
      marketAlerts: [marketAlert({ severity: "low" })],
      isWatchlisted: () => true,
    });
    expect(stream[0].kind).toBe(KINDS.SUGGESTION);
  });

  it("holding beats watchlist for otherwise identical market items", () => {
    const stream = build({
      marketAlerts: [
        marketAlert({ id: "w", symbol: "SOL" }),
        marketAlert({ id: "h", symbol: "ADA" }),
      ],
      isWatchlisted: (s) => s === "SOL",
      isHolding: (s) => s === "ADA",
    });
    expect(stream[0].symbol).toBe("ADA");
    expect(stream[1].symbol).toBe("SOL");
  });

  it("a fresh critical market event on a HOLDING outranks a portfolio suggestion", () => {
    // The band that matters most: a crash of a coin you hold must not lose
    // to a static "would you like an alert?" card.
    const stream = build({
      recommendations: [suggestion({ symbol: "ETH", basis: "portfolio" })],
      marketAlerts: [
        marketAlert({
          symbol: "ADA",
          type_key: "crater",
          severity: "critical",
          ts: (NOW - 60_000) / 1000, // fresh
        }),
      ],
      isHolding: (s) => s === "ADA",
    });
    expect(stream[0].symbol).toBe("ADA");
    expect(stream[0].kind).toBe(KINDS.MARKET);
    expect(stream[1].kind).toBe(KINDS.SUGGESTION);
  });

  it("your fired alert still outranks even an urgent market event", () => {
    const stream = build({
      userEvents: [userEvent({ symbol: "BTC" })],
      marketAlerts: [
        marketAlert({
          symbol: "ADA",
          type_key: "crater",
          severity: "critical",
          ts: (NOW - 60_000) / 1000,
        }),
      ],
      isHolding: (s) => s === "ADA",
    });
    expect(stream[0].kind).toBe(KINDS.YOUR_ALERT);
  });

  it("is deterministic for a fixed clock", () => {
    const args = {
      userEvents: [userEvent()],
      recommendations: [suggestion()],
      marketAlerts: [marketAlert()],
      isWatchlisted: () => true,
    };
    const a = build(args).map((i) => i.id);
    const b = build(args).map((i) => i.id);
    expect(a).toEqual(b);
  });
});

describe("noise control", () => {
  it("dedupes market items per symbol+type keeping the newest", () => {
    const stream = build({
      marketAlerts: [
        marketAlert({ id: "old", ts: (NOW - 3 * 3600_000) / 1000 }),
        marketAlert({ id: "new", ts: (NOW - 5 * 60_000) / 1000 }),
      ],
      isWatchlisted: () => true,
    });
    expect(stream).toHaveLength(1);
    expect(stream[0].id).toBe("mk:new");
  });

  it("ages out stale market items and old user events", () => {
    const stream = build({
      marketAlerts: [
        marketAlert({ ts: (NOW - MARKET_MAX_AGE_MS - 60_000) / 1000 }),
      ],
      userEvents: [
        userEvent({ triggered_ts: (NOW - USER_EVENT_MAX_AGE_MS - 60_000) / 1000 }),
      ],
      isWatchlisted: () => true,
    });
    expect(stream).toHaveLength(0);
  });

  it("drops a price-family market item near in time to your fired alert (same occurrence)", () => {
    // Fired at NOW-10m; moonshot at NOW-20m → same symbol, price family,
    // within 2h: this is the move the user's own alert already reported.
    const stream = build({
      userEvents: [userEvent({ symbol: "BTC" })],
      marketAlerts: [
        marketAlert({ id: "same", symbol: "BTC" }),
        marketAlert({ id: "other", symbol: "SOL" }),
      ],
      isWatchlisted: () => true,
    });
    const kindsBySymbol = stream.map((i) => `${i.symbol}:${i.kind}`);
    expect(kindsBySymbol).toContain("BTC:your_alert");
    expect(kindsBySymbol).toContain("SOL:market");
    expect(kindsBySymbol).not.toContain("BTC:market");
  });

  it("keeps a non-price event (whale) on the fired symbol — distinct intelligence", () => {
    const stream = build({
      userEvents: [userEvent({ symbol: "BTC" })],
      marketAlerts: [
        marketAlert({ id: "whale", symbol: "BTC", type_key: "whale" }),
      ],
      isWatchlisted: () => true,
    });
    const kinds = stream.map((i) => `${i.symbol}:${i.kind}`);
    expect(kinds).toContain("BTC:your_alert");
    expect(kinds).toContain("BTC:market"); // whale is not the same occurrence
  });

  it("keeps a price-family event outside the proximity window", () => {
    // Fired at NOW-10m; dump happened NOW-5h → a different move entirely.
    const stream = build({
      userEvents: [userEvent({ symbol: "BTC" })],
      marketAlerts: [
        marketAlert({
          id: "olddump",
          symbol: "BTC",
          type_key: "dump",
          ts: (NOW - 5 * 3600_000) / 1000,
        }),
      ],
      isWatchlisted: () => true,
    });
    expect(stream.map((i) => i.id)).toContain("mk:olddump");
  });

  it("respects the stream limit", () => {
    const alerts = Array.from({ length: 50 }, (_, i) =>
      marketAlert({ id: `a${i}`, symbol: `C${i}`, ts: (NOW - i * 60_000) / 1000 })
    );
    const stream = build({ marketAlerts: alerts, isWatchlisted: () => true, limit: 10 });
    expect(stream).toHaveLength(10);
  });
});

describe("adapters", () => {
  it("holdingSymbolsFrom reads recommendation and rule basis", () => {
    const set = holdingSymbolsFrom({
      recommendations: [suggestion({ symbol: "ETH", basis: "portfolio" }),
                        suggestion({ id: "r2", symbol: "SOL", basis: "watchlist" })],
      rules: [{ symbol: "ADA", recommendation_basis: "portfolio" }],
    });
    expect(set.has("ETH")).toBe(true);
    expect(set.has("ADA")).toBe(true);
    expect(set.has("SOL")).toBe(false);
  });

  it("normalizeMarketAlert tolerates both field conventions", () => {
    const a = normalizeMarketAlert({ symbol: "BTC-USD", type: "WHALE", urgency: "HIGH", title: "t", ts: 1 });
    expect(a.symbol).toBe("BTC");
    expect(a.typeKey).toBe("whale");
    expect(a.severity).toBe("high");
  });

  it("toTsMs handles seconds, millis, and ISO strings", () => {
    expect(toTsMs(1_800_000_000)).toBe(1_800_000_000_000);
    expect(toTsMs(1_800_000_000_000)).toBe(1_800_000_000_000);
    expect(toTsMs("2027-01-15T00:00:00Z")).toBe(Date.parse("2027-01-15T00:00:00Z"));
    expect(toTsMs(null)).toBeNull();
  });
});
