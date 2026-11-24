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

// News/source navigation is separate from the generated Coinbase Trade link.
export function getExternalAlertSourceUrl(value) {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) return null;
    if (["www.coinbase.com", "coinbase.com"].includes(url.hostname.replace(/\.$/, ""))) return null;
    return url.href;
  } catch {
    return null;
  }
}

export const coinbaseSpotUrl = getCoinbaseAdvancedSpotUrl;
export default coinbaseSpotUrl;
