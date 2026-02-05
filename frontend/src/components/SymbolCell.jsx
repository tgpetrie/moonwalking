// frontend/src/components/SymbolCell.jsx
export function SymbolCell({ token }) {
  const symbol = token.symbol || "?";
  const name = token.base ?? token.name ?? token.displayName ?? token.symbol ?? "";
  return (
    <td className="cell-token">
      <span className="token-symbol">{symbol}</span>
      <span className="token-label">{name}</span>
    </td>
  );
}

export default SymbolCell;
