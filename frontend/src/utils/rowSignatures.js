const round2 = (value) => {
  const num = typeof value === "string" ? Number(value) : Number.isFinite(value) ? value : Number(value);
  const safe = Number.isFinite(num) ? num : 0;
  return Math.round(safe * 100) / 100;
};

export const sigTop = (rows = [], topN = 12, pctFn = () => 0, keyFn = () => "") => {
  if (!Array.isArray(rows) || !rows.length) return "";
  const normalized = rows.slice(0, topN);
  return normalized
    .map((row) => {
      const key = String(keyFn(row) ?? "").trim() || "UNKNOWN";
      return `${key}:${round2(pctFn(row))}`;
    })
    .join("|");
};

export default { sigTop };
