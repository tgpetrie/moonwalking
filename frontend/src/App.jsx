// frontend/src/App.jsx — cleaned single-definition App
import React, { Suspense, useEffect, useState, lazy } from "react";
import { WatchlistProvider, useWatchlist } from "./context/WatchlistContext.jsx";
import { useData } from "./hooks/useData";
import DashboardShell from "./components/DashboardShell.jsx";

const SentimentPanel = lazy(() => import("./components/cards/SentimentPanel.jsx"));

function WatchlistReconciler({ bySymbol }) {
  const { refreshFromData } = useWatchlist();
  useEffect(() => {
    refreshFromData(bySymbol);
  }, [bySymbol, refreshFromData]);
  return null;
}

export default function App() {
  const { bySymbol, ...data } = useData();
  const [sentimentOpen, setSentimentOpen] = useState(false);
  const [sentimentRow, setSentimentRow] = useState(null);
  const [sentimentInterval, setSentimentInterval] = useState("3m");

  const handleInfo = (rowOrSymbol, interval = "3m") => {
    const nextRow =
      typeof rowOrSymbol === "string"
        ? { symbol: rowOrSymbol }
        : rowOrSymbol || null;
    setSentimentRow(nextRow);
    setSentimentInterval(interval);
    setSentimentOpen(Boolean(nextRow));
  };

  return (
    <WatchlistProvider>
      <WatchlistReconciler bySymbol={bySymbol} />
      <DashboardShell
        data={data}
        bySymbol={bySymbol}
        onInfo={handleInfo}
      />
      {sentimentOpen && (
        <Suspense fallback={null}>
          <SentimentPanel
            open={sentimentOpen}
            onClose={() => setSentimentOpen(false)}
            row={sentimentRow}
            interval={sentimentInterval}
          />
        </Suspense>
      )}
    </WatchlistProvider>
  );
}
