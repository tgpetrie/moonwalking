import React from 'react';
import TokenRow from './TokenRow.jsx';
import { useData } from '../context/useData';

export default function LosersTable({ rows: externalRows, onInfo }) {
  const usingExternal = Array.isArray(externalRows);
  const { data } = useData();

  const finalRows = usingExternal ? externalRows : (data?.losers_3m ?? []);

  if (!finalRows || finalRows.length === 0) return <div className="text-center py-8">No losers data</div>;

  return (
    <div className="overflow-visible w-full panel-3m flex flex-col gap-1">
      {finalRows.map((r, idx) => (
        <TokenRow
          key={r.symbol || idx}
          row={r}
          index={idx}
          changeKey={r.price_change_3min ? 'price_change_3min' : 'price_change_percentage_3min'}
          onInfo={onInfo}
        />
      ))}
    </div>
  );
}
