// LEGACY UI COMPONENT
// This file is not used in the current BHABIT home dashboard.
// See `docs/UI_HOME_DASHBOARD.md` for the canonical component list.
//
// Keep this file here for historical reference. Do not re-import into AppRoot.jsx.
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
