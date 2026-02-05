// frontend/src/lib/normalizeMarketRow.js

import { baselineOrNull } from "../utils/num.js";

// strip -USD, /USD, -USDT, ... for display
export function cleanSymbol(symbol = "") {
  return symbol.replace(/[-/](USD|USDT|USDC)$/i, "").toUpperCase();
}

/**
 * Normalize a 1m gainer row from /data
 * backend shape:
 *  {
 *    symbol: "DOT-USD",
 *    current_price: 2.888,
 *    initialPrice1min: 2.853,
 *    priceChangePct1min: 1.2267,
 *    rank: 1,
 *    ...
 *  }
 */
export function normalize1m(row = {}) {
  return {
    symbol: row.symbol,
    displaySymbol: cleanSymbol(row.symbol),
    rank: typeof row.rank === "number" ? row.rank : null,
    price: typeof row.current_price === "number" ? row.current_price : null,
    prevPrice: baselineOrNull(row.initial_price_1min),
    changePct:
      typeof row.price_change_percentage_1min === "number"
        ? row.price_change_percentage_1min
        : null,
    side: "gain",
  };
}

/**
 * Normalize a 3m row (gainer or loser) from /data
 * backend shape:
 *  {
 *    symbol: "DOT-USD",
 *    current_price: 2.888,
 *    initialPrice3min: 2.8789,
 *    priceChangePct3min: 0.3157,
 *    rank: 1
 *  }
 */
export function normalize3m(row = {}, { side = "gain" } = {}) {
  return {
    symbol: row.symbol,
    displaySymbol: cleanSymbol(row.symbol),
    rank: typeof row.rank === "number" ? row.rank : null,
    price: typeof row.current_price === "number" ? row.current_price : null,
    prevPrice: baselineOrNull(row.initial_price_3min),
    changePct:
      typeof row.price_change_percentage_3min === "number"
        ? row.price_change_percentage_3min
        : null,
    side,
  };
}
