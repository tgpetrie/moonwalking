const COINBASE_ORIGIN = "https://www.coinbase.com";

export function coinbaseSpotUrl(row) {
  // Prefer an explicit trade URL if backend provides it.
  const trade = row?.trade_url || row?.tradeUrl || row?.trade;
  if (trade && typeof trade === 'string' && trade.startsWith('http')) {
    return trade;
  }

  // Get product_id or construct from symbol
  let pid = row?.product_id || row?.productId || row?.product;

  // If no product_id, construct it from symbol (e.g., "ETH" -> "ETH-USD")
  if (!pid && row?.symbol) {
    const symbol = String(row.symbol).toUpperCase().trim();
    if (symbol) {
      pid = symbol.includes('-') ? symbol : `${symbol}-USD`;
    }
  }

  if (!pid) return null;
  return `${COINBASE_ORIGIN}/advanced-trade/spot/${encodeURIComponent(String(pid).toUpperCase())}`;
}

export default coinbaseSpotUrl;
