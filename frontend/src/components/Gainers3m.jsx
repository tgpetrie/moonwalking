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
            index={idx + 1}
            symbol={row.symbol}
            price={row.price}
            prevPrice={row.initial_price_3min}
            changePct={row.changePct}
            side="up"
            onInfo={onInfo}
          />
        ))}
    </Panel>
  );
}
