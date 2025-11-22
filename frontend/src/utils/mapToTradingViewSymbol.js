export function mapToTradingViewSymbol(sym) {
  if (!sym) return null;

  const s = String(sym).toUpperCase().replace(/[-\s\/]/g, "");

  // Prefer Coinbase for USD pairs
  if (s.endsWith("USD") || s.endsWith("USDT") || s.endsWith("USDC")) {
    return `COINBASE:${s}`;
  }

  // fallback to BINANCE with USDT suffix
  return `BINANCE:${s}USDT`;
}
