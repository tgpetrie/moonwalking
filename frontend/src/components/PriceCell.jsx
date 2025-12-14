// frontend/src/components/PriceCell.jsx
import { baselineOrNull } from "../utils/num";

export function PriceCell({ token }) {
  const now = token.current_price ?? token.currentPrice ?? token.price ?? null;
  const prev = baselineOrNull(
    token.previous_price_1m ??
      token.previous_price_3m ??
      token.previous_price ??
      token.initial_price_1min ??
      token.initial_price_3min ??
      token.price_1m_ago ??
      null
  );

  const fmt = (v) =>
    v == null
      ? "—"
      : `$${Number(v).toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 6,
        })}`;

  return (
    <td className="cell-price">
      <span className="token-price-current">{fmt(now)}</span>
      <span className="token-price-previous">{fmt(prev)}</span>
    </td>
  );
}

export default PriceCell;
