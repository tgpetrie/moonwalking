// frontend/src/App.jsx
import { WatchlistProvider, useWatchlist } from "./context/WatchlistContext.jsx";
import { SentimentProvider } from "./context/SentimentContext.jsx";
import { IntelligenceProvider } from "./context/IntelligenceContext.jsx";
import { DataProvider, useData } from "./context/DataContext.jsx";
import DashboardShell from "./components/DashboardShell.jsx";
import { FloatingActionMenu } from "./components/FloatingActionMenu.jsx";
import AlertInbox from "./components/AlertInbox.jsx";

function IntelligenceBridge({ children }) {
  const { items } = useWatchlist();
  const watchSymbols = items.map(i => i.symbol);

  return (
    <IntelligenceProvider watchSymbols={watchSymbols}>
      {children}
    </IntelligenceProvider>
  );
}

function AlertSystemBridge() {
  const { alerts, alertsUnread, markAllRead, clearAllAlerts } = useData();

  const handleAlertClick = (alert) => {
    if (!alert?.symbol) return;

    // Dispatch event to open sentiment popup for this token
    if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
      window.dispatchEvent(new CustomEvent("openInfo", { detail: alert.symbol }));
    }

    // Also scroll to the token row if visible
    try {
      const symbolNorm = alert.symbol.toUpperCase();
      const row = document.querySelector(`[data-symbol="${symbolNorm}"]`);
      if (row) {
        row.scrollIntoView({ behavior: "smooth", block: "center" });
        row.classList.add("highlight-pulse");
        setTimeout(() => row.classList.remove("highlight-pulse"), 2000);
      }
    } catch (err) {
      console.debug("Could not scroll to token:", err);
    }
  };

  // Scroll to Intelligence Log (AnomalyStream)
  const scrollToAlerts = () => {
    const anomalyStream = document.querySelector('.bh-anom');
    if (anomalyStream) {
      anomalyStream.scrollIntoView({ behavior: "smooth", block: "center" });
      // Expand if collapsed
      if (anomalyStream.getAttribute('data-collapsed') === '1') {
        const header = anomalyStream.querySelector('.bh-anom-head');
        if (header) header.click();
      }
    }
  };

  // Define FAB actions
  const fabActions = [
    {
      id: "alerts",
      icon: "🔔",
      label: "Alerts",
      ariaLabel: "View alerts in Intelligence Log",
      onClick: scrollToAlerts,
    },
    // Future: Learning action will be added here
    // {
    //   id: "learning",
    //   icon: "📚",
    //   label: "Learning",
    //   ariaLabel: "Open learning resources",
    //   onClick: handleLearningClick,
    // },
  ];

  return (
    <>
      <AlertInbox
        alerts={alerts || []}
        unreadCount={alertsUnread}
        markAllRead={markAllRead}
        clearAllAlerts={clearAllAlerts}
        onAlertClick={handleAlertClick}
      />
      <FloatingActionMenu
        actions={fabActions}
        mainIcon="⚡"
        mainAriaLabel="Quick actions menu"
      />
    </>
  );
}

export default function App() {
  return (
    <DataProvider>
      <WatchlistProvider>
        <SentimentProvider>
          <IntelligenceBridge>
            <div className="bh-shell">
              <DashboardShell />
            </div>
            <AlertSystemBridge />
          </IntelligenceBridge>
        </SentimentProvider>
      </WatchlistProvider>
    </DataProvider>
  );
}
