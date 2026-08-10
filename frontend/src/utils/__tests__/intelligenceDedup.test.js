import { describe, expect, it } from "vitest";
import {
  createEventKey,
  shouldSkip,
  markSeen,
  expireOldKeys,
} from "../intelligenceDedup.js";

const NOW = 1_800_000_000_000;

// ---------------------------------------------------------------------------
// createEventKey
// ---------------------------------------------------------------------------

describe("createEventKey", () => {
  it("produces a stable semantic key from type+symbol+window+direction", () => {
    const a = { type_key: "whale_move", symbol: "DOGE-USD", window: "1h", direction: "up" };
    expect(createEventKey(a)).toBe("whale_move|DOGE|1h|up");
  });

  it("strips USD suffix from symbol", () => {
    expect(createEventKey({ type_key: "moonshot", symbol: "BTC-USD" })).toBe("moonshot|BTC||");
    expect(createEventKey({ type_key: "moonshot", symbol: "BTC-USDT" })).toBe("moonshot|BTC||");
  });

  it("falls back to alert.type when type_key is absent", () => {
    const a = { type: "CRATER", symbol: "ETH", window: "3m", direction: "down" };
    expect(createEventKey(a)).toBe("crater|ETH|3m|down");
  });

  it("reads window from evidence when top-level window is absent", () => {
    const a = { type_key: "breakout", symbol: "SOL", evidence: { window: "1m" } };
    expect(createEventKey(a)).toBe("breakout|SOL|1m|");
  });

  it("normalises type to lowercase", () => {
    expect(createEventKey({ type: "WHALE_MOVE", symbol: "BTC", direction: "UP" })).toBe(
      "whale_move|BTC||up"
    );
  });

  it("two alerts with same semantic fields share a key regardless of UUID", () => {
    const a = { type_key: "dump", symbol: "ADA-USD", window: "3m", direction: "down", id: "dump_ADA-USD_abc" };
    const b = { type_key: "dump", symbol: "ADA-USD", window: "3m", direction: "down", id: "dump_ADA-USD_xyz" };
    expect(createEventKey(a)).toBe(createEventKey(b));
  });
});

// ---------------------------------------------------------------------------
// shouldSkip / markSeen — duplicate suppression
// ---------------------------------------------------------------------------

describe("shouldSkip / markSeen", () => {
  it("allows an unseen key through", () => {
    const seen = new Map();
    expect(shouldSkip("moonshot|BTC||up", seen, NOW)).toBe(false);
  });

  it("blocks a key that was just seen", () => {
    const seen = new Map();
    markSeen("moonshot|BTC||up", seen, NOW);
    expect(shouldSkip("moonshot|BTC||up", seen, NOW + 1000)).toBe(true);
  });

  it("backend alert repeated across polls appears only once", () => {
    const seen = new Map();
    const key = "whale_move|DOGE|1h|up";
    // Poll 1 — fires
    expect(shouldSkip(key, seen, NOW)).toBe(false);
    markSeen(key, seen, NOW);
    // Polls 2-N within TTL — same ongoing condition, skip
    for (let i = 1; i <= 10; i++) {
      expect(shouldSkip(key, seen, NOW + i * 8_000)).toBe(true);
    }
  });

  it("same symbol+type re-appears after TTL (backend cooldown cycle reset)", () => {
    const seen = new Map();
    const key = "whale_move|DOGE|1h|up";
    markSeen(key, seen, NOW);
    // After 5 minutes (TTL)
    expect(shouldSkip(key, seen, NOW + 5 * 60_000 + 1)).toBe(false);
  });

  it("MOONSHOT does not duplicate as a SPIKE — different semantic keys are independent", () => {
    const seen = new Map();
    const moonKey = "moonshot|DOGE|1m|up";
    markSeen(moonKey, seen, NOW);
    // A hypothetical legacy SPIKE key is different — not blocked
    expect(shouldSkip("spike|DOGE|1m|up", seen, NOW + 1000)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// expireOldKeys — prevents unbounded Map growth
// ---------------------------------------------------------------------------

describe("expireOldKeys", () => {
  it("removes entries older than 2×TTL", () => {
    const seen = new Map();
    markSeen("old|A||", seen, NOW - 12 * 60_000); // 12 min ago — beyond 2×5min
    markSeen("fresh|B||", seen, NOW - 60_000); // 1 min ago — within TTL
    expireOldKeys(seen, NOW);
    expect(seen.has("old|A||")).toBe(false);
    expect(seen.has("fresh|B||")).toBe(true);
  });

  it("bounded history: 50 symbols accumulate then prune to recent-only", () => {
    const seen = new Map();
    // 50 stale entries added 15 min ago
    for (let i = 0; i < 50; i++) {
      markSeen(`whale_move|C${i}|1h|up`, seen, NOW - 15 * 60_000);
    }
    // 3 fresh entries
    markSeen("moonshot|BTC||up", seen, NOW - 30_000);
    markSeen("dump|ETH||down", seen, NOW - 45_000);
    markSeen("fomo|SOL||up", seen, NOW - 20_000);

    expireOldKeys(seen, NOW);
    expect(seen.size).toBe(3);
  });

  it("unknown backend type is not blocked — unknown key never collides with real types", () => {
    const seen = new Map();
    // Real moonshot fires
    markSeen("moonshot|XRP|1m|up", seen, NOW);
    // An unmapped/unknown type for same symbol is separate key
    expect(shouldSkip("|XRP||", seen, NOW + 100)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Volume gap-filler dedup design (unit contract, not component)
// ---------------------------------------------------------------------------

describe("volume shock does not spam every percentage change", () => {
  it("same symbol can only fire once per cooldown window via volCooldownRef pattern", () => {
    // Simulate the volCooldownRef pattern used in AnomalyStream
    const cooldown = new Map();
    const COOLDOWN_MS = 5 * 60_000;

    const shouldFireVolume = (symbol, pct, nowMs) => {
      if (pct < 80) return false;
      const last = cooldown.get(symbol) || 0;
      if (nowMs - last < COOLDOWN_MS) return false;
      cooldown.set(symbol, nowMs);
      return true;
    };

    // First tick at 80% — fires
    expect(shouldFireVolume("DOGE", 82, NOW)).toBe(true);
    // Same symbol 8 seconds later, even higher volume — blocked by cooldown
    expect(shouldFireVolume("DOGE", 95, NOW + 8_000)).toBe(false);
    // After cooldown passes — fires again
    expect(shouldFireVolume("DOGE", 110, NOW + COOLDOWN_MS + 1)).toBe(true);
    // Different symbol fires independently
    expect(shouldFireVolume("BTC", 120, NOW + 1000)).toBe(true);
  });
});
