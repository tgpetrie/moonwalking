import React from "react";

export type TableRow = { rank: number; symbol: string; price: string; pct: string; peak?: number; isNew?: boolean; flash?: 'up' | 'down' };
interface Props {
  variant?: 'gainers' | 'losers';
  title: string;
  totalPct?: string;
  rows: TableRow[];
  columns?: { showPrice?: boolean; pctLabel?: string };
  loading?: boolean;
  skeletonRows?: number;
  emptyMessage?: string;
}

export default function TableShell({ variant='gainers', title, totalPct='—', rows, columns, loading=false, skeletonRows=4, emptyMessage='No data' }: Props){
  const headerClass = variant === 'losers' ? 'header-pink' : 'header-purple';
  const pctLabel = columns?.pctLabel ?? '%';
  const showPrice = columns?.showPrice ?? true;
  const showSkeletons = loading && rows.length === 0;
  return (
    <section className="card">
      <div className={headerClass}>
        <div className="header-inner justify-between">
          <div>{title}</div>
          <div className="num">{totalPct}</div>
        </div>
      </div>
  <table className="u-table" aria-live="polite">
        <thead className="u-thead">
          <tr className="text-left">
            <th className="col-rank">#</th>
            <th className="col-symbol">Symbol</th>
            {showPrice && <th className="col-price">Price</th>}
            <th className="col-pct">{pctLabel}</th>
          </tr>
        </thead>
        <tbody className="u-tbody">
          {showSkeletons && Array.from({length:skeletonRows}).map((_,i)=>(
            <tr key={'sk'+i} className="opacity-70 animate-pulse">
              <td className="col-rank">{i+1}</td>
              <td className="col-symbol"><div className="h-4 w-16 bg-white/10 rounded"/></td>
              {showPrice && <td className="col-price"><div className="h-4 w-12 bg-white/10 rounded ml-auto"/></td>}
              <td className="col-pct"><div className="h-4 w-10 bg-white/10 rounded ml-auto"/></td>
            </tr>
          ))}
          {!showSkeletons && rows.map(r => (
            <tr key={r.rank+':'+r.symbol} className={(r.isNew? 'fx-pop ' : '') + (r.flash ? (r.flash==='up' ? 'fx-flash-up' : 'fx-flash-down') : '')}>
              <td className="col-rank opacity-70">{r.rank}</td>
              <td className="col-symbol font-semibold truncate">{r.symbol}</td>
              {showPrice && <td className="col-price num">{r.price}</td>}
              <td className="col-pct num">{r.pct}{r.peak && <span className="badge-peak">Peak ×{r.peak}</span>}</td>
            </tr>
          ))}
          {!loading && rows.length===0 && !showSkeletons && (
            <tr>
              <td colSpan={showPrice?4:3} className="text-center py-4 text-sm opacity-60">{emptyMessage}</td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}
