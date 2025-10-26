import React, { memo } from "react";
import "../../styles/rows.css";
import { useGainers } from "../../hooks/useData";
import { ColContract } from "./ColContract";
import RowActions from "./RowActions";

type Props = { interval?: "1m" | "3m"; className?: string };

type Row = {
  symbol?: string;
  price?: number;
  changePct?: number;
};

const SKELETON_KEYS = ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"];

const formatPrice = (price?: number) => {
  if (typeof price !== "number" || !Number.isFinite(price)) return "—";
  const decimals = price < 1 ? 4 : 2;
  return price.toFixed(decimals);
};

const formatPct = (pct?: number) => {
  if (typeof pct !== "number" || !Number.isFinite(pct)) return "—";
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(3)}%`;
};

const SkeletonRows = () =>
  SKELETON_KEYS.map((key, index) => (
    <tr key={key} data-test={`gainer-skeleton-${index}`}>
      <td colSpan={4} className="py-3">
        <div className="h-5 w-full animate-pulse rounded-full bg-white/5" />
      </td>
    </tr>
  ));

const DataRows = ({ rows }: { rows: Row[] }) =>
  rows.map((row, index) => {
    const symbol = row.symbol ?? `row-${index}`;
    const price = typeof row.price === "number" ? row.price : undefined;
    const pct = typeof row.changePct === "number" ? row.changePct : undefined;
    return (
      <tr key={symbol} className="bhabit-row fade-in" data-test={`gainer-row-${symbol}`}>
        <td className="py-2">{symbol}</td>
        <td className="py-2 text-right font-mono tabular-nums" data-test={`price-${symbol}`}>
          {formatPrice(price)}
        </td>
        <td
          className={`py-2 text-right font-mono tabular-nums ${Number(pct) >= 0 ? "text-gain" : "text-loss"}`}
          data-test={`pct-${symbol}`}
        >
          {formatPct(pct)}
        </td>
        <td className="py-2 text-right align-top">
          <RowActions symbol={symbol} price={price} />
        </td>
      </tr>
    );
  });

const TwoColumnRows = ({ rows }: { rows: Row[] }) => {
  // pair rows into two-columns; each pair renders as a single table row with colspan=4
  const pairs: Array<[Row | undefined, Row | undefined]> = [];
  for (let i = 0; i < rows.length; i += 2) {
    pairs.push([rows[i], rows[i + 1]]);
  }

  return (
    <>
      {pairs.map((pair, idx) => {
        const left = pair[0];
        const right = pair[1];
        const key = left?.symbol ?? right?.symbol ?? `pair-${idx}`;
        return (
          <tr key={key} className="bhabit-row fade-in" data-test={`gainer-pair-${idx}`}>
            <td colSpan={4} className="py-2">
              <div className="grid grid-cols-2 gap-6 items-start">
                <div className="flex flex-col">
                  {left ? (
                    <>
                      <div className="text-sm font-medium" data-test={`symbol-${left.symbol}`}>
                        {left.symbol}
                      </div>
                      <div className="text-right font-mono tabular-nums">
                        <div data-test={`price-${left.symbol}`}>{formatPrice(left.price)}</div>
                        <div className={`${Number(left.changePct) >= 0 ? "text-gain" : "text-loss"}`} data-test={`pct-${left.symbol}`}>
                          {formatPct(left.changePct)}
                        </div>
                      </div>
                      <div className="self-end mt-1">
                        <RowActions symbol={left.symbol!} price={typeof left.price === "number" ? left.price : undefined} />
                      </div>
                    </>
                  ) : null}
                </div>

                <div className="flex flex-col">
                  {right ? (
                    <>
                      <div className="text-sm font-medium" data-test={`symbol-${right.symbol}`}>
                        {right.symbol}
                      </div>
                      <div className="text-right font-mono tabular-nums">
                        <div data-test={`price-${right.symbol}`}>{formatPrice(right.price)}</div>
                        <div className={`${Number(right.changePct) >= 0 ? "text-gain" : "text-loss"}`} data-test={`pct-${right.symbol}`}>
                          {formatPct(right.changePct)}
                        </div>
                      </div>
                      <div className="self-end mt-1">
                        <RowActions symbol={right.symbol!} price={typeof right.price === "number" ? right.price : undefined} />
                      </div>
                    </>
                  ) : null}
                </div>
              </div>
            </td>
          </tr>
        );
      })}
    </>
  );
};

function GainersTableInner({ interval = "3m", className = "" }: Props) {
  const { rows, loading } = useGainers(interval);

  return (
    <table className={`w-full table-fixed border-collapse ${className}`} data-test="gainers-table">
      <ColContract />
      <thead>
        <tr className="text-xs uppercase tracking-wide opacity-70">
          <th className="py-2 text-left">Asset</th>
          <th className="py-2 text-right">Price</th>
          <th className="py-2 text-right">Δ%</th>
          <th className="py-2" />
        </tr>
      </thead>
      <tbody>{!rows.length && loading ? <SkeletonRows /> : <DataRows rows={rows} />}</tbody>
    </table>
  );
}

export default memo(GainersTableInner);
