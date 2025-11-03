export function formatSymbol(raw) {
  if (!raw) return "";
  try {
    return String(raw).replace(/-USD$/i, "");
  } catch (e) {
    return String(raw || "");
  }
}

export default formatSymbol;
