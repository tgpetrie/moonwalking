import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ScorecardRedesignPage, {
  evidenceOf,
  humanizeLabel,
  resolveSource,
} from "./ScorecardRedesignPage";

vi.mock("../config/api.js", () => ({ getBackendBase: () => "" }));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const SETUP_DEEP = {
  state: "Escalating",
  direction: "up",
  label: "STRONG_BUY",
  sample_size: 200,
  win_rate: 0.62,
  recent_win_rate: 0.58,
  recent_sample: 50,
  median_favorable_pct: 2.6,
  median_adverse_pct: -1.0,
  median_return: { "5m": 0.6, "15m": 0.9, "30m": 1.3, "60m": 1.9 },
};

const SETUP_THIN = {
  ...SETUP_DEEP,
  state: "Building",
  label: "WATCH",
  sample_size: 15,
  win_rate: 0.18,
  recent_win_rate: 0.14,
};

// A bearish category rendered alongside the bullish one — the pairing that used
// to read as two contradictory live calls.
const SETUP_CAUTION = {
  ...SETUP_DEEP,
  state: "Reversal Risk",
  direction: "down",
  label: "CAUTION",
  sample_size: 120,
  win_rate: 0.18,
  recent_win_rate: 0.14,
};

const BOARD_READY = {
  board: "ignition_1m",
  status: "measured",
  read: "No clear edge",
  sample_size: 150,
  matched_sample_size: 130,
  continuation_rate: 0.18,
  reversal_rate: 0.2,
  continuation_ci95: [0.12, 0.24],
  continuation_lift_vs_control: -0.02,
  median_directional_return: { "5m": -0.1, "15m": -0.2, "30m": 0.1, "60m": 0.3 },
};

const BOARD_LEARNING = {
  ...BOARD_READY,
  board: "confirmation_3m_up",
  status: "learning",
  sample_size: 45,
  continuation_rate: 0.44,
  continuation_lift_vs_control: 0.08,
};

function makeResponse(overrides = {}) {
  return {
    status: "live",
    signals: {
      total_graded: 1500,
      overall_win_rate: 0.21,
      target_pct: 2.0,
      adverse_pct: 1.0,
      horizon_minutes: 60,
      signal_types: [SETUP_DEEP],
      ...overrides.signals,
    },
    boards: {
      total_entries: 300,
      boards: { ignition_1m: BOARD_READY },
      ...overrides.boards,
    },
  };
}

function routeFetch({ scorecard, coin, progress, coinOk = true }) {
  global.fetch = vi.fn(async (url) => {
    const href = String(url);
    if (href.includes("/api/signals/outcomes/status")) {
      return {
        ok: Boolean(progress),
        status: progress ? 200 : 404,
        json: vi.fn().mockResolvedValue(progress || {}),
      };
    }
    if (href.includes("/api/coin-history/")) {
      return {
        ok: coinOk,
        status: coinOk ? 200 : 500,
        json: vi.fn().mockResolvedValue(coin || {}),
      };
    }
    return { ok: true, status: 200, json: vi.fn().mockResolvedValue(scorecard) };
  });
}

function mockFetch(payload) {
  routeFetch({ scorecard: payload });
}

async function renderLoaded(payload = makeResponse(), props = {}) {
  mockFetch(payload);
  const utils = render(<ScorecardRedesignPage {...props} />);
  await waitFor(() => expect(utils.container.querySelector(".scr-hero")).toBeTruthy());
  return utils;
}

/** The signals zone, which is the one carrying the chart controls. */
function signalsZone(container) {
  return container.querySelector('.scr-zone[data-tone="signals"]');
}

// ---------------------------------------------------------------------------
// Pure adapters
// ---------------------------------------------------------------------------

describe("evidenceOf", () => {
  it("maps sample sizes to plain-English depth labels", () => {
    expect(evidenceOf(200).label).toBe("Deep evidence");
    expect(evidenceOf(45).label).toBe("Solid evidence");
    expect(evidenceOf(15).label).toBe("Thin evidence");
    expect(evidenceOf(3).label).toBe("Barely tested");
    expect(evidenceOf(0).label).toBeNull();
  });

  it("never reuses the words that name a setup state", () => {
    for (const n of [1, 10, 30, 100]) {
      expect(evidenceOf(n).label).not.toContain("Building");
      expect(evidenceOf(n).label).not.toContain("Strong");
    }
  });

  it("carries a trust sentence for every tier", () => {
    for (const n of [0, 3, 15, 45, 200]) {
      expect(typeof evidenceOf(n).trust).toBe("string");
      expect(evidenceOf(n).trust.length).toBeGreaterThan(0);
    }
  });
});

describe("humanizeLabel", () => {
  it("uses the friendly name when there is one", () => {
    expect(humanizeLabel("STRONG_BUY")).toBe("Strong Buy");
    expect(humanizeLabel("CAUTION")).toBe("Caution");
  });

  // These are the labels the live backend actually returns.
  it("stops unmapped internal constants from shouting", () => {
    expect(humanizeLabel("BREAKDOWN CONFIRMED")).toBe("Breakdown confirmed");
    expect(humanizeLabel("MIXED — NO CLEAR EDGE")).toBe("Mixed — no clear edge");
    expect(humanizeLabel("EARLY — WATCH FOR CONFIRMATION")).toBe(
      "Early — watch for confirmation"
    );
    expect(humanizeLabel("QUIET_FLOW_BUILDING")).toBe("Quiet flow building");
  });

  it("leaves text that was already written for a human alone", () => {
    expect(humanizeLabel("Reversal risk rising")).toBe("Reversal risk rising");
  });

  it("never renders an empty name", () => {
    expect(humanizeLabel("")).toBe("Unnamed setup");
    expect(humanizeLabel(null)).toBe("Unnamed setup");
    expect(humanizeLabel(undefined)).toBe("Unnamed setup");
  });
});

describe("resolveSource", () => {
  it("keeps preview, demo, and live distinct", () => {
    expect(resolveSource(true, "live").chip).toBe("Preview data");
    expect(resolveSource(false, "demo").chip).toBe("Demo data");
    expect(resolveSource(false, "live").chip).toBe("Live data");
  });

  it("gives every state its own headline and explanation", () => {
    const chips = new Set();
    const headlines = new Set();
    for (const source of [
      resolveSource(true, "live"),
      resolveSource(false, "demo"),
      resolveSource(false, "live"),
    ]) {
      chips.add(source.chip);
      headlines.add(source.headline);
      expect(source.note.length).toBeGreaterThan(20);
    }
    expect(chips.size).toBe(3);
    expect(headlines.size).toBe(3);
  });
});

// ---------------------------------------------------------------------------
// Loading and error states
// ---------------------------------------------------------------------------

describe("ScorecardRedesignPage – loading and error states", () => {
  it("shows plain loading text while the fetch is pending", () => {
    global.fetch = vi.fn(() => new Promise(() => {}));
    render(<ScorecardRedesignPage />);
    expect(screen.getByText(/Loading the track record/i)).toBeInTheDocument();
  });

  it("shows a plain error message when the fetch fails", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network failure"));
    render(<ScorecardRedesignPage />);
    await waitFor(() =>
      expect(screen.getByText(/Couldn't load the scorecard/i)).toBeInTheDocument()
    );
  });

  it("falls back to a sample in preview mode instead of erroring", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("offline"));
    const { container } = render(<ScorecardRedesignPage previewMode />);
    await waitFor(() =>
      expect(container.querySelector(".scr-hero__source").textContent).toBe("Preview data")
    );
    expect(screen.queryByText(/Couldn't load the scorecard/i)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Data provenance
// ---------------------------------------------------------------------------

describe("ScorecardRedesignPage – data labeling", () => {
  // The chip carries the label; the full explanation is a tooltip so it costs
  // no vertical space at the top of the page.
  it("labels live data on the chip, with the detail as a tooltip", async () => {
    const { container } = await renderLoaded();
    const chip = container.querySelector(".scr-hero__source");
    expect(chip.textContent).toBe("Live data");
    expect(chip.dataset.source).toBe("live");
    expect(chip.getAttribute("title")).toMatch(/measured from real recorded outcomes/i);
  });

  it("labels demo data returned by the server", async () => {
    const { container } = await renderLoaded({ ...makeResponse(), status: "demo" });
    const chip = container.querySelector(".scr-hero__source");
    expect(chip.textContent).toBe("Demo data");
    expect(chip.getAttribute("title")).toMatch(/Do not read anything into these results/i);
  });

  // A preview page that quietly swapped in an empty live payload would be
  // labelled "preview" while showing live numbers.
  it("keeps the sample, and the preview label, when live data is empty", async () => {
    mockFetch({
      status: "live",
      signals: { total_graded: 0, overall_win_rate: null, signal_types: [] },
      boards: { total_entries: 0, boards: {} },
    });
    const { container } = render(<ScorecardRedesignPage previewMode />);
    await waitFor(() => expect(container.querySelector(".scr-hero")).toBeTruthy());
    expect(container.querySelector(".scr-hero__source").textContent).toBe("Preview data");
  });

  it("switches to the live label once real outcomes exist", async () => {
    const { container } = await renderLoaded(makeResponse(), { previewMode: true });
    await waitFor(() =>
      expect(container.querySelector(".scr-hero__source").textContent).toBe("Live data")
    );
  });

  // A chip alone is easy to miss. Numbers that were never measured get a
  // banner too; measured numbers do not, so the banner stays meaningful.
  it("banners anything that is not measured from real outcomes", async () => {
    const { container } = await renderLoaded({ ...makeResponse(), status: "demo" });
    const banner = container.querySelector(".scr-provenance");
    expect(banner.dataset.source).toBe("demo");
    expect(within(banner).getByText("You are viewing demo data.")).toBeInTheDocument();
    expect(banner.textContent).toMatch(/Do not read anything into these results/i);
  });

  it("does not banner live data", async () => {
    const { container } = await renderLoaded();
    expect(container.querySelector(".scr-provenance")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Hero
// ---------------------------------------------------------------------------

describe("ScorecardRedesignPage – hero", () => {
  it("makes the coin itself the page heading instead of restating it in prose", async () => {
    const { container } = await renderLoaded();
    const coin = container.querySelector(".scr-hero__coin");
    expect(coin.textContent).toBe("BTC");
    expect(coin.tagName).toBe("H2");
    expect(screen.queryByText(/Track record for/i)).not.toBeInTheDocument();
  });

  it("puts the numbers straight under the coin, with no prose in between", async () => {
    const { container } = await renderLoaded();
    const hero = container.querySelector(".scr-hero");
    expect([...hero.children].map((el) => el.className)).toEqual([
      "scr-hero__bar",
      "scr-headline",
      "scr-scoring",
    ]);
    expect(hero.querySelectorAll(":scope > p").length).toBe(0);
  });

  it("shows the three headline metrics", async () => {
    await renderLoaded();
    expect(screen.getByText("Signals that worked")).toBeInTheDocument();
    expect(screen.getByText("21.0%")).toBeInTheDocument();
    expect(screen.getByText("Most dependable category")).toBeInTheDocument();
    expect(screen.getByText("Boards with enough history")).toBeInTheDocument();
  });

  it("folds the scoring rule away instead of spending hero space on it", async () => {
    const { container } = await renderLoaded();
    const scoring = container.querySelector(".scr-scoring");
    expect(scoring.open).toBe(false);

    fireEvent.click(scoring.querySelector("summary"));
    await waitFor(() => expect(scoring.open).toBe(true));

    const rule = container.querySelector(".scr-hero__rule").textContent;
    expect(rule).toMatch(/counts as working/i);
    expect(rule).toMatch(/\+2%/);
    expect(rule).toMatch(/-1%/);
    expect(rule).toMatch(/60 minutes/);
  });

  it("keeps the coin picker compact and inline with the coin", async () => {
    const { container } = await renderLoaded();
    expect(container.querySelector(".scr-hero__bar .scr-coinpicker")).toBeTruthy();
    // Label is present for screen readers but not taking up a visible row.
    expect(screen.getByLabelText("Change coin")).toBeInTheDocument();
    expect(container.querySelector(".scr-coinpicker label").className).toBe("scr-vh");
  });
});

// ---------------------------------------------------------------------------
// Zones
// ---------------------------------------------------------------------------

describe("ScorecardRedesignPage – zone separation", () => {
  it("separates the four kinds of information into labeled zones", async () => {
    const { container } = await renderLoaded();
    const tones = [...container.querySelectorAll(".scr-zone")].map((z) => z.dataset.tone);
    expect(tones).toEqual(["signals", "boards", "coin", "diagnostics"]);
  });

  it("gives each zone a single short heading", async () => {
    const { container } = await renderLoaded();
    expect(
      [...container.querySelectorAll(".scr-zone__title")].map((el) => el.textContent)
    ).toEqual(["Signal history", "Board history", "BTC history", "Internal diagnostics"]);
    for (const zone of container.querySelectorAll(".scr-zone")) {
      expect(zone.querySelector(".scr-zone__head").children.length).toBe(2);
    }
  });

  // Full-height coloured rails made every zone shout; the marker carries it now.
  it("carries zone colour on the step marker, not a full-height rail", async () => {
    const { container } = await renderLoaded();
    for (const zone of container.querySelectorAll(".scr-zone")) {
      expect(zone.querySelector(".scr-zone__step")).toBeTruthy();
    }
  });

  it("opens every zone with what it measures and what to do with it", async () => {
    const { container } = await renderLoaded();
    const ledes = [...container.querySelectorAll(".scr-zone__lede")];
    expect(ledes.length).toBe(4);
    for (const lede of ledes) {
      expect(lede.textContent.length).toBeGreaterThan(60);
      // The lede belongs to the body, not the heading row, so the heading
      // stays a single short line.
      expect(lede.closest(".scr-zone__head")).toBeNull();
    }
  });

  // Two categories that sound like opposite advice appear in one list. The
  // page has to say outright that they are not simultaneous recommendations.
  it("says the signal categories are past buckets, not advice given at once", async () => {
    const { container } = await renderLoaded();
    const note = signalsZone(container).querySelector(".scr-scope-note");
    expect(note).toBeTruthy();
    expect(note.textContent).toMatch(/not advice being given right now/i);
    expect(note.textContent).toMatch(/does not mean BHABIT is telling you to buy and sell at once/i);
    expect(note.textContent).toMatch(/live board/i);
  });

  // Naming a pair that is not on screen would be its own small confusion.
  it("names two categories actually on screen as the example", async () => {
    const { container } = await renderLoaded(
      makeResponse({ signals: { signal_types: [SETUP_DEEP, SETUP_CAUTION] } })
    );
    const note = signalsZone(container).querySelector(".scr-scope-note");
    expect(within(note).getByText("Strong Buy")).toBeInTheDocument();
    expect(within(note).getByText("Caution")).toBeInTheDocument();
  });

  it("falls back to generic wording when the data has only one direction", async () => {
    const { container } = await renderLoaded();
    const note = signalsZone(container).querySelector(".scr-scope-note");
    expect(note.textContent).toMatch(/two rows that sound like opposite advice/i);
  });

  it("keeps internal diagnostics collapsed", async () => {
    const { container } = await renderLoaded();
    const zone = container.querySelector('.scr-zone[data-tone="diagnostics"]');
    expect(within(zone).getByText("Internal diagnostics")).toBeInTheDocument();
    expect(zone.querySelector("details").open).toBe(false);
  });

  it("carries no page-level explainer furniture", async () => {
    const { container } = await renderLoaded();
    expect(container.querySelector(".scr-hierarchy")).toBeNull();
    expect(screen.queryByText(/Why are there three kinds of cards/i)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Chart treatments
// ---------------------------------------------------------------------------

describe("ScorecardRedesignPage – chart treatments", () => {
  // Bars are the default: the question is "was it right?", which is a rate,
  // and rates across categories do not sum to 100%.
  it("defaults to bars, not the volume pie", async () => {
    const { container } = await renderLoaded();
    expect(container.querySelector(".scr-chartswitch__btn.is-active").textContent).toBe("Bars");
    expect(signalsZone(container).querySelector(".scr-barrow")).toBeTruthy();
    expect(signalsZone(container).querySelector(".scr-pie")).toBeNull();
  });

  it("offers bars and gauges as alternatives", async () => {
    const { container } = await renderLoaded();
    expect(
      [...container.querySelectorAll(".scr-chartswitch__btn")].map((b) => b.textContent)
    ).toEqual(["Bars", "Volume mix", "Gauges"]);

    fireEvent.click(screen.getByRole("button", { name: "Volume mix" }));
    await waitFor(() => expect(signalsZone(container).querySelector(".scr-pie")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Gauges" }));
    await waitFor(() => expect(signalsZone(container).querySelector(".scr-donut")).toBeTruthy());
  });

  it("draws one coloured section per category, sized by share of calls", async () => {
    const { container } = await renderLoaded(
      makeResponse({ signals: { signal_types: [SETUP_DEEP, SETUP_CAUTION, SETUP_THIN] } })
    );
    fireEvent.click(screen.getByRole("button", { name: "Volume mix" }));
    const zone = signalsZone(container);
    await waitFor(() => expect(zone.querySelectorAll(".scr-pie__slice").length).toBe(3));

    // Each section gets its own fill, and the legend lists one row per section.
    const fills = [...zone.querySelectorAll(".scr-pie__slice")].map((s) => s.getAttribute("fill"));
    expect(new Set(fills).size).toBe(3);
    expect(zone.querySelectorAll(".scr-legend__item").length).toBe(3);

    // Legend headline is the slice share, so chart and legend always agree.
    const shares = [...zone.querySelectorAll(".scr-legend__pct")].map((el) =>
      parseInt(el.textContent, 10)
    );
    expect(shares.reduce((a, b) => a + b, 0)).toBeGreaterThan(95);
    for (const el of zone.querySelectorAll(".scr-legend__pct-label")) {
      expect(el.textContent).toBe("of calls");
    }
  });

  it("blows up the selected section and shows its detail alongside", async () => {
    const { container } = await renderLoaded(
      makeResponse({ signals: { signal_types: [SETUP_DEEP, SETUP_CAUTION] } })
    );
    fireEvent.click(screen.getByRole("button", { name: "Volume mix" }));
    const zone = signalsZone(container);
    await waitFor(() => expect(zone.querySelector(".scr-legend__row")).toBeTruthy());
    expect(zone.querySelector(".scr-legend__detail")).toBeNull();

    fireEvent.click(zone.querySelectorAll(".scr-legend__row")[0]);

    await waitFor(() => expect(zone.querySelector(".scr-legend__detail")).toBeTruthy());
    const detail = zone.querySelector(".scr-legend__detail");
    expect(within(detail).getByText("What this is")).toBeInTheDocument();
    expect(within(detail).getByText("How it compares")).toBeInTheDocument();
    expect(within(detail).getByText("What to do with it")).toBeInTheDocument();

    // The chosen section lifts out of the ring.
    expect(zone.querySelector(".scr-pie__slice.is-selected")).toBeTruthy();
  });

  // An empty chart implies we measured and found nothing. Collection still
  // running is a different fact and gets a different display.
  it("shows collection progress rather than an empty chart", async () => {
    routeFetch({
      scorecard: makeResponse({ signals: { total_graded: 0, signal_types: [] } }),
      progress: { total: 17, complete: 0, collecting: 17, horizon_minutes: 60 },
    });
    const { container } = render(<ScorecardRedesignPage />);
    await waitFor(() => expect(container.querySelector(".scr-collecting")).toBeTruthy());

    const panel = container.querySelector(".scr-collecting");
    expect(within(panel).getByText("Still collecting")).toBeInTheDocument();
    expect(within(panel).getByText("0 of 17 graded")).toBeInTheDocument();
    expect(panel.textContent).toMatch(/graded 60 minutes after it fires/i);
  });

  it("falls back to a plain message when nothing has been recorded at all", async () => {
    const { container } = await renderLoaded(
      makeResponse({
        signals: { total_graded: 0, signal_types: [] },
        boards: { total_entries: 0, boards: {} },
      })
    );
    expect(within(signalsZone(container)).getByText(/No signals have been recorded yet/i))
      .toBeInTheDocument();
  });

  it("marks the average on the bar chart so a score can be judged against it", async () => {
    const { container } = await renderLoaded();
    await waitFor(() =>
      expect(signalsZone(container).querySelector(".scr-bars__avg")).toBeTruthy()
    );
    expect(signalsZone(container).querySelector(".scr-bars__avg-label").textContent).toMatch(
      /21%/
    );
  });

  // A live payload carries twenty-odd categories. Showing every one at once is
  // the wall of data the redesign exists to replace.
  it("folds away the long tail of categories, and can show it on request", async () => {
    const many = Array.from({ length: 14 }, (_, i) => ({
      ...SETUP_DEEP,
      label: `SETUP ${i}`,
      sample_size: 200 - i,
    }));
    const { container } = await renderLoaded(makeResponse({ signals: { signal_types: many } }));
    const rows = () => signalsZone(container).querySelectorAll(".scr-barrow");

    expect(rows().length).toBe(8);
    const more = within(signalsZone(container)).getByRole("button", {
      name: /Show all 14 categories/i,
    });
    expect(more.textContent).toMatch(/6 more/);

    fireEvent.click(more);
    await waitFor(() => expect(rows().length).toBe(14));

    fireEvent.click(
      within(signalsZone(container)).getByRole("button", { name: /Show the top 8 only/i })
    );
    await waitFor(() => expect(rows().length).toBe(8));
  });

  it("leaves a short list alone", async () => {
    const { container } = await renderLoaded(
      makeResponse({ signals: { signal_types: [SETUP_DEEP, SETUP_CAUTION] } })
    );
    expect(signalsZone(container).querySelector(".scr-bars__more")).toBeNull();
  });

  // A board chart has no meaningful average to compare against, and
  // `Number(null)` is 0 — so a missing baseline used to draw "avg 0%".
  it("omits the average marker when there is no baseline to draw", async () => {
    const { container } = await renderLoaded();
    const boardsZone = container.querySelector('.scr-zone[data-tone="boards"]');
    expect(boardsZone.querySelector(".scr-barrow")).toBeTruthy();
    expect(boardsZone.querySelector(".scr-bars__avg")).toBeNull();
  });

  it("reorders categories from a single control", async () => {
    const { container } = await renderLoaded(
      makeResponse({ signals: { signal_types: [SETUP_THIN, SETUP_DEEP] } })
    );
    const names = () =>
      [...signalsZone(container).querySelectorAll(".scr-barrow__name")].map((el) => el.textContent);

    expect(names()[0]).toBe("Strong Buy");
    fireEvent.change(screen.getByLabelText("Order by"), { target: { value: "tested" } });
    await waitFor(() => expect(names()[0]).toBe("Strong Buy"));
    expect(container.querySelectorAll(".scr-order__select").length).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// Historical framing — never a live call
// ---------------------------------------------------------------------------

describe("ScorecardRedesignPage – historical framing", () => {
  it("states direction in the past tense", async () => {
    const { container } = await renderLoaded();
    fireEvent.click(screen.getByRole("button", { name: "Gauges" }));
    await waitFor(() => expect(container.querySelector(".scr-tile")).toBeTruthy());

    const tile = container.querySelector(".scr-tile");
    expect(tile.textContent).toMatch(/Predicted a rise/);
    expect(tile.textContent).not.toMatch(/Expects a/);
  });

  it("scores each category against the average inside its detail", async () => {
    const { container } = await renderLoaded();
    const zone = signalsZone(container);
    fireEvent.click(zone.querySelector(".scr-barrow"));
    await waitFor(() => expect(zone.querySelector(".scr-groupdetail")).toBeTruthy());
    expect(
      within(zone.querySelector(".scr-groupdetail")).getByText(
        /Well ahead of the average signal/i
      )
    ).toBeInTheDocument();
  });

  it("labels the board readiness in plain words", async () => {
    const { container } = await renderLoaded(
      makeResponse({
        boards: { boards: { ignition_1m: BOARD_READY, confirmation_3m_up: BOARD_LEARNING } },
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Gauges" }));
    await waitFor(() =>
      expect(container.querySelectorAll('.scr-zone[data-tone="boards"] .scr-tile').length).toBe(2)
    );

    const chips = [
      ...container.querySelectorAll('.scr-zone[data-tone="boards"] .scr-status'),
    ].map((el) => el.textContent);
    expect(chips).toContain("Enough history");
    expect(chips).toContain("Still learning");
    expect(chips).not.toContain("measured");
  });

  it("spells out the edge against similar coins in the board detail", async () => {
    const { container } = await renderLoaded();
    const zone = container.querySelector('.scr-zone[data-tone="boards"]');
    fireEvent.click(zone.querySelector(".scr-barrow"));
    await waitFor(() => expect(zone.querySelector(".scr-groupdetail")).toBeTruthy());
    expect(zone.textContent).toMatch(/changed the odds by -2%/i);
  });
});

// ---------------------------------------------------------------------------
// Coin drilldown
// ---------------------------------------------------------------------------

describe("ScorecardRedesignPage – coin drilldown", () => {
  // The hero names a coin from the first paint. Asking the user to pick the
  // coin already named on screen is the wrong opening move.
  it("loads the default coin's history on arrival", async () => {
    routeFetch({
      scorecard: makeResponse(),
      coin: {
        status: "live",
        product_id: "BTC-USD",
        total_outcomes: 64,
        target_pct: 2.0,
        adverse_pct: 1.0,
        horizon_minutes: 60,
        signal_types: [SETUP_DEEP],
      },
    });

    render(<ScorecardRedesignPage />);
    await waitFor(() =>
      expect(
        screen.getByText(
          "64 measured signals — the most common setup worked 62% of the time."
        )
      ).toBeInTheDocument()
    );
    expect(screen.queryByText(/Pick a coin at the top of the page/i)).not.toBeInTheDocument();

    const calls = global.fetch.mock.calls.map((call) => String(call[0]));
    expect(calls.some((href) => href.includes("/api/coin-history/BTC"))).toBe(true);
  });

  // The user did not ask for that lookup, so its failure must not shout.
  it("stays quiet when the automatic lookup fails", async () => {
    routeFetch({ scorecard: makeResponse(), coinOk: false });
    const { container } = render(<ScorecardRedesignPage />);

    await waitFor(() => expect(container.querySelector(".scr-hero")).toBeTruthy());
    await waitFor(() =>
      expect(screen.getByText(/Pick a coin at the top of the page/i)).toBeInTheDocument()
    );
    expect(screen.queryByText(/Couldn't load BTC/i)).not.toBeInTheDocument();
  });

  it("loads a coin from the hero picker and refocuses the page on it", async () => {
    routeFetch({
      scorecard: makeResponse(),
      coin: {
        status: "live",
        product_id: "ETH-USD",
        total_outcomes: 32,
        target_pct: 2.0,
        adverse_pct: 1.0,
        horizon_minutes: 60,
        signal_types: [{ ...SETUP_DEEP, label: "BUY_WATCH", sample_size: 32, win_rate: 0.5625 }],
      },
    });

    const { container } = render(<ScorecardRedesignPage />);
    await waitFor(() => expect(screen.getByLabelText("Change coin")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Change coin"), { target: { value: "eth" } });
    fireEvent.click(screen.getByRole("button", { name: "Show" }));

    await waitFor(() => expect(container.querySelector(".scr-hero__coin").textContent).toBe("ETH"));
    expect(screen.getByText("ETH history")).toBeInTheDocument();
    expect(
      screen.getByText("32 measured signals — the most common setup worked 56% of the time.")
    ).toBeInTheDocument();
  });

  it("explains a thin coin sample instead of quoting a rate", async () => {
    routeFetch({
      scorecard: makeResponse(),
      coin: {
        status: "live",
        product_id: "SOL-USD",
        total_outcomes: 12,
        target_pct: 2.0,
        adverse_pct: 1.0,
        horizon_minutes: 60,
        signal_types: [],
      },
    });

    render(<ScorecardRedesignPage />);
    await waitFor(() => expect(screen.getByLabelText("Change coin")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Change coin"), { target: { value: "SOL" } });
    fireEvent.click(screen.getByRole("button", { name: "Show" }));

    await waitFor(() =>
      expect(
        screen.getByText("Only 12 measured signals so far — too few to put a number on.")
      ).toBeInTheDocument()
    );
  });

  it("surfaces a coin lookup failure without breaking the page", async () => {
    routeFetch({ scorecard: makeResponse(), coinOk: false });

    const { container } = render(<ScorecardRedesignPage />);
    await waitFor(() => expect(screen.getByLabelText("Change coin")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Show" }));

    await waitFor(() => expect(screen.getByText(/Couldn't load BTC/i)).toBeInTheDocument());
    expect(signalsZone(container).querySelector(".scr-barrow")).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Power-user details
// ---------------------------------------------------------------------------

describe("ScorecardRedesignPage – power-user details", () => {
  it("keeps the grouped rollups and scoring parameters collapsed by default", async () => {
    await renderLoaded(makeResponse({ signals: { signal_types: [SETUP_DEEP, SETUP_THIN] } }));
    const advanced = screen.getByText(/Show internal diagnostics/i).closest("details");
    expect(advanced.open).toBe(false);

    fireEvent.click(advanced.querySelector("summary"));
    await waitFor(() => expect(advanced.open).toBe(true));

    expect(within(advanced).getByText("How outcomes are scored")).toBeInTheDocument();
    expect(within(advanced).getByText("Setups grouped by stage")).toBeInTheDocument();
    expect(within(advanced).getByText("Boards grouped by readiness")).toBeInTheDocument();
  });
});
