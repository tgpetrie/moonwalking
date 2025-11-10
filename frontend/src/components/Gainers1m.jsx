import TokenRow from "./TokenRow.jsx";

export default function Gainers1m({ rows = [], loading, onInfo }) {
  return (
    <section className="panel panel-left">
      <header className="panel-header">1-MIN GAINERS</header>
      <div className="panel-body">
        {loading && !rows.length ? <div className="panel-empty">Loading…</div> : null}
        {rows.map((row, idx) => (
          <TokenRow
            key={row.symbol || idx}
            index={idx + 1}
            symbol={row.symbol}
            price={row.current_price}
            prevPrice={row.initial_price_1min}
            changePct={row.price_change_percentage_1min}
            side="up"
            onInfo={onInfo}
          />
        ))}
      </div>
    </section>
  );
}
