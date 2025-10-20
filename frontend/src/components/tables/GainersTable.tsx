import React from "react";
import "../../styles/rows.css";
import { useGainers } from "../../hooks/useData";
import { ColContract } from "./ColContract";
import RowActions from "./RowActions";

type Props = { interval?: "1m" | "3m"; className?: string };

export default function GainersTable({ interval = "3m", className = "" }: Props) {
  const { rows, loading } = useGainers(interval);

  return (
    <table className={`w-full table-fixed border-collapse ${className}`}>
      <ColContract />
      <thead>
        <tr className="text-xs uppercase tracking-wide opacity-70">
          <th className="text-left py-2">Asset</th>
          <th className="text-right py-2">Price</th>
          <th className="text-right py-2">Δ%</th>
          <th className="py-2" />
        </tr>
      </thead>
      <tbody>
        {(!rows.length && loading)
          ? Array.from({ length: 8 }).map((_, i) => (
              <tr key={`skeleton-${i}`}>
                <td colSpan={4} className="py-3">
                  <div
                    className="h-5 w-full animate-pulse bg-white/5 rounded-full"
                    style={{ animationDelay: `${i * 60}ms` }}
                  />
                </td>
              </tr>
            ))
          : rows.map((r, idx) => (
              <tr key={r.symbol} className="bhabit-row fade-in" style={{ animationDelay: `${idx * 45}ms` }}>
                <td className="py-2">{r.symbol}</td>
                <td className="py-2 text-right font-mono tabular-nums">
                  {Number.isFinite(r.price) ? r.price.toFixed(r.price < 1 ? 4 : 2) : "—"}
                </td>
                <td className={`py-2 text-right font-mono tabular-nums ${Number(r.changePct) >= 0 ? "text-gain" : "text-loss"}`}>
                  {Number.isFinite(r.changePct)
                    ? `${r.changePct >= 0 ? "+" : ""}${r.changePct.toFixed(3)}%`
                    : "—"}
                </td>
                <td className="py-2 text-right align-top">
                  <RowActions symbol={r.symbol} price={typeof r.price === "number" ? r.price : undefined} />
                </td>
              </tr>
            ))}
      </tbody>
    </table>
  );
}
