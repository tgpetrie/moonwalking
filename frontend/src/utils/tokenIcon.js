export function tokenIconUrl(symbol) {
  const clean = String(symbol || "")
    .trim()
    .toLowerCase()
    .replace(/-(usd|usdt|perp)$/i, "")
    .replace(/[^a-z0-9]/g, "");
  return clean ? `https://assets.coincap.io/assets/icons/${clean}@2x.png` : "";
}

export function tokenIconFallback(symbol) {
  const clean = String(symbol || "")
    .trim()
    .toUpperCase()
    .replace(/-(USD|USDT|PERP)$/i, "")
    .replace(/[^A-Z0-9]/g, "");
  return clean.slice(0, 3) || "?";
}
