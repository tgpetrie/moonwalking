import { useEffect, useState } from "react";
import { WatchlistProvider, useWatchlist } from "./context/WatchlistContext.jsx";
import { IntelligenceProvider } from "./context/IntelligenceContext.jsx";
import { DataProvider } from "./context/DataContext.jsx";
import DashboardShell from "./components/DashboardShell.jsx";
import MvpApp from "./mvp/MvpApp.jsx";

const mvpRouteSet = new Set([
  "/login",
  "/signup",
  "/app/dashboard",
  "/app/watchlists",
  "/app/portfolio",
  "/app/settings",
]);

function isMvpRoute(pathname) {
  return (
    mvpRouteSet.has(pathname) ||
    pathname.startsWith("/app/") ||
    pathname.startsWith("/u/")
  );
}

function IntelligenceBridge({ children }) {
  const { items } = useWatchlist();
  const watchSymbols = items.map((item) => item.symbol);

  return (
    <IntelligenceProvider watchSymbols={watchSymbols}>
      {children}
    </IntelligenceProvider>
  );
}

function LegacyDashboardApp() {
  return (
    <DataProvider>
      <WatchlistProvider>
        <IntelligenceBridge>
          <div className="bh-shell">
            <DashboardShell />
          </div>
        </IntelligenceBridge>
      </WatchlistProvider>
    </DataProvider>
  );
}

export default function App() {
  const [pathname, setPathname] = useState(() => window.location.pathname || "/");

  useEffect(() => {
    const syncPath = () => setPathname(window.location.pathname || "/");
    const { pushState, replaceState } = window.history;

    const wrapHistoryMethod = (method) =>
      function wrappedHistoryMethod(...args) {
        const result = method.apply(this, args);
        window.dispatchEvent(new Event("locationchange"));
        return result;
      };

    window.history.pushState = wrapHistoryMethod(pushState);
    window.history.replaceState = wrapHistoryMethod(replaceState);

    window.addEventListener("popstate", syncPath);
    window.addEventListener("locationchange", syncPath);

    return () => {
      window.history.pushState = pushState;
      window.history.replaceState = replaceState;
      window.removeEventListener("popstate", syncPath);
      window.removeEventListener("locationchange", syncPath);
    };
  }, []);

  if (isMvpRoute(pathname)) {
    return <MvpApp />;
  }

  return <LegacyDashboardApp />;
}
