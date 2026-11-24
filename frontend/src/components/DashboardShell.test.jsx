import { fireEvent, render, screen } from "@testing-library/react";
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
  useWatchlist: () => ({ items: [{ symbol: "RENDER" }, { symbol: "FET" }], toggle: vi.fn() }),
}));

vi.mock("../hooks/useMacroCycleScan.js", () => ({
  useMacroCycleScan: () => ({ scan: null, loading: false, error: null }),
}));

vi.mock("./IndustryPulse.jsx", () => ({
  default: ({ symbols, onInfo }) => (
    <div data-testid="industry-pulse-mount" data-symbols={symbols.join(",")} data-clickable={typeof onInfo === "function" ? "yes" : "no"} />
  ),
}));

vi.mock("./VolumeBannerScroll.jsx", () => ({ default: () => null }));
vi.mock("./TopBannerScroll.jsx", () => ({ default: () => null }));
vi.mock("./SentimentPopupAdvanced.jsx", () => ({ default: () => null }));
vi.mock("./AlertsPanelGlobal.jsx", () => ({ default: () => null }));
vi.mock("./AnomalyStream.jsx", () => ({
  default: ({ heldSymbols = [], watchSymbols = [] }) => (
    <div data-testid="anomaly-stream-mount" data-held={heldSymbols.join(",")} data-watch={watchSymbols.join(",")} />
  ),
}));
const { HELD } = vi.hoisted(() => ({ HELD: new Set(["ATOM", "LTC"]) }));
vi.mock("./alerts/useHoldingSymbols.js", () => ({ default: () => HELD }));
vi.mock("./AlertsDock.jsx", () => ({ default: () => null }));
vi.mock("./AskBhabitPanel.jsx", () => ({ default: () => null }));
vi.mock("./BoardWrapper.jsx", () => ({ default: ({ children }) => children }));
vi.mock("./GainersTable1Min.jsx", () => ({ default: () => null }));
vi.mock("./GainersTable3Min.jsx", () => ({ default: () => null }));
vi.mock("./LosersTable3Min.jsx", () => ({ default: () => null }));
vi.mock("./WatchlistPanel.jsx", () => ({ default: () => null }));
vi.mock("./LiveLeaderboard.jsx", () => ({ default: () => null }));
vi.mock("../mvp/AgentsPage.jsx", () => ({ default: () => <div>Mission Control deck</div> }));
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

describe("DashboardShell brand alignment", () => {
  it("renders the 2026 vector BHABIT lockup and moon-rabbit brand mark", () => {
    const { container } = render(<DashboardShell />);

    const hero = screen.getByRole("img", { name: "BHABIT" });
    expect(hero.getAttribute("src")).toMatch(/bhabit-header-logo.*\.svg/);
    expect(hero).toHaveClass("bh-brand-hero__logo");
    expect(hero.closest(".bh-brand-hero--compact")).not.toBeNull();

    const brand = screen.getByRole("link", { name: "BHABIT home" });
    const [mark, wordmark] = brand.querySelectorAll("img");
    expect(mark.getAttribute("src")).toMatch(/moon-rabbit-mark.*\.svg/);
    expect(wordmark.getAttribute("src")).toMatch(/bhabit-wordmark.*\.svg/);
    expect(container.querySelector('img[src*="bhabit-logo"], img[src$=".png"]')).toBeNull();
  });

  it("puts the workspace views and desk pages in one top navigation row", () => {
    render(<DashboardShell />);

    const header = screen.getByRole("banner");
    const views = screen.getByRole("navigation", { name: "Workspace views" });
    const desk = screen.getByRole("navigation", { name: "Desk pages" });
    expect(header).toContainElement(views);
    expect(header).toContainElement(desk);
    expect(views).toHaveClass("bh-utabs");
    expect(desk).toHaveClass("bh-utabs");
    expect(views.parentElement).toBe(desk.parentElement);
    expect(views.nextElementSibling).toHaveClass("bh-topnav__divider");

    expect(Array.from(views.querySelectorAll("button"), (b) => b.textContent)).toEqual([
      "Live Tape",
      "Cycle Atlas & Pulse",
      "Mission Control",
    ]);
    expect(screen.getByRole("button", { name: "Live Tape" })).toHaveAttribute("aria-pressed", "true");
    expect(Array.from(desk.querySelectorAll("a"), (a) => [a.textContent, a.getAttribute("href")])).toEqual([
      ["Watchlists", "/app/watchlists"],
      ["Portfolio", "/app/portfolio"],
      ["Scorecard", "/app/scorecard"],
    ]);
    expect(document.querySelector(".board-core .bh-workspace-tabs")).toBeNull();
  });

  it("labels the assistant ASK BHABIT", async () => {
    const { default: AskBhabitPanel } = await vi.importActual("./AskBhabitPanel.jsx");
    render(<AskBhabitPanel />);

    expect(screen.getByText("ASK BHABIT")).toBeInTheDocument();
    expect(screen.queryByText(/codex/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByTitle("Ask Bhabit"));
    expect(screen.getByRole("dialog", { name: "Ask Bhabit" })).toBeInTheDocument();
  });
});

describe("DashboardShell industry pulse", () => {
  it("mounts the cycle scanner on the board with the watchlist symbols and a coin opener", () => {
    render(<DashboardShell />);

    expect(screen.queryByTestId("industry-pulse-mount")).not.toBeInTheDocument();
    expect(screen.getByText("IGNITION (1M)")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cycle Atlas & Pulse" }));
    const pulse = screen.getByTestId("industry-pulse-mount");
    expect(pulse).toHaveAttribute("data-symbols", "RENDER,FET");
    expect(pulse).toHaveAttribute("data-clickable", "yes");
    expect(pulse.closest(".bh-rail-stack")).not.toBeNull();
    expect(screen.queryByText("IGNITION (1M)")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Mission Control" }));
    expect(screen.getByText("Mission Control deck")).toBeInTheDocument();
    expect(screen.queryByTestId("industry-pulse-mount")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Live Tape" }));
    expect(screen.getByText("IGNITION (1M)")).toBeInTheDocument();
  });

  it("feeds Coinbase holdings and the watchlist into the intelligence log", () => {
    render(<DashboardShell />);

    fireEvent.click(screen.getByRole("button", { name: "Cycle Atlas & Pulse" }));
    const stream = screen.getByTestId("anomaly-stream-mount");
    expect(stream).toHaveAttribute("data-held", "ATOM,LTC");
    expect(stream).toHaveAttribute("data-watch", "RENDER,FET");
  });
});
