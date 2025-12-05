// src/components/TokenRowSimple.jsx
import React from "react";
import TokenRow from "./TokenRow.jsx";
import { tickerFromSymbol } from "../utils/format";

// Simple wrapper that reuses the canonical TokenRow grid so legacy callers stay aligned.
export default function TokenRowSimple({ index = 0, row = {}, onInfo }) {
  const symbolRaw =
    row?.symbol ||
    row?.ticker ||
    row?.slug ||
    "--";
  const symbol = tickerFromSymbol(symbolRaw) || symbolRaw;

  const price =
    row?.price ??
    row?.current_price ??
    row?.last_price ??
    null;

  const previousPrice =
    row?.previous_price ??
    row?.initial_price_3min ??
    row?.initial_price_1min ??
    row?.baseline ??
    null;

  const pctRaw =
    row?.pct ??
    row?.price_change_percentage_1min ??
    row?.price_change_percentage_3min ??
    row?.change_1m ??
    row?.change_3m ??
    null;

  const pct =
    pctRaw != null && !Number.isNaN(Number(pctRaw))
      ? Number(pctRaw)
      : null;

  const rowType = pct == null ? undefined : pct >= 0 ? "gainer" : "loser";

  return (
    <TokenRow
      rank={index + 1}
      row={{
        ...row,
        symbol,
        current_price: price,
        previous_price: previousPrice,
        price_change_percentage_1min: pct,
        price_change_percentage_3min: pct,
      }}
      rowType={rowType}
      onInfo={onInfo}
    />
  );
}
