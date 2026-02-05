// LEGACY UI COMPONENT
// This file is not used in the current BHABIT home dashboard.
// See `docs/UI_HOME_DASHBOARD.md` for the canonical component list.
//
// Keep this file here for historical reference. Do not re-import into AppRoot.jsx.
import React, { useEffect, useState } from 'react';
import TokenRow from './TokenRow.jsx';
import { useData } from '../context/useData';
import { normalizeTableRow } from '../lib/adapters';

/**
 * 3‑minute gainers list using adapter-normalized rows and unified TokenRow.
 * Keeps polling behavior from the original component but renders using
 * the hardened TokenRow to ensure consistent click/info/star behavior.
 */
export default function GainersTable({ refreshTrigger, rows: externalRows, loading: externalLoading, error: externalError, onInfo }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const usingExternal = Array.isArray(externalRows);
  const { data } = useData();

  // If parent passed rows, prefer them. Otherwise read from DataContext.
  const finalRows = usingExternal ? externalRows : (data?.gainers_3m ?? []);
  const finalLoading = usingExternal ? !!externalLoading : false;
  const finalError = externalError || null;

  if (finalLoading && finalRows.length === 0) return <div className="text-center py-8">Loading...</div>;
  if (!finalLoading && finalError && finalRows.length === 0) return <div className="text-center py-8">Backend unavailable (no data)</div>;
  if (!finalLoading && !finalError && finalRows.length === 0) return <div className="text-center py-8">No gainers data</div>;

  return (
    <div className="overflow-auto w-full">
      <div className="flex flex-col gap-1">
        {finalRows.map((r, idx) => (
          <TokenRow
            key={r.symbol || idx}
            index={typeof r.rank === 'number' ? r.rank - 1 : idx}
            row={r}
            changeKey={r.price_change_3min ? 'price_change_3min' : 'price_change_percentage_3min'}
            onInfo={onInfo}
          />
        ))}
      </div>
    </div>
  );
}
