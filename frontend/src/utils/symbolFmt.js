// Display-only symbol formatter: strips quote currency (e.g., BTC-USD -> BTC).
export function displaySymbol(raw) {
  if (!raw) return "";
  const s = String(raw).toUpperCase();
  return s.includes("-") ? s.split("-")[0] : s;
}

export default displaySymbol;
