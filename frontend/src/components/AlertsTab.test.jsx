import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SignalRow, freshnessFromStale } from "./AlertsTab";
import AnomalyStream from "./AnomalyStream.jsx";
import SmartAlertRulesPanel, { buildConditionValue } from "./SmartAlertRulesPanel.jsx";

// AlertsTab imports contexts that SignalRow doesn't use — mock so the module loads cleanly
vi.mock("../context/DataContext", () => ({ useData: () => ({}) }));
vi.mock("../context/WatchlistContext.jsx", () => ({ useWatchlist: () => ({ watchlist: [] }) }));

const NOW_MS = 1_800_000_000_000;

describe("market mood feed freshness", () => {
  it("describes literal feed age instead of calling it confidence", () => {
    expect(freshnessFromStale(1.2, 0.7)).toMatchObject({
      label: "Feed freshness: 1.2s",
      hint: "Oldest market input is 1.2s old.",
    });
  });

  it("shows unavailable when no freshness measurement exists", () => {
    expect(freshnessFromStale(null, null).label).toBe("Feed freshness unavailable");
  });
});

const base = {
  id: "test-1",
  symbol: "BTC-USD",
  type_key: "breakout",
  severity: "high",
  event_ts_ms: NOW_MS - 60_000,
};

const productionInterp = {
  summary: "Price broke out +4.8% in 3m with confirmed multi-window momentum.",
  supportingFactors: ["Large move: +4.8% in 3m", "Momentum confirmed across 1m, 1h windows"],
  cautionFactors: [],
  invalidationCondition: "Move reverses below the 3m open",
  confidence: 63,
  confidenceFactors: ["Large move: +4.8% in 3m"],
  interpretation_support_level: "production",
};

// ---------------------------------------------------------------------------
// 1. Primary text — interpretation summary replaces fallback message
// ---------------------------------------------------------------------------

describe("SignalRow – primary text", () => {
  it("uses the coin's USD spot page for Trade, even when the signal has a source URL", () => {
    render(
      <SignalRow
        a={{ ...base, symbol: "RENDER-USDC", url: "https://example.com/news" }}
        nowMs={NOW_MS}
      />,
    );
    const link = screen.getByRole("link", { name: "Open Coinbase Advanced Trade" });
    expect(link).toHaveAttribute("href", "https://www.coinbase.com/advanced-trade/spot/RENDER-USD");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("keeps an intelligence log Trade link on Coinbase when the feed supplies an alternate URL", async () => {
    render(<AnomalyStream data={{ alerts: [{ ...base, symbol: "RENDER", trade_url: "https://example.com/trade" }] }} />);
    const link = await screen.findByRole("link", { name: "RENDER" });
    expect(link).toHaveAttribute("href", "https://www.coinbase.com/advanced-trade/spot/RENDER-USD");
  });

  it("shows interpretation summary when support_level is production", () => {
    render(<SignalRow a={{ ...base, interpretation: productionInterp }} nowMs={NOW_MS} />);
    expect(screen.getByText(/Price broke out.*confirmed multi-window momentum/)).toBeInTheDocument();
  });

  it("shows interpretation summary when support_level is experimental", () => {
    const a = {
      ...base,
      message: "Old message that should not appear",
      interpretation: { ...productionInterp, interpretation_support_level: "experimental" },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText(/Price broke out.*confirmed multi-window momentum/)).toBeInTheDocument();
  });

  it("falls back to message when support_level is none", () => {
    const a = {
      ...base,
      message: "BTC moved upward sharply",
      interpretation: { summary: "should not show", confidence: null, interpretation_support_level: "none" },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.queryByText("should not show")).not.toBeInTheDocument();
    expect(screen.getByText(/moved upward sharply/)).toBeInTheDocument();
  });

  it("falls back to message when interpretation is absent", () => {
    const a = { ...base, message: "BTC breakout signal" };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText(/breakout signal/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 2. Supporting factors disclosure
// ---------------------------------------------------------------------------

describe("SignalRow – Why this read? disclosure", () => {
  it("shows disclosure trigger when supporting factors exist", () => {
    render(<SignalRow a={{ ...base, interpretation: productionInterp }} nowMs={NOW_MS} />);
    expect(screen.getByText("Why this read?")).toBeInTheDocument();
  });

  it("shows disclosure trigger when only caution factors exist", () => {
    const a = {
      ...base,
      interpretation: {
        ...productionInterp,
        supportingFactors: [],
        cautionFactors: ["Thin liquidity in window"],
      },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("Why this read?")).toBeInTheDocument();
  });

  it("does not render disclosure when no factors exist", () => {
    const a = {
      ...base,
      interpretation: {
        ...productionInterp,
        supportingFactors: [],
        cautionFactors: [],
        invalidationCondition: "",
      },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.queryByText("Why this read?")).not.toBeInTheDocument();
  });

  it("does not render disclosure when support_level is none", () => {
    const a = {
      ...base,
      interpretation: {
        ...productionInterp,
        interpretation_support_level: "none",
      },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.queryByText("Why this read?")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 3. Confidence label source — interpretation engine score takes precedence
// ---------------------------------------------------------------------------

describe("SignalRow – confidence label source", () => {
  it("uses interpretation.confidence when support_level is production", () => {
    const a = {
      ...base,
      confidence: 30,                       // root: would map to Limited
      interpretation: { ...productionInterp, confidence: 75 }, // engine: High
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("High")).toBeInTheDocument();
  });

  it("uses interpretation.confidence when support_level is experimental", () => {
    const a = {
      ...base,
      confidence: 80,                       // root: High
      interpretation: {
        ...productionInterp,
        confidence: 40,                     // engine: Limited
        interpretation_support_level: "experimental",
      },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("Limited")).toBeInTheDocument();
  });

  it("maps interpretation.confidence 70+ to High", () => {
    const a = { ...base, interpretation: { ...productionInterp, confidence: 70 } };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("High")).toBeInTheDocument();
  });

  it("maps interpretation.confidence 45–69 to Developing", () => {
    const a = { ...base, interpretation: { ...productionInterp, confidence: 50 } };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("Developing")).toBeInTheDocument();
  });

  it("maps interpretation.confidence <45 to Limited", () => {
    const a = { ...base, interpretation: { ...productionInterp, confidence: 30 } };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("Limited")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 4. Signals/event confidence is semantically distinct from interpretation
// ---------------------------------------------------------------------------

describe("SignalRow – event rows do not reuse interpretation confidence labels", () => {
  it("does not show root event confidence when support_level is none", () => {
    const a = {
      ...base,
      confidence: 80,
      interpretation: { summary: "x", confidence: null, interpretation_support_level: "none" },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.queryByText("High")).not.toBeInTheDocument();
  });

  it("does not show High solely from a Moonwalking event-state score", () => {
    const a = { ...base, primary_state: "Moonwalking", confidence: 82 };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.queryByText("High")).not.toBeInTheDocument();
    expect(screen.getByText("MOONWALKING")).toBeInTheDocument();
  });

  it("suppresses the chip on Signals rows even if interpretation is present", () => {
    const a = { ...base, interpretation: { ...productionInterp, confidence: 80 } };
    render(<SignalRow a={a} nowMs={NOW_MS} confidenceSemantics="none" />);
    expect(screen.queryByText("High")).not.toBeInTheDocument();
    expect(screen.getByText(/Price broke out/)).toBeInTheDocument();
    expect(screen.getByText("Why this read?")).toBeInTheDocument();
  });

  it("does not mutate the stored event confidence value", () => {
    const a = { ...base, primary_state: "Reversal Risk", confidence: 72 };
    render(<SignalRow a={a} nowMs={NOW_MS} confidenceSemantics="none" />);
    expect(a.confidence).toBe(72);
  });
});

// ---------------------------------------------------------------------------
// 5. the_read demotion — hidden behind disclosure when interpretation exists
// ---------------------------------------------------------------------------

describe("SignalRow – the_read demotion", () => {
  const theRead = {
    label: "Breakout Active",
    condition: "Resistance cleared",
    summary: "Price pushed above recent resistance on volume",
    tone: "favorable",
  };

  it("demotes the_read when interpretation is present (Event analysis trigger visible)", () => {
    const a = { ...base, interpretation: productionInterp, the_read: theRead };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("Event analysis")).toBeInTheDocument();
    // THE READ eyebrow is not immediately visible at top level
    expect(screen.queryByLabelText("The Read")).not.toBeInTheDocument();
  });

  it("the_read renders at top level when no interpretation", () => {
    const a = { ...base, the_read: theRead };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("THE READ")).toBeInTheDocument();
  });

  it("the_read renders at top level when support_level is none", () => {
    const a = {
      ...base,
      the_read: theRead,
      interpretation: { summary: "x", confidence: null, interpretation_support_level: "none" },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText("THE READ")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 6. Graceful degradation — missing / partial interpretation
// ---------------------------------------------------------------------------

describe("SignalRow – keyboard", () => {
  const theRead = {
    label: "Breakout Active",
    condition: "Resistance cleared",
    summary: "Price pushed above recent resistance on volume",
    tone: "favorable",
  };

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("lets Enter and Space toggle every expander without opening Coinbase", () => {
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    const a = { ...base, interpretation: productionInterp, the_read: theRead };
    render(<SignalRow a={a} nowMs={NOW_MS} />);

    for (const label of ["Why this read?", "Event analysis", "Signal details"]) {
      const summary = screen.getByText(label);
      expect(summary.tagName).toBe("SUMMARY");
      for (const key of ["Enter", " "]) {
        // fireEvent returns false when a handler called preventDefault(),
        // which is what blocked the native <details> toggle.
        expect(fireEvent.keyDown(summary, { key })).toBe(true);
      }
    }
    expect(open).not.toHaveBeenCalled();
  });

  it("still opens the trade link on Enter and Space on the row itself", () => {
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    const { container } = render(<SignalRow a={base} nowMs={NOW_MS} />);
    const row = container.querySelector(".bh-signal-row");

    expect(fireEvent.keyDown(row, { key: "Enter" })).toBe(false);
    fireEvent.keyDown(row, { key: " " });

    expect(open).toHaveBeenCalledTimes(2);
    expect(open).toHaveBeenCalledWith(
      "https://www.coinbase.com/advanced-trade/spot/BTC-USD",
      "_blank",
      "noopener,noreferrer",
    );
  });
});

describe("SignalRow – graceful degradation", () => {
  it("renders without crash when interpretation key is missing entirely", () => {
    render(<SignalRow a={base} nowMs={NOW_MS} />);
    expect(screen.getByText("BREAKOUT")).toBeInTheDocument();
  });

  it("renders without crash when interpretation.confidence is null", () => {
    const a = {
      ...base,
      interpretation: { summary: "Signal detected.", confidence: null, interpretation_support_level: "production" },
    };
    render(<SignalRow a={a} nowMs={NOW_MS} />);
    expect(screen.getByText(/Signal detected/)).toBeInTheDocument();
  });

  it("renders without crash when supportingFactors is absent from interpretation", () => {
    const a = {
      ...base,
      interpretation: { summary: "Breakout.", confidence: 60, interpretation_support_level: "production" },
    };
    expect(() => render(<SignalRow a={a} nowMs={NOW_MS} />)).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// 7. Legacy alerts — alerts without interpretation key still render correctly
// ---------------------------------------------------------------------------

describe("SignalRow – legacy alerts (pre-engine)", () => {
  it("shows message text for legacy alert with no interpretation", () => {
    const legacy = { ...base, message: "BTC surged above resistance" };
    render(<SignalRow a={legacy} nowMs={NOW_MS} />);
    expect(screen.getByText(/surged above resistance/)).toBeInTheDocument();
  });

  it("does not present root event confidence as interpretation confidence", () => {
    const legacy = { ...base, confidence: 72, message: "BTC breakout" };
    render(<SignalRow a={legacy} nowMs={NOW_MS} />);
    expect(screen.queryByText("High")).not.toBeInTheDocument();
    expect(screen.getByText("breakout")).toBeInTheDocument();
  });

  it("shows no Why this read? for legacy alert", () => {
    render(<SignalRow a={{ ...base, message: "BTC moved" }} nowMs={NOW_MS} />);
    expect(screen.queryByText("Why this read?")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Smart wake-up rules & history panel
// ---------------------------------------------------------------------------

describe("SmartAlertRulesPanel", () => {
  const seeded = {
    id: 1,
    name: "Stage 3 Industry Breakout Wake-Up",
    enabled: true,
    urgency: "wake_up",
    scope: "market",
    symbols: [],
    conditions: [{ predicate: "liquidity_rotation_stage", value: { min: 3 } }],
    match: "all",
  };

  function mockSmartAlerts({ delivery = { dispatcher: 1 }, createError } = {}) {
    let rules = [seeded];
    let history = [{ id: 9, rule_id: 1, symbol: "MARKET", urgency: "wake_up", fired_ts: 1_800_000_000, message: "Stage 3 breakout" }];
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, options = {}) => {
      const path = String(url).replace(/^https?:\/\/[^/]+/, "");
      const method = options.method || "GET";
      const body = options.body ? JSON.parse(options.body) : undefined;
      calls.push({ path, method, body });
      let payload = { status: "live" };
      const ruleMatch = path.match(/^\/api\/smart-alerts\/rules\/(\d+)$/);
      if (ruleMatch && method === "PATCH") {
        rules = rules.map((r) => (r.id === Number(ruleMatch[1]) ? { ...r, ...body } : r));
        payload.rule = rules.find((r) => r.id === Number(ruleMatch[1]));
      } else if (ruleMatch && method === "DELETE") {
        rules = rules.filter((r) => r.id !== Number(ruleMatch[1]));
        payload.deleted = Number(ruleMatch[1]);
      } else if (path === "/api/smart-alerts/rules" && method === "POST") {
        if (createError) return Promise.resolve({ ok: false, status: 409, json: async () => ({ error: createError }) });
        payload.rule = { id: 2, enabled: true, symbols: [], match: "all", ...body };
        rules = [...rules, payload.rule];
      } else if (path === "/api/smart-alerts/rules") {
        payload = { ...payload, rules, predicates: ["price_above", "stop_proximity_pct", "daily_macd_kiss"], ntfy_configured: false };
      } else if (path.startsWith("/api/smart-alerts/history")) {
        payload.history = history;
      } else if (path === "/api/smart-alerts/test") {
        payload.alert = { id: 10, rule_id: 0, symbol: "TEST", urgency: body.urgency, fired_ts: 1_800_000_100, message: "Test Alert", delivered: delivery };
        history = [payload.alert, ...history];
      }
      return Promise.resolve({ ok: true, status: method === "POST" ? 201 : 200, json: async () => payload });
    }));
    return calls;
  }

  async function openPanel() {
    const { container } = render(<SmartAlertRulesPanel />);
    const details = container.querySelector("details");
    details.open = true;
    fireEvent(details, new Event("toggle"));
    await screen.findByRole("list", { name: "Smart alert rules" });
  }

  afterEach(() => vi.unstubAllGlobals());

  it("loads nothing until opened, then lists rules and history", async () => {
    const calls = mockSmartAlerts();
    render(<SmartAlertRulesPanel />);
    expect(calls).toHaveLength(0);
    cleanup();
    await openPanel();
    const rule = screen.getByRole("listitem", { name: seeded.name });
    expect(within(rule).getByText("Wake-up")).toBeInTheDocument();
    expect(within(rule).getByText("liquidity_rotation_stage ≥ 3")).toBeInTheDocument();
    expect(screen.getByText("Stage 3 breakout")).toBeInTheDocument();
    expect(screen.getByText(/No ntfy push destination is configured/)).toBeInTheDocument();
  });

  it("toggles, deletes, creates rules and fires a test alert", async () => {
    const calls = mockSmartAlerts();
    await openPanel();

    fireEvent.click(screen.getByRole("checkbox", { name: `Enable ${seeded.name}` }));
    await waitFor(() => expect(screen.getByRole("checkbox", { name: `Enable ${seeded.name}` })).not.toBeChecked());

    const form = screen.getByRole("form", { name: "New smart alert rule" });
    const add = within(form).getByRole("button", { name: "Add rule" });
    expect(add).toBeDisabled();
    fireEvent.change(within(form).getByRole("textbox", { name: "Name" }), { target: { value: "RENDER reclaim" } });
    fireEvent.change(within(form).getByRole("combobox", { name: "Urgency" }), { target: { value: "action_queue" } });
    fireEvent.change(within(form).getByRole("combobox", { name: "Scope" }), { target: { value: "symbols" } });
    fireEvent.change(within(form).getByRole("textbox", { name: "Symbols" }), { target: { value: "render" } });
    fireEvent.change(within(form).getByRole("textbox", { name: "Value" }), { target: { value: "9.5" } });
    fireEvent.click(add);
    expect(await screen.findByRole("listitem", { name: "RENDER reclaim" })).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Test alert urgency" }), { target: { value: "action_queue" } });
    fireEvent.click(screen.getByRole("button", { name: "Send test alert" }));
    expect(await screen.findByText("Test alert sent.")).toBeInTheDocument();
    expect(screen.getByText("TEST")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: `Delete ${seeded.name}` }));
    await waitFor(() => expect(screen.queryByRole("listitem", { name: seeded.name })).not.toBeInTheDocument());

    const writes = calls.filter((c) => c.method !== "GET").map(({ path, method, body }) => ({ path, method, body }));
    expect(writes).toEqual([
      { path: "/api/smart-alerts/rules/1", method: "PATCH", body: { enabled: false } },
      {
        path: "/api/smart-alerts/rules",
        method: "POST",
        body: {
          name: "RENDER reclaim",
          urgency: "action_queue",
          scope: "symbols",
          symbols: ["RENDER"],
          conditions: [{ predicate: "price_above", value: 9.5 }],
        },
      },
      { path: "/api/smart-alerts/test", method: "POST", body: { urgency: "action_queue" } },
      { path: "/api/smart-alerts/rules/1", method: "DELETE", body: undefined },
    ]);
  });

  it("keeps the rule form available after a rejected edit and reports a failed test delivery", async () => {
    mockSmartAlerts({ delivery: { ntfy: "failed:Timeout" }, createError: "Rule name exists." });
    await openPanel();
    const form = screen.getByRole("form", { name: "New smart alert rule" });
    const name = within(form).getByRole("textbox", { name: "Name" });
    fireEvent.change(name, { target: { value: "Duplicate" } });
    fireEvent.change(within(form).getByRole("textbox", { name: "Value" }), { target: { value: "9.5" } });
    fireEvent.click(within(form).getByRole("button", { name: "Add rule" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Rule name exists.");
    expect(name).toHaveValue("Duplicate");

    fireEvent.click(screen.getByRole("button", { name: "Send test alert" }));
    expect(await screen.findByText("Test alert recorded. Delivery failed.")).toBeInTheDocument();
    expect(screen.getByText("TEST")).toBeInTheDocument();
  });

  it("explains owner-only access", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, status: 401, json: async () => ({ error: "Sign in" }) })));
    const { container } = render(<SmartAlertRulesPanel />);
    const details = container.querySelector("details");
    details.open = true;
    fireEvent(details, new Event("toggle"));
    expect(await screen.findByRole("alert")).toHaveTextContent("available to the configured portfolio owner");
  });

  it("shapes condition values for each predicate", () => {
    expect(buildConditionValue("price_above", "9.5")).toBe(9.5);
    expect(buildConditionValue("price_below", "abc")).toBeNull();
    expect(buildConditionValue("stop_proximity_pct", "3")).toEqual({ max: 3 });
    expect(buildConditionValue("liquidity_rotation_stage", "3")).toEqual({ min: 3 });
    expect(buildConditionValue("liquidity_rotation_stage", "stage_2_btc_majors_lead")).toBe("stage_2_btc_majors_lead");
    expect(buildConditionValue("daily_macd_kiss", "")).toBe(true);
    expect(buildConditionValue("fib_zone_hit", "")).toBe("rollover_target_box");
    expect(buildConditionValue("cycle_bucket", "")).toBeNull();
  });
});
