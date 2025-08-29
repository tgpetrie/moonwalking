import React, { useMemo, useRef, useEffect } from "react";
import { useAppStore } from "../state/store";

// Local, non-invasive formatters (no external deps)
const trim = (s='') => s.replace(/-USD$/,'');
const fmtPrice = (n) => {
  if (n == null || Number.isNaN(Number(n))) return "—";
  const v = Number(n);
  if (v >= 100) return v.toFixed(0);
  if (v >= 1)   return v.toFixed(3);
  return v.toFixed(6);
};
const fmtPct = (n) => {
  if (n == null || Number.isNaN(Number(n))) return "—";
  const v = Number(n);
  return (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
};

/**
 * 1‑MINUTE GAINERS (single table)
 * - Title bar: ORANGE (per final spec)
 * - Rank + % text: PURPLE with subtle glow on row hover (scoped via wrapper)
 * - Columns: # | Symbol | Price | 1m % (universal widths)
 * - Data: reads from shared store (t1m), filters ≥0.1%, sorts desc, top 8
 * - Peak ×N badge inline without breaking alignment
 */
export default function GainersTable1m(){
  const t1m = useAppStore(s=>s.t1m);
  const seenRef = useRef(new Set());

  const rows = useMemo(() => ([...(t1m||[])]
    .filter(r => Math.abs(Number(r.pct1m ?? r.pct ?? 0)) >= 0.1)
    .sort((a,b) => Number(b.pct1m ?? b.pct ?? 0) - Number(a.pct1m ?? a.pct ?? 0))
    .slice(0, 8)
    .map((r, i) => ({
      rank: i + 1,
      key: r.symbol,
      symbol: trim(r.symbol || ""),
      price: fmtPrice(r.price),
      pct: fmtPct(r.pct1m ?? r.pct),
      peak: r.peak,
      isNew: !seenRef.current.has(r.symbol)
    }))
  ), [t1m]);

  // mark as seen so the pop-in anim only happens once per symbol
  useEffect(() => { rows.forEach(r => seenRef.current.add(r.key)); }, [rows]);

  return (
    <section className="card gainers-table">
      {/* ORANGE header for gainers (title stays exact) */}
      <div className="header-orange">
        <div className="header-inner justify-between">
          <div>1‑MIN GAINERS</div>
          <div className="num">{rows.length ? rows[0].pct : "—"}</div>
        </div>
      </div>

      <table className="u-table">
        <thead className="u-thead">
          <tr className="text-left">
            <th className="col-rank">#</th>
            <th className="col-symbol">Symbol</th>
            <th className="col-price">Price</th>
            <th className="col-pct">1m %</th>
          </tr>
        </thead>
        <tbody className="u-tbody">
          {rows.map((r) => (
            <tr key={`${r.rank}-${r.key}`} className={r.isNew ? "fx-pop" : ""}>
              <td className="col-rank">{r.rank}</td>
              <td className="col-symbol font-semibold truncate">{r.symbol}</td>
              <td className="col-price num">${r.price}</td>
              <td className="col-pct num">
                <span className={`num ${Number(r.pct.replace(/[^0-9.-]/g,'')) >= 0 ? 'text-pct-positive' : 'text-pct-negative'}`}>{r.pct}</span>
                {r.peak && r.peak >= 1 ? (
                  <span className="badge-peak badge-peak--compact" aria-hidden>{r.peak <= 1 ? 'x' : `x${Math.floor(r.peak)}`}</span>
                ) : null}
              </td>
            </tr>
          ))}
          {!rows.length && (
            <tr>
              <td colSpan={4} className="py-6 text-center opacity-60">Backend unavailable (no data)</td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}