const COINBASE_ORIGIN = "https://www.coinbase.com";

export function coinbaseSpotUrl(row) {
  // Prefer an explicit trade URL if backend provides it.
  const trade = row?.trade_url || row?.tradeUrl || row?.trade;
  if (trade && typeof trade === 'string' && trade.startsWith('http')) {
    return trade;
  }

  // Only use an explicit, backend-provided product id. Do not guess from symbol.
  const pid = row?.product_id || row?.productId || row?.product;
  if (!pid) return null;
  return `${COINBASE_ORIGIN}/advanced-trade/spot/${encodeURIComponent(String(pid))}`;
}

export default coinbaseSpotUrl;
