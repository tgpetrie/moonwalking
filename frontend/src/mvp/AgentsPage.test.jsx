import { StrictMode } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AgentsPage, { ago } from "./AgentsPage.jsx";

vi.mock("../config/api.js", () => ({ getBackendBase: () => "" }));

const NOW = Math.floor(Date.now() / 1000);

const summary = (agent, label, state, extra = {}) => ({
  agent,
  label,
  purpose: `${label} purpose.`,
  state,
  run_count: state === "never_run" ? 0 : 3,
  last_activity_ts: state === "never_run" ? null : NOW - 600,
  latest_run: state === "never_run" ? null : { id: 1, agent, status: state === "failed" ? "error" : "ok", error: null },
  latest_findings_by_severity: {},
  ...extra,
});

const obs = (id, agent, severity, summaryText, extra = {}) => ({
  id,
  agent,
  kind: "k",
  severity,
  symbol: null,
  summary: summaryText,
  evidence: {},
  source: {},
  created_ts: NOW - 120,
  expires_ts: null,
  ...extra,
});

function statusPayload(summaries, extra = {}) {
  return {
    status: "live",
    generated_ts: NOW,
    total_observations: 0,
    last_run: null,
    agents: [],
    agent_summaries: summaries,
    local_llm: { enabled: false },
    ...extra,
  };
}

function mockApi(status, observations = []) {
  vi.stubGlobal("fetch", vi.fn((url) => {
    const body = String(url).includes("/api/agents/status")
      ? status
      : { status: "live", observations };
    return Promise.resolve({ ok: true, status: 200, json: async () => body });
  }));
}

afterEach(() => vi.unstubAllGlobals());

const NEVER = [
  summary("data_quality", "Data Quality", "never_run"),
  summary("audit_triage", "Audit Triage", "never_run"),
];

describe("AgentsPage", () => {
  it("records explicit paper fill and close prices", async () => {
    let ticket = { id: "x", product_id: "BTC-USD", side: "buy", status: "approved_paper" };
    vi.stubGlobal("fetch", vi.fn((url, options = {}) => {
      let body;
      if (String(url).includes("/api/execution-agent/mode")) {
        body = { status: "live", mode: "autonomous" };
      } else if (String(url).includes("/api/execution-agent/tickets")) {
        if (options.method === "POST") {
          const action = JSON.parse(options.body);
          ticket = { ...ticket, status: action.action === "fill" ? "filled_paper" : "closed_paper" };
          body = { status: "live", ticket };
        } else body = { status: "live", tickets: [ticket] };
      } else body = String(url).includes("/api/agents/status") ? statusPayload(NEVER) : { status: "live", observations: [] };
      return Promise.resolve({ ok: true, status: 200, json: async () => body });
    }));
    render(<AgentsPage />);
    fireEvent.change(await screen.findByLabelText("Paper fill price"), { target: { value: "100" } });
    fireEvent.click(screen.getByRole("button", { name: "Record fill (Paper)" }));
    fireEvent.change(await screen.findByLabelText("Paper exit price"), { target: { value: "105" } });
    fireEvent.click(screen.getByRole("button", { name: "Close position (Paper)" }));
    expect(await screen.findByText(/closed_paper/)).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("/api/execution-agent/tickets", expect.objectContaining({ body: expect.stringContaining('"exit_price":105') }));
  });
  it("updates the paper mode and approves a staged paper ticket", async () => {
    vi.stubGlobal("fetch", vi.fn((url, options = {}) => {
      let body;
      if (String(url).includes("/api/execution-agent/mode")) {
        body = { status: "live", mode: options.method === "POST" ? JSON.parse(options.body).mode : "advisory" };
      } else if (String(url).includes("/api/execution-agent/tickets")) {
        const ticket = { id: "ticket-1", product_id: "BTC-USD", status: options.method === "POST" ? "approved_paper" : "staged_for_approval", entry_price: 100, stop_trigger_price: 95, stop_limit_price: 94, target_price: 115, notional_usd: 100, rr_planned: 2.5 };
        body = options.method === "POST" ? { status: "live", ticket } : { status: "live", tickets: [ticket] };
      } else {
        body = String(url).includes("/api/agents/status") ? statusPayload(NEVER) : { status: "live", observations: [] };
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => body });
    }));
    render(<AgentsPage />);
    const mode = await screen.findByRole("combobox", { name: "Execution mode" });
    fireEvent.change(mode, { target: { value: "guardian" } });
    expect(await screen.findByDisplayValue("Guardian")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Approve (Paper)" }));
    expect(await screen.findByText(/approved_paper/)).toBeInTheDocument();
    expect(screen.getByText(/No Coinbase orders are submitted/)).toBeInTheDocument();
  });
  it("says the ledger is unavailable when the backend can't be reached", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("connect ECONNREFUSED"))));
    render(<AgentsPage />);
    expect(await screen.findByText("Agent ledger unavailable")).toBeInTheDocument();
    expect(screen.getByText(/ECONNREFUSED/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("lists every known agent as never run and explains how to start one", async () => {
    mockApi(statusPayload(NEVER));
    render(<AgentsPage />);
    expect(await screen.findByText("No agent has run on this machine yet")).toBeInTheDocument();
    expect(screen.getByText("python scripts/run_local_agents.py")).toBeInTheDocument();
    const card = screen.getByRole("article", { name: "Data Quality agent" });
    expect(within(card).getByText("Never run")).toBeInTheDocument();
    expect(within(card).getByText("Hasn't run on this machine yet")).toBeInTheDocument();
  });

  it("shows each agent's state, and a failed run's error", async () => {
    mockApi(statusPayload([
      summary("data_quality", "Data Quality", "idle", { latest_findings_by_severity: { warning: 2, info: 1 } }),
      summary("portfolio_watch", "Portfolio Watch", "failed", { latest_run: { id: 2, status: "error", error: "risk board unreachable" } }),
      summary("tape_scout", "Tape Scout", "running"),
      summary("development_efficiency", "Development Efficiency", "interrupted"),
    ], { last_run: { agent: "data_quality", finished_ts: NOW - 600 } }));
    render(<AgentsPage />);

    const idle = await screen.findByRole("article", { name: "Data Quality agent" });
    expect(within(idle).getByText("Idle")).toBeInTheDocument();
    expect(within(idle).getByText("2 warning · 1 info")).toBeInTheDocument();
    const failed = screen.getByRole("article", { name: "Portfolio Watch agent" });
    expect(within(failed).getByText("Failed")).toBeInTheDocument();
    expect(within(failed).getByText("risk board unreachable")).toBeInTheDocument();
    expect(within(screen.getByRole("article", { name: "Tape Scout agent" })).getByText("Running")).toBeInTheDocument();
    expect(within(screen.getByRole("article", { name: "Development Efficiency agent" })).getByText("Interrupted")).toBeInTheDocument();
    expect(screen.queryByText("No agent has run on this machine yet")).not.toBeInTheDocument();
  });

  it("lists findings with their evidence and a link to the page they came from", async () => {
    mockApi(
      statusPayload([summary("portfolio_watch", "Portfolio Watch", "idle")]),
      [obs(1, "portfolio_watch", "critical", "ETH is in the highest protection bucket.", {
        symbol: "ETH",
        evidence: { status: "high", distance_to_stop_pct: 4.1 },
        source: { surface: "portfolio_risk_board" },
      })]
    );
    render(<AgentsPage />);
    const findings = await screen.findByRole("region", { name: "Findings" });
    expect(within(findings).getByText("ETH is in the highest protection bucket.")).toBeInTheDocument();
    expect(within(within(findings).getByRole("list")).getByText("Critical")).toBeInTheDocument();
    fireEvent.click(within(findings).getByText("Evidence"));
    expect(within(findings).getByText("distance_to_stop_pct")).toBeInTheDocument();
    expect(within(findings).getByText("4.1")).toBeInTheDocument();
    expect(within(findings).getByRole("link", { name: "Risk Board" })).toHaveAttribute("href", "/app/risk-board");
  });

  it("filters by severity and hides expired findings unless asked", async () => {
    mockApi(statusPayload([summary("data_quality", "Data Quality", "idle")]), [
      obs(1, "data_quality", "warning", "Board snapshot is stale."),
      obs(2, "data_quality", "info", "gainers_1m is empty right now."),
      obs(3, "data_quality", "watch", "Old expired note.", { expires_ts: NOW - 60 }),
    ]);
    render(<AgentsPage />);
    const findings = await screen.findByRole("region", { name: "Findings" });
    expect(within(findings).queryByText("Old expired note.")).not.toBeInTheDocument();

    fireEvent.click(within(findings).getByRole("button", { name: "Warning" }));
    expect(within(findings).getByText("Board snapshot is stale.")).toBeInTheDocument();
    expect(within(findings).queryByText("gainers_1m is empty right now.")).not.toBeInTheDocument();

    fireEvent.click(within(findings).getByRole("button", { name: "All" }));
    fireEvent.click(within(findings).getByRole("checkbox", { name: /show expired/i }));
    expect(within(findings).getByText("Old expired note.")).toBeInTheDocument();
  });

  it("groups audit findings and is explicit that they're identified, not tracked", async () => {
    mockApi(statusPayload([summary("audit_triage", "Audit Triage", "idle")]), [
      obs(1, "audit_triage", "critical", "P0: Stale quote shown as live.", { kind: "audit_problem" }),
      obs(2, "audit_triage", "watch", "Step 1: wire freshness label.", { kind: "audit_implementation_step" }),
    ]);
    render(<AgentsPage />);
    const audit = await screen.findByRole("region", { name: "Audit queue" });
    expect(within(audit).getByText("Identified, not tracked")).toBeInTheDocument();
    expect(within(audit).getByText(/Problems found/)).toBeInTheDocument();
    expect(within(audit).getByText("P0: Stale quote shown as live.")).toBeInTheDocument();
    expect(within(audit).getByText(/Implementation steps/)).toBeInTheDocument();
    // Audit items live in the queue, not duplicated in the general findings list.
    const findings = screen.getByRole("region", { name: "Findings" });
    expect(within(findings).queryByText("P0: Stale quote shown as live.")).not.toBeInTheDocument();
  });

  // React's dev double-mount once aborted the first load and the in-flight
  // guard skipped the second, so the page showed "0 agents" as if the ledger
  // were genuinely empty.
  it("still loads under StrictMode's double mount", async () => {
    mockApi(statusPayload(NEVER));
    render(<StrictMode><AgentsPage /></StrictMode>);
    expect(await screen.findByRole("article", { name: "Data Quality agent" })).toBeInTheDocument();
  });

  it("shows loading, not an empty ledger, before the first response", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(<AgentsPage />);
    expect(screen.getByText("Loading the agent ledger…")).toBeInTheDocument();
    expect(screen.queryByText("Never")).not.toBeInTheDocument();
  });

  it("offers no control that runs agents, edits code or trades", async () => {
    mockApi(statusPayload(NEVER));
    render(<AgentsPage />);
    await screen.findByText("No agent has run on this machine yet");
    expect(screen.queryByRole("button", { name: /run|fix|apply|buy|sell|trade|order/i })).not.toBeInTheDocument();
  });

  describe("Cycle Strategist deck", () => {
    const proposal = (extra = {}) => ({
      proposal_id: "0123456789abcdef",
      action: "TRIM_TO_USDC",
      symbol: "RENDER",
      side: "sell",
      status: "pending_approval",
      reference_price: 9.42,
      stop_price: null,
      trim_pct: 37.5,
      reasons: ["Inside the 0.618–0.786 rollover box"],
      execution: null,
      ...extra,
    });

    function mockDeck({ proposals = [proposal()], autonomy, reloadPlans = [] } = {}) {
      let settings = autonomy || {
        autonomy_mode: "approval_queue",
        execution_mode: "dry_run",
        emergency_pause: false,
        daily_order_cap: 3,
      };
      let rows = proposals;
      const calls = [];
      vi.stubGlobal("fetch", vi.fn((url, options = {}) => {
        const path = String(url);
        const body = options.body ? JSON.parse(options.body) : undefined;
        calls.push({ path, method: options.method || "GET", body });
        let payload;
        if (path.startsWith("/api/agents/autonomy")) {
          settings = { ...settings, ...body };
          payload = { status: "live", autonomy: settings };
        } else if (/\/api\/agents\/proposals\/[^/]+\/(approve|reject)$/.test(path)) {
          const decision = path.endsWith("approve") ? "approved" : "rejected";
          rows = rows.map((row) => ({ ...row, status: decision }));
          payload = { status: "live", proposal: rows[0], autonomy: settings };
        } else if (path.startsWith("/api/agents/proposals")) {
          payload = { status: "live", proposals: rows, reload_plans: reloadPlans, autonomy: settings };
        } else if (path.includes("/api/agents/status")) {
          payload = statusPayload(NEVER);
        } else payload = { status: "live", observations: [] };
        return Promise.resolve({ ok: true, status: 200, json: async () => payload });
      }));
      return calls;
    }

    it("lists proposals with a canonical Coinbase trade link and records approval", async () => {
      const calls = mockDeck();
      render(<AgentsPage />);
      const queue = await screen.findByRole("region", { name: "Trade proposal queue" });
      const row = await within(queue).findByRole("listitem", { name: "RENDER Trim to USDC" });
      expect(within(row).getByText("37.5%")).toBeInTheDocument();
      expect(within(row).getByText("Pending approval")).toBeInTheDocument();
      const trade = within(row).getByRole("link", { name: "Trade" });
      expect(trade).toHaveAttribute("href", "https://www.coinbase.com/advanced-trade/spot/RENDER-USD");
      expect(trade).toHaveAttribute("target", "_blank");
      expect(trade).toHaveAttribute("rel", "noopener noreferrer");

      fireEvent.click(within(row).getByRole("button", { name: "Approve" }));
      expect(await within(row).findByText("Approved")).toBeInTheDocument();
      expect(within(row).queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
      expect(calls.some((c) => c.method === "POST" && c.path === "/api/agents/proposals/0123456789abcdef/approve")).toBe(true);
    });

    it("rejects a proposal and shows guard block reasons", async () => {
      const calls = mockDeck({
        proposals: [proposal({ status: "blocked_by_guard", execution: { block_reasons: ["daily_order_cap_reached"] } })],
      });
      render(<AgentsPage />);
      const row = await screen.findByRole("listitem", { name: "RENDER Trim to USDC" });
      expect(within(row).getByText("Guard: daily order cap reached")).toBeInTheDocument();
      fireEvent.click(within(row).getByRole("button", { name: "Reject" }));
      expect(await within(row).findByText("Rejected")).toBeInTheDocument();
      expect(calls.some((c) => c.path.endsWith("/reject"))).toBe(true);
    });

    it("marks a stale floor break for reassessment with its reclaim level", async () => {
      mockDeck({
        proposals: [proposal({
          action: "PROTECTIVE_STOP",
          reference_price: 1.4,
          stop_price: 1.3,
          trim_pct: 100,
          breach_state: "stale_floor_break_reassess",
          evidence: { trigger: "stale_floor_break", reclaim_resistance: 1.76, broken_floor_price: 1.76 },
          execution: { held_reason: "stale_floor_break_reassess" },
        })],
        autonomy: { autonomy_mode: "auto_protect_exits", execution_mode: "dry_run", emergency_pause: false, daily_order_cap: 3 },
      });
      render(<AgentsPage />);
      const row = await screen.findByRole("listitem", { name: "RENDER Protective stop" });
      expect(within(row).getByText("Reassess")).toBeInTheDocument();
      expect(within(row).getByText("Reclaim").nextSibling).toHaveTextContent("1.76");
      expect(within(row).getByText("Held for approval: stale floor break reassess")).toBeInTheDocument();
      expect(within(row).getByRole("button", { name: "Approve" })).toBeInTheDocument();
    });

    it("switches autonomy mode, execution mode, pause and daily cap", async () => {
      const calls = mockDeck({ proposals: [] });
      render(<AgentsPage />);
      const deck = await screen.findByRole("region", { name: "Autonomy control deck" });
      const modeB = await within(deck).findByRole("button", { name: "Mode B · Auto-Protect Exits" });
      expect(within(deck).getByRole("button", { name: "Mode A · Approval Queue" })).toHaveAttribute("aria-pressed", "true");

      fireEvent.click(modeB);
      expect(await within(deck).findByText(/Mode B: trims and protective stops/)).toBeInTheDocument();
      expect(modeB).toHaveAttribute("aria-pressed", "true");

      fireEvent.click(within(deck).getByRole("button", { name: "Live Guarded" }));
      expect(await within(deck).findByText(/no live order route yet/)).toBeInTheDocument();

      fireEvent.click(within(deck).getByRole("checkbox", { name: /emergency pause/i }));
      expect(await within(deck).findByText("Paused")).toBeInTheDocument();

      const cap = within(deck).getByRole("spinbutton", { name: "Daily order cap" });
      const saveCap = within(deck).getByRole("button", { name: "Save cap" });
      fireEvent.change(cap, { target: { value: "25" } });
      expect(saveCap).toBeDisabled();
      fireEvent.change(cap, { target: { value: "5" } });
      fireEvent.click(saveCap);
      await within(deck).findByDisplayValue("5");

      const posts = calls.filter((c) => c.method === "POST").map((c) => c.body);
      expect(posts).toEqual([
        { autonomy_mode: "auto_protect_exits" },
        { execution_mode: "live_guarded" },
        { emergency_pause: true },
        { daily_order_cap: 5 },
      ]);
      expect(screen.getByText(/No proposals yet/)).toBeInTheDocument();
    });

    const reloadPlan = (extra = {}) => ({
      available: true,
      reference_price: 175,
      trim_quantity: 3.75,
      freed_usdc: 656.25,
      invalidation_stop: 58.8,
      fresh_cash_usd: 0,
      projected_reloaded_coins: 6.471354,
      net_coin_gain_qty: 2.721354,
      net_coin_gain_pct: 27.21,
      tranches: [
        { index: 1, weight_pct: 25, level: 120, usdc: 164.06, coins: 1.367188, basis: "log_fib_0.618" },
        { index: 2, weight_pct: 35, level: 105, usdc: 229.69, coins: 2.1875, basis: "log_fib_0.702" },
        { index: 3, weight_pct: 40, level: 90, usdc: 262.5, coins: 2.916667, basis: "daily_higher_low_floor" },
      ],
      ...extra,
    });

    const sizing = (extra = {}) => ({
      base_risk_pct: 1,
      stage_multiplier: 0.5,
      risk_budget_pct: 0.5,
      max_open_risk_pct: 5,
      open_risk_pct: 0.3,
      equity_basis: "supplied",
      heat_capped: false,
      position_capped: false,
      suggested_notional_usd: 750,
      suggested_quantity: 25,
      risk_at_stop_usd: 50,
      ...extra,
    });

    it("shows the reload plan with the extra coins a trim-and-rebuy would add", async () => {
      mockDeck({ proposals: [proposal({ symbol: "SOL", reference_price: 175, reload_plan: reloadPlan() })] });
      render(<AgentsPage />);
      const row = await screen.findByRole("listitem", { name: "SOL Trim to USDC" });
      const plan = within(row).getByRole("region", { name: "SOL reload plan" });
      expect(within(plan).getByRole("heading", { name: "Reload Plan (+27.21% Extra Coins)" })).toBeInTheDocument();
      expect(within(plan).getByText(/Trim 3.75 SOL for \$656.25 USDC, rebuy 6.4714 SOL \(\+2.7214 SOL\) with \$0.00 fresh cash\./)).toBeInTheDocument();
      const rungs = within(plan).getAllByRole("row").slice(1);
      expect(rungs).toHaveLength(3);
      expect(within(rungs[0]).getByRole("rowheader", { name: "1 · 25%" })).toBeInTheDocument();
      expect(within(rungs[0]).getByText("120")).toBeInTheDocument();
      expect(within(rungs[0]).getByText("$164.06")).toBeInTheDocument();
      expect(within(rungs[0]).getByText("0.618 log-Fib support")).toBeInTheDocument();
      expect(within(rungs[2]).getByText("Daily higher-low floor")).toBeInTheDocument();
      expect(within(plan).getByText(/Invalid below 58.8\..*fees and slippage are not included/)).toBeInTheDocument();
      // A trim has no entry size or reward-to-risk badge.
      expect(within(row).queryByText(/^R:R/)).not.toBeInTheDocument();
      expect(within(row).queryByText("Suggested Size")).not.toBeInTheDocument();
    });

    it("says when a trim has no reload ladder", async () => {
      mockDeck({ proposals: [proposal({ reload_plan: { available: false, reason: "no_support_level_between_stop_and_price" } })] });
      render(<AgentsPage />);
      const row = await screen.findByRole("listitem", { name: "RENDER Trim to USDC" });
      expect(within(row).getByText(/No reload ladder: no support level sits between/)).toBeInTheDocument();
      expect(within(row).queryByRole("region", { name: "RENDER reload plan" })).not.toBeInTheDocument();
    });

    it("shows the R:R badge, target and suggested size on an entry", async () => {
      mockDeck({
        proposals: [proposal({
          action: "BREAKOUT_ENTRY", symbol: "AVAX", side: "buy", trim_pct: null,
          reference_price: 30, stop_price: 28, target_price: 45,
          reward_to_risk_ratio: 7.5, sizing: sizing(),
        })],
      });
      render(<AgentsPage />);
      const row = await screen.findByRole("listitem", { name: "AVAX Breakout entry" });
      expect(within(row).getByText("R:R 7.50")).toBeInTheDocument();
      expect(within(row).getByText("Target").nextSibling).toHaveTextContent("45");
      expect(within(row).getByText("Suggested Size").nextSibling).toHaveTextContent("$750.00 · 25 AVAX");
      expect(within(row).getByText("Risk").nextSibling).toHaveTextContent("0.50% · $50.00 at stop · 0.5× stage");
      expect(within(row).getByRole("link", { name: "Trade" })).toHaveAttribute(
        "href", "https://www.coinbase.com/advanced-trade/spot/AVAX-USD"
      );
      expect(within(row).queryByText(/Heat cap/)).not.toBeInTheDocument();
    });

    it("explains a heat-capped size and a size that needs equity", async () => {
      mockDeck({
        proposals: [
          proposal({
            proposal_id: "aaaaaaaaaaaaaaaa", action: "BREAKOUT_ENTRY", symbol: "AVAX", side: "buy", trim_pct: null,
            reward_to_risk_ratio: 7.5,
            sizing: sizing({
              heat_capped: true, open_risk_pct: 4.8, risk_budget_pct: 0.2, suggested_notional_usd: 300,
              suggested_quantity: 10, risk_at_stop_usd: 20, equity_basis: "held_positions_mark",
            }),
          }),
          proposal({
            proposal_id: "bbbbbbbbbbbbbbbb", action: "ACCUMULATE_SUPPORT", symbol: "LINK", side: "buy", trim_pct: null,
            reward_to_risk_ratio: 2,
            sizing: sizing({ suggested_notional_usd: null, suggested_quantity: null, risk_at_stop_usd: null, equity_basis: null, note: "equity_unknown" }),
          }),
        ],
      });
      render(<AgentsPage />);
      const capped = await screen.findByRole("listitem", { name: "AVAX Breakout entry" });
      expect(within(capped).getByText(/Heat cap: open risk is 4.8% of the 5% limit, so the size is reduced\./)).toBeInTheDocument();
      expect(within(capped).getByText(/cash is not counted/)).toBeInTheDocument();
      const unsized = screen.getByRole("listitem", { name: "LINK Accumulate support" });
      expect(within(unsized).getByText("R:R 2.00")).toBeInTheDocument();
      expect(within(unsized).getByText("Suggested Size").nextSibling).toHaveTextContent("needs portfolio equity");
    });

    it("renders a reload card funded by freed USDC with a spot trade link", async () => {
      mockDeck({
        proposals: [proposal({
          action: "RELOAD_ACCUMULATE", symbol: "SOL", side: "buy", trim_pct: null,
          reference_price: 118, stop_price: 110, target_price: 175, reward_to_risk_ratio: 7.13,
          reasons: ["Price has reached 1 unfilled reload rung(s) from an earlier trim."],
          sizing: sizing({ suggested_notional_usd: 164.06, suggested_quantity: 1.39034, funded_usd: 164.06, risk_at_stop_usd: 11.12, risk_budget_pct: 0.111 }),
        })],
      });
      render(<AgentsPage />);
      const row = await screen.findByRole("listitem", { name: "SOL Reload accumulate" });
      expect(within(row).getByText("Reload accumulate")).toBeInTheDocument();
      expect(within(row).getByText("R:R 7.13")).toBeInTheDocument();
      expect(within(row).getByText("Suggested Size").nextSibling).toHaveTextContent("$164.06 · 1.3903 SOL");
      expect(within(row).getByText(/USDC funding limit \$164\.06\./)).toBeInTheDocument();
      expect(within(row).getByRole("link", { name: "Trade" })).toHaveAttribute(
        "href", "https://www.coinbase.com/advanced-trade/spot/SOL-USD"
      );
      expect(within(row).getByRole("button", { name: "Approve" })).toBeInTheDocument();
    });

    it("renders a rotation card with a trade link for each leg", async () => {
      mockDeck({
        proposals: [proposal({
          action: "ROTATE_TO_LEADER", symbol: "DOT", side: "sell", trim_pct: 25,
          reference_price: 5, stop_price: null, target_price: 1.6, reward_to_risk_ratio: 7.5,
          sizing: sizing({ suggested_notional_usd: 125, suggested_quantity: 125, funded_usd: 125, risk_at_stop_usd: 10, risk_budget_pct: 0.1 }),
          pair: {
            sell_symbol: "DOT", sell_product_id: "DOT-USD", buy_symbol: "LINK", buy_product_id: "LINK-USD",
            freed_usd: 125,
            leader: { symbol: "LINK", reference_price: 1, stop_price: 0.92, target_price: 1.6, reward_to_risk_ratio: 7.5 },
          },
        })],
      });
      render(<AgentsPage />);
      const row = await screen.findByRole("listitem", { name: "DOT Rotate to leader" });
      expect(within(row).getByText("DOT → LINK")).toBeInTheDocument();
      expect(within(row).getByText("R:R 7.50")).toBeInTheDocument();
      expect(within(row).getByText("LINK stop").nextSibling).toHaveTextContent("0.9200");
      expect(within(row).getByText("Suggested Size").nextSibling).toHaveTextContent("$125.00 · 125 LINK");
      const sell = within(row).getByRole("link", { name: "Sell DOT" });
      const buy = within(row).getByRole("link", { name: "Buy LINK" });
      expect(sell).toHaveAttribute("href", "https://www.coinbase.com/advanced-trade/spot/DOT-USD");
      expect(buy).toHaveAttribute("href", "https://www.coinbase.com/advanced-trade/spot/LINK-USD");
      for (const link of [sell, buy]) {
        expect(link).toHaveAttribute("target", "_blank");
        expect(link).toHaveAttribute("rel", "noopener noreferrer");
      }
      expect(within(row).queryByRole("link", { name: "Trade" })).not.toBeInTheDocument();
    });

    it("lists open reload ladders and marks spent rungs", async () => {
      const open = reloadPlan({
        plan_id: "0123456789abcdef", symbol: "SOL", product_id: "SOL-USD", trim_status: "approved", remaining_usdc: 492.19,
      });
      open.tranches = open.tranches.map((rung) => ({ ...rung, filled: rung.index === 1 }));
      mockDeck({ proposals: [], reloadPlans: [open] });
      render(<AgentsPage />);
      const ladders = await screen.findByRole("region", { name: "Open reload ladders" });
      const ladder = within(ladders).getByRole("listitem", { name: "SOL open reload ladder" });
      expect(within(ladder).getByText("$492.19 unspent")).toBeInTheDocument();
      expect(within(ladder).getByText("0.618 log-Fib support · spent")).toBeInTheDocument();
      expect(within(ladder).getByRole("link", { name: "Trade" })).toHaveAttribute(
        "href", "https://www.coinbase.com/advanced-trade/spot/SOL-USD"
      );
    });

    it("has no ladders panel when nothing is open, and reloads it after a trim is approved", async () => {
      const calls = mockDeck({ proposals: [proposal({ reload_plan: reloadPlan() })] });
      render(<AgentsPage />);
      const row = await screen.findByRole("listitem", { name: "RENDER Trim to USDC" });
      expect(screen.queryByRole("region", { name: "Open reload ladders" })).not.toBeInTheDocument();
      const listsBefore = calls.filter((c) => c.method === "GET" && c.path.startsWith("/api/agents/proposals")).length;
      fireEvent.click(within(row).getByRole("button", { name: "Approve" }));
      expect(await within(row).findByText("Approved")).toBeInTheDocument();
      await waitFor(() => {
        const lists = calls.filter((c) => c.method === "GET" && c.path.startsWith("/api/agents/proposals")).length;
        expect(lists).toBeGreaterThan(listsBefore);
      });
    });

    it("explains owner-only access instead of crashing", async () => {
      vi.stubGlobal("fetch", vi.fn((url) => {
        const path = String(url);
        if (path.startsWith("/api/agents/proposals")) {
          return Promise.resolve({ ok: false, status: 403, json: async () => ({ error: "Forbidden" }) });
        }
        const payload = path.includes("/api/agents/status") ? statusPayload(NEVER) : { status: "live", observations: [] };
        return Promise.resolve({ ok: true, status: 200, json: async () => payload });
      }));
      render(<AgentsPage />);
      expect(await screen.findByText("Strategist controls are available to the configured portfolio owner.")).toBeInTheDocument();
    });
  });
});

describe("ago", () => {
  it("formats relative time and handles never", () => {
    const now = 1_000_000 * 1000;
    expect(ago(null, now)).toBe("never");
    expect(ago(1_000_000 - 20, now)).toBe("just now");
    expect(ago(1_000_000 - 300, now)).toBe("5 min ago");
    expect(ago(1_000_000 - 7200, now)).toBe("2 hr ago");
    expect(ago(1_000_000 - 86400 * 3, now)).toBe("3 days ago");
  });
});
