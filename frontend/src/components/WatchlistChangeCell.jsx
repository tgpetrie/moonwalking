// frontend/src/components/WatchlistChangeCell.jsx
export function WatchlistChangeCell({ token }) {
  const value = token.percentChange ?? 0;
  const isPositive = value >= 0;

  return (
    <td className="cell-change">
      <span className={`token-change ${isPositive ? "pos" : "neg"}`}>
        {Number(value).toFixed(3)}%
      </span>
    </td>
  );
}

export default WatchlistChangeCell;
