// frontend/src/App.jsx
import React, { useState, useCallback } from "react";
import { WatchlistProvider } from "./context/WatchlistContext.jsx";
import { useGainers, useLosers3m } from "./hooks/useData.js";
import RefreshTicker from "./components/RefreshTicker.jsx";
import Gainers1m from "./components/Gainers1m.jsx";
import ThreeMinRow from "./components/ThreeMinRow.jsx";
import AssetTabbedPanel from "./components/AssetTabbedPanel.jsx";

export default function App() {
  const g1m = useGainers("1m");
  const g3m = useGainers("3m");
  const losers = useLosers3m();

  const [selected, setSelected] = useState(null);

  const handleRefresh = useCallback(() => {
    g1m.mutate && g1m.mutate();
    g3m.mutate && g3m.mutate();
    losers.mutate && losers.mutate();
  }, [g1m, g3m, losers]);

  const handleInfo = useCallback((payload) => {
    setSelected(payload);
  }, []);

  return (
    <WatchlistProvider>
      <RefreshTicker seconds={30} onRefresh={handleRefresh} />

      <main>
        <Gainers1m rows={g1m.rows} loading={g1m.loading} onInfo={handleInfo} />
        <ThreeMinRow
          gainers={g3m.rows}
          losers={losers.rows}
          loading={g3m.loading || losers.loading}
          onInfo={handleInfo}
        />
      </main>

      <AssetTabbedPanel asset={selected} onClose={() => setSelected(null)} />
    </WatchlistProvider>
  );
}

