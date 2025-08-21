import React from "react";

type Row = { rank: number; symbol: string; price: string; pct: string; peak?: number; isNew?: boolean; flash?: 'up' | 'down' };
interface Props {
  variant?: 'gainers' | 'losers';
  title: string;
  totalPct?: string;
  rows: Row[];
  columns?: { showPrice?: boolean; pctLabel?: string };
}

export default function TableShell({ variant='gainers', title, totalPct='—', rows, columns }: Props){
  const headerClass = variant === 'losers' ? 'header-pink' : 'header-purple';
  const pctLabel = columns?.pctLabel ?? '%';
  const showPrice = columns?.showPrice ?? true;
  return (
    <section className="card">
      <div className={headerClass}>
        <div className="header-inner justify-between">
          <div>{title}</div>
          <div className="num">{totalPct}</div>
        </div>
      </div>
      <table className="u-table">
        <thead className="u-thead">
          <tr className="text-left">
            <th className="col-rank">#</th>
            <th className="col-symbol">Symbol</th>
            {showPrice && <th className="col-price">Price</th>}
            <th className="col-pct">{pctLabel}</th>
          </tr>
        </thead>
        <tbody className="u-tbody">
          {rows.map(r => (
            <tr key={r.rank+':'+r.symbol} className={(r.isNew? 'fx-pop ' : '') + (r.flash ? (r.flash==='up' ? 'fx-flash-up' : 'fx-flash-down') : '')}>
              <td className="col-rank opacity-70">{r.rank}</td>
              <td className="col-symbol font-semibold truncate">{r.symbol}</td>
              {showPrice && <td className="col-price num">{r.price}</td>}
              <td className="col-pct num">{r.pct}{r.peak && <span className="badge-peak">Peak ×{r.peak}</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
