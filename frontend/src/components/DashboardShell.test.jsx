import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../hooks/useDashboardData", () => ({
  useDashboardData: () => ({
    gainers1m: [],
    gainers3m: [],
    losers3m: [],
    bannerVolume1h: [],
    bannerPrice1h: [],
    alerts: [],
    loading: false,
    error: null,
    lastUpdated: "2026-08-12T12:00:00.000Z",
    fatal: false,
    coverage: {},
    warming: false,
    warming3m: false,
    staleSeconds: 0,
    partial: false,
    lastGoodTs: null,
    alertsMeta: { market_pressure: { index: 72 } },
    liveRankings: [],
    boardOutcomes: { boards: {} },
  }),
}));

vi.mock("../context/WatchlistContext.jsx", () => ({
  useWatchlist: () => ({ items: [], toggle: vi.fn() }),
}));

vi.mock("./VolumeBannerScroll.jsx", () => ({ default: () => null }));
vi.mock("./TopBannerScroll.jsx", () => ({ default: () => null }));
vi.mock("./SentimentPopupAdvanced.jsx", () => ({ default: () => null }));
vi.mock("./AlertsPanelGlobal.jsx", () => ({ default: () => null }));
vi.mock("./AnomalyStream.jsx", () => ({ default: () => null }));
vi.mock("./AlertsDock.jsx", () => ({ default: () => null }));
vi.mock("./AskBhabitPanel.jsx", () => ({ default: () => null }));
vi.mock("./BoardWrapper.jsx", () => ({ default: ({ children }) => children }));
vi.mock("./GainersTable1Min.jsx", () => ({ default: () => null }));
vi.mock("./GainersTable3Min.jsx", () => ({ default: () => null }));
vi.mock("./LosersTable3Min.jsx", () => ({ default: () => null }));
vi.mock("./WatchlistPanel.jsx", () => ({ default: () => null }));
vi.mock("./LiveLeaderboard.jsx", () => ({ default: () => null }));
vi.mock("./MarketSignalCard.jsx", () => ({
  default: () => <div>Unsupported market verdict</div>,
}));

import DashboardShell from "./DashboardShell.jsx";

describe("DashboardShell market status", () => {
  it("keeps measured market pressure without rendering the unsupported market verdict", () => {
    render(<DashboardShell />);

    expect(screen.getByTitle("Market Pressure: 72")).toHaveTextContent("HOT 72");
    expect(screen.queryByText("Unsupported market verdict")).not.toBeInTheDocument();
  });
});
