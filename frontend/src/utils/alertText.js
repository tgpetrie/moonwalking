const escapeRegExp = (value) => String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export function stripLeadingSymbol(message, symbol) {
  const msg = String(message || "").trim();
  const sym = String(symbol || "").trim().toUpperCase();
  if (!msg || !sym) return msg;

  const symEsc = escapeRegExp(sym);
  const re = new RegExp(`^${symEsc}(?:[-/ ]?(?:USD|USDT|USDC))?\\s+`, "i");
  return msg.replace(re, "").trim();
}

export function stripLeadingType(message, typeLabel) {
  const msg = String(message || "").trim();
  const type = String(typeLabel || "").trim();
  if (!msg || !type) return msg;
  const typeEsc = escapeRegExp(type);
  return msg.replace(new RegExp(`^${typeEsc}\\s*[:\\-—]\\s*`, "i"), "").trim();
}
