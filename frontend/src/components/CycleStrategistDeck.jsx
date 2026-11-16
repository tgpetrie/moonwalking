import { useCallback, useEffect, useState } from "react";
import {
  approveAgentProposal,
  fetchAgentProposals,
  rejectAgentProposal,
  updateAgentAutonomy,
} from "../api.js";
import { getCoinbaseAdvancedSpotUrl } from "../utils/coinbaseUrl.js";

// Cycle Strategist control deck. Everything here is dry-run: approving a
// proposal records the decision only, and Mode B simulates exits.

const AUTONOMY_MODES = [
  ["approval_queue", "Mode A · Approval Queue"],
  ["auto_protect_exits", "Mode B · Auto-Protect Exits"],
];
const EXECUTION_MODES = [
  ["dry_run", "Dry-Run"],
  ["live_guarded", "Live Guarded"],
];
const ACTION_LABEL = {
  TRIM_TO_USDC: "Trim to USDC",
  PROTECTIVE_STOP: "Protective stop",
  ACCUMULATE_SUPPORT: "Accumulate support",
  BREAKOUT_ENTRY: "Breakout entry",
};
const STATUS_LABEL = {
  pending_approval: "Pending approval",
  approved: "Approved",
  rejected: "Rejected",
  blocked_by_guard: "Blocked by guard",
  auto_executed_dry_run: "Auto-executed (dry run)",
  auto_armed_dry_run: "Stop armed (dry run)",
};
const STATUS_CHIP = {
  pending_approval: "is-sev-warning",
  blocked_by_guard: "is-sev-critical",
  approved: "is-sev-watch",
  auto_executed_dry_run: "is-sev-watch",
  auto_armed_dry_run: "is-sev-watch",
};
const DECIDABLE = new Set(["pending_approval", "blocked_by_guard"]);
const MAX_CAP = 20;

const price = (value) => {
  const n = Number(value);
  if (value === null || value === undefined || !Number.isFinite(n)) return "—";
  return n >= 1 ? n.toLocaleString(undefined, { maximumFractionDigits: 2 }) : n.toPrecision(4);
};

function ProposalRow({ proposal, busy, onDecide }) {
  const symbol = String(proposal.symbol || "").toUpperCase();
  const status = proposal.status || "pending_approval";
  const tradeUrl = getCoinbaseAdvancedSpotUrl(proposal);
  const blockReasons = Array.isArray(proposal.execution?.block_reasons) ? proposal.execution.block_reasons : [];
  return (
    <li className="mw-finding mw-proposal" aria-label={`${symbol} ${ACTION_LABEL[proposal.action] || proposal.action}`}>
      <div className="mw-finding__line">
        <span className={`mw-agents-chip ${proposal.side === "buy" ? "is-state-running" : "is-sev-warning"}`}>
          {ACTION_LABEL[proposal.action] || proposal.action}
        </span>
        <span className="mw-finding__symbol">{symbol}</span>
        <span className={`mw-agents-chip ${STATUS_CHIP[status] || ""}`}>{STATUS_LABEL[status] || status}</span>
      </div>
      <dl className="mw-proposal__levels">
        <div><dt>Reference</dt><dd>{price(proposal.reference_price)}</dd></div>
        <div><dt>Stop</dt><dd>{price(proposal.stop_price)}</dd></div>
        {proposal.trim_pct ? <div><dt>Trim</dt><dd>{proposal.trim_pct}%</dd></div> : null}
      </dl>
      {Array.isArray(proposal.reasons) && proposal.reasons.length ? (
        <p className="mw-finding__summary">{proposal.reasons.join(" · ")}</p>
      ) : null}
      {blockReasons.length ? <p className="mw-agents-note">Guard: {blockReasons.join(", ").replaceAll("_", " ")}</p> : null}
      <div className="mw-proposal__actions">
        {tradeUrl ? (
          <a
            className="mw-button mw-button--ghost mw-button--sm"
            href={tradeUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            Trade
          </a>
        ) : null}
        {DECIDABLE.has(status) && proposal.proposal_id ? (
          <>
            <button type="button" className="mw-button mw-button--ghost mw-button--sm" disabled={busy}
              onClick={() => onDecide(proposal.proposal_id, "approve")}>Approve</button>
            <button type="button" className="mw-button mw-button--ghost mw-button--sm" disabled={busy}
              onClick={() => onDecide(proposal.proposal_id, "reject")}>Reject</button>
          </>
        ) : null}
      </div>
    </li>
  );
}

export default function CycleStrategistDeck() {
  const [autonomy, setAutonomy] = useState(null);
  const [proposals, setProposals] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [capDraft, setCapDraft] = useState("");

  const load = useCallback(async () => {
    try {
      const payload = await fetchAgentProposals({ limit: 100 });
      setProposals(Array.isArray(payload.proposals) ? payload.proposals : []);
      if (payload.autonomy && typeof payload.autonomy === "object") {
        setAutonomy(payload.autonomy);
        setCapDraft(String(payload.autonomy.daily_order_cap ?? ""));
      }
      setError("");
    } catch (cause) {
      setError(cause.status === 401 || cause.status === 403
        ? "Strategist controls are available to the configured portfolio owner."
        : cause.message || "Strategist proposals are unavailable.");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async (changes) => {
    setBusy(true);
    try {
      const payload = await updateAgentAutonomy(changes);
      if (payload.autonomy) {
        setAutonomy(payload.autonomy);
        setCapDraft(String(payload.autonomy.daily_order_cap ?? ""));
      }
      setError("");
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  };

  const decide = async (id, decision) => {
    setBusy(true);
    try {
      const payload = await (decision === "approve" ? approveAgentProposal(id) : rejectAgentProposal(id));
      if (payload.proposal) {
        setProposals((rows) => rows.map((row) => (row.proposal_id === id ? payload.proposal : row)));
      }
      setError("");
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  };

  const capValue = Number(capDraft);
  const capValid = capDraft !== "" && Number.isInteger(capValue) && capValue >= 0 && capValue <= MAX_CAP;
  const pending = proposals.filter((p) => DECIDABLE.has(p.status)).length;

  return (
    <>
      <section className="mw-panel mw-autonomy-deck" aria-label="Autonomy control deck">
        <div className="mw-panel__header">
          <div><h3>Autonomy Control Deck</h3><span>Cycle Strategist · dry-run only, no live orders</span></div>
          {autonomy?.emergency_pause ? <span className="mw-agents-chip is-sev-critical">Paused</span> : null}
        </div>
        {error ? <p className="mw-agents-error" role="alert">{error}</p> : null}
        {autonomy ? (
          <div className="mw-agents-filters">
            <div className="mw-pill-row" role="group" aria-label="Autonomy mode">
              {AUTONOMY_MODES.map(([value, label]) => (
                <button key={value} type="button" disabled={busy}
                  className={`mw-pill${autonomy.autonomy_mode === value ? " is-active" : ""}`}
                  aria-pressed={autonomy.autonomy_mode === value}
                  onClick={() => save({ autonomy_mode: value })}>{label}</button>
              ))}
            </div>
            <div className="mw-pill-row" role="group" aria-label="Execution mode">
              {EXECUTION_MODES.map(([value, label]) => (
                <button key={value} type="button" disabled={busy}
                  className={`mw-pill${autonomy.execution_mode === value ? " is-active" : ""}`}
                  aria-pressed={autonomy.execution_mode === value}
                  onClick={() => save({ execution_mode: value })}>{label}</button>
              ))}
            </div>
            <label className="mw-agents-check">
              <input type="checkbox" checked={Boolean(autonomy.emergency_pause)} disabled={busy}
                onChange={(e) => save({ emergency_pause: e.target.checked })} /> Emergency Pause
            </label>
            <label>
              <span>Daily Order Cap</span>
              <input type="number" min="0" max={MAX_CAP} step="1" value={capDraft} aria-label="Daily order cap"
                className="mw-autonomy-deck__cap" onChange={(e) => setCapDraft(e.target.value)} />
              <button type="button" className="mw-button mw-button--ghost mw-button--sm"
                disabled={busy || !capValid || capValue === autonomy.daily_order_cap}
                onClick={() => save({ daily_order_cap: capValue })}>Save cap</button>
            </label>
          </div>
        ) : null}
        {autonomy?.execution_mode === "live_guarded" ? (
          <p className="mw-agents-note">
            Live Guarded has no live order route yet, so automatic exits stay blocked. Use Dry-Run to simulate them.
          </p>
        ) : autonomy ? (
          <p className="mw-agents-note">
            {autonomy.autonomy_mode === "auto_protect_exits"
              ? "Mode B: trims and protective stops run through the guarded dry-run exit path; entries wait for approval."
              : "Mode A: every proposal waits for your approval. Approval records the decision; it never places an order."}
          </p>
        ) : null}
      </section>

      <section className="mw-panel" aria-label="Trade proposal queue">
        <div className="mw-panel__header">
          <div><h3>Trade Proposal Queue</h3><span>{pending} awaiting a decision</span></div>
          <button type="button" className="mw-button mw-button--ghost mw-button--sm" onClick={load} disabled={busy}>Refresh</button>
        </div>
        {proposals.length ? (
          <ul className="mw-findings">
            {proposals.map((p) => (
              <ProposalRow key={p.proposal_id || `${p.symbol}-${p.action}`} proposal={p} busy={busy} onDecide={decide} />
            ))}
          </ul>
        ) : (
          <p className="mw-agents-note">No proposals yet. The Cycle Strategist adds them on each agent pass.</p>
        )}
      </section>
    </>
  );
}
