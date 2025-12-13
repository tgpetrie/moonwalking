// frontend/src/components/Change1mCell.jsx
export function Change1mCell({ token }) {
  const value = token.change_1m ?? token.pct ?? 0;
  const isPositive = value >= 0;

  return (
    <td className="cell-change">
      <span className={`token-change ${isPositive ? "pos" : "neg"}`}>
        {Number(value).toFixed(3)}%
      </span>
    </td>
  );
}

export default Change1mCell;
