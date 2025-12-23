// frontend/src/App.jsx
import { WatchlistProvider, useWatchlist } from "./context/WatchlistContext.jsx";
import { SentimentProvider } from "./context/SentimentContext.jsx";
import { IntelligenceProvider } from "./context/IntelligenceContext.jsx";
import { DataProvider } from "./context/DataContext.jsx";
import DashboardShell from "./components/DashboardShell.jsx";

function IntelligenceBridge({ children }) {
  const { items } = useWatchlist();
  const watchSymbols = items.map(i => i.symbol);

  return (
    <IntelligenceProvider watchSymbols={watchSymbols}>
      {children}
    </IntelligenceProvider>
  );
}

export default function App() {
  return (
    <DataProvider>
      <WatchlistProvider>
        <SentimentProvider>
          <IntelligenceBridge>
            <DashboardShell />
          </IntelligenceBridge>
        </SentimentProvider>
      </WatchlistProvider>
    </DataProvider>
  );
}
