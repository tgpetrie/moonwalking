// frontend/src/App.jsx
import React from "react";
import { WatchlistProvider } from "./context/WatchlistContext.jsx";
import { SentimentProvider } from "./context/SentimentContext.jsx";
import DashboardShell from "./components/DashboardShell.jsx";

export default function App() {
  return (
    <WatchlistProvider>
      <SentimentProvider>
        <DashboardShell />
      </SentimentProvider>
    </WatchlistProvider>
  );
}
