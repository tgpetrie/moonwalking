const COINBASE_ORIGIN = "https://www.coinbase.com";

// Trade destinations always use the USD spot pair, never a backend URL override.
export function getCoinbaseAdvancedSpotUrl(coin) {
  const candidates = typeof coin === "string"
    ? [coin]
    : [coin?.product_id, coin?.productId, coin?.product, coin?.pair,
        coin?.symbol, coin?.base_currency, coin?.ticker, coin?.base];
  for (const candidate of candidates) {
    if (typeof candidate !== "string") continue;
    const base = candidate.trim().toUpperCase().split(/[-/]/)[0].trim();
    if (/^[A-Z0-9]+$/.test(base)) {
      return `${COINBASE_ORIGIN}/advanced-trade/spot/${base}-USD`;
    }
  }
  return null;
}

export const coinbaseSpotUrl = getCoinbaseAdvancedSpotUrl;
export default coinbaseSpotUrl;
