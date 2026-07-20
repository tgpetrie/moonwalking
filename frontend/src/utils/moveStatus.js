export function getMoveStatus(token = {}, side = "gainer") {
  const score = Number(token?.live_score);
  const dataQuality = Number(token?.data_quality) || 0;
  const risks = Array.isArray(token?.live_risks)
    ? token.live_risks.map((item) => String(item).toLowerCase())
    : [];
  const thin = dataQuality < 50 || risks.some((risk) => risk.includes("thin liquidity") || risk.includes("wide spread"));
  if (thin) return "Thin";
  if (risks.some((risk) => risk.includes("extended move"))) return "Extended";
  const confirmed = side === "loser" ? score <= 35 : score >= 65;
  return confirmed && dataQuality >= 67 ? "Confirmed" : "Unconfirmed";
}
