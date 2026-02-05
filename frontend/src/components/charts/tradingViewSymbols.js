export function mapToTradingViewSymbol(sym = "") {
  const clean = sym.toUpperCase().replace(/[^A-Z0-9]/g, "");
  if (!clean) return "COINBASE:BTCUSD";
  if (clean.endsWith("USD")) return `COINBASE:${clean}`;
  return `BINANCE:${clean}USDT`;
}
