// Display-only helper: strips quote currency (e.g., BTC-USD -> BTC)
export default function baseSymbol(productIdOrSymbol = "") {
  const s = String(productIdOrSymbol || "");
  return s.includes("-") ? s.split("-")[0] : s;
}
