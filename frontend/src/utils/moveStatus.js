// Display text for each status key. The key is kept stable and separate from
// the label because it also drives the `bh-live-rank--<tone>` CSS class; a
// label with a space in it would split into two classes and lose its styling.
//
// "Tape confirmed" rather than "Confirmed": this check only asks whether
// current tape strength scores well. It is not the popup's multi-factor
// posture check, and the narrower wording keeps the two from looking like
// answers to the same question.
export const MOVE_STATUS_LABELS = {
  Confirmed: "Tape confirmed",
  Unconfirmed: "Unconfirmed",
  Extended: "Extended",
  Thin: "Thin",
};

export function getMoveStatusLabel(status, side = "gainer") {
  if (status === "Confirmed" && side === "loser") return "Tape confirmed down";
  return MOVE_STATUS_LABELS[status] || status;
}

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
