// frontend/src/components/PriceCell.jsx
import { baselineOrNull, displayOrDash } from "../utils/num.js";

export function PriceCell({ token }) {
  const now = token.current_price ?? token.currentPrice ?? token.price ?? null;
  const baseline = baselineOrNull(token.previous_price_1m ?? token.previous_price_3m ?? token.previous_price ?? token.initial_price_1min ?? token.initial_price_3min ?? token.price_1m_ago ?? null);

  const fmtNow = (v) =>
    v == null || !Number.isFinite(Number(v))
      ? "—"
      : `$${Number(v).toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 6,
        })}`;

  const fmtPrev = (v) =>
    displayOrDash(v, (n) =>
      `$${Number(n).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 6,
      })}`
    );

  return (
    <td className="cell-price">
      <span className="token-price-current">{fmtNow(now)}</span>
      <span className="token-price-previous">{fmtPrev(baseline)}</span>
    </td>
  );
}

export default PriceCell;
