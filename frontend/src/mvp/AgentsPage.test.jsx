import { StrictMode } from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
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
