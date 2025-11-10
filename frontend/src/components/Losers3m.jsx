import TokenRow from "./TokenRow.jsx";

export default function Losers3m({ rows = [], loading, onInfo }) {
  return (
    <section className="panel panel-right">
      <header className="panel-header">3-MIN LOSERS</header>
      <div className="panel-body">
        {loading && !rows.length ? <div className="panel-empty">Loading…</div> : null}
        {rows.map((row, idx) => (
          <TokenRow
            key={row.symbol || idx}
            index={idx + 1}
            symbol={row.symbol}
            price={row.current_price}
            prevPrice={row.initial_price_3min}
            changePct={row.price_change_percentage_3min}
            side="down"
            onInfo={onInfo}
          />
        ))}
      </div>
    </section>
  );
}
