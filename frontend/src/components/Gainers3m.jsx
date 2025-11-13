import Panel from "./Panel.jsx";
import TokenRow from "./TokenRow.jsx";

export default function Gainers3m({ rows = [], loading, message, onInfo }) {
  return (
    <Panel title="3-Minute Gainers">
      {loading && <div className="panel-empty">Loading…</div>}
      {!loading && message && <div className="panel-empty">{message}</div>}
      {!loading && !message &&
        rows.map((row, idx) => (
          <TokenRow
            key={row.symbol || idx}
            index={idx}
            rank={idx + 1}
            row={row}
            changeKey="price_change_percentage_3min"
            onInfo={onInfo}
          />
        ))}
    </Panel>
  );
}
