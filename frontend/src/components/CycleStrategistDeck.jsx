import { useCallback, useEffect, useState } from "react";
import {
  approveAgentProposal,
  fetchAgentProposals,
  rejectAgentProposal,
  runCycleAgentPass,
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
  RELOAD_ACCUMULATE: "Reload accumulate",
  ROTATE_TO_LEADER: "Rotate to leader",
};
const RUNG_BASIS = {
  "log_fib_0.618": "0.618 log-Fib support",
  "log_fib_0.702": "0.702 log-Fib support",
  "log_fib_0.786": "0.786 log-Fib support",
  daily_higher_low_floor: "Daily higher-low floor",
  fib_confluence_cluster: "Fib confluence cluster",
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

const finite = (value) => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
const usd = (value) => (finite(value)
  ? `$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  : "—");
const coins = (value) => (finite(value) ? Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 }) : "—");
const signedCoins = (value) => `${value >= 0 ? "+" : ""}${coins(value)}`;
const signedPct = (value) => (finite(value) ? `${Number(value) >= 0 ? "+" : ""}${Number(value).toFixed(2)}%` : "—");

function TradeLink({ target, children }) {
  const url = getCoinbaseAdvancedSpotUrl(target);
  if (!url) return null;
  return (
    <a className="mw-button mw-button--ghost mw-button--sm" href={url} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  );
}

// Trim → rebuy ladder: the USDC a trim frees, laddered into lower support.
function ReloadPlan({ plan, symbol }) {
  if (!plan || typeof plan !== "object") return null;
  if (!plan.available) {
    return (
      <p className="mw-agents-note">
        No reload ladder: no support level sits between the invalidation stop and the trim price.
      </p>
    );
  }
  const tranches = Array.isArray(plan.tranches) ? plan.tranches : [];
  return (
    <section className="mw-proposal__plan" aria-label={`${symbol} reload plan`}>
      <h4>Reload Plan ({signedPct(plan.net_coin_gain_pct)} Extra Coins)</h4>
      <p className="mw-finding__summary">
        Trim {coins(plan.trim_quantity)} {symbol} for {usd(plan.freed_usdc)} USDC, rebuy {coins(plan.projected_reloaded_coins)} {symbol}
        {finite(plan.net_coin_gain_qty) ? ` (${Number(plan.net_coin_gain_qty) >= 0 ? "+" : ""}${coins(plan.net_coin_gain_qty)} ${symbol})` : ""} with {usd(plan.fresh_cash_usd)} fresh cash.
      </p>
      <table className="mw-proposal__rungs">
        <thead>
          <tr><th scope="col">Rung</th><th scope="col">Level</th><th scope="col">USDC</th><th scope="col">Coins</th><th scope="col">Basis</th></tr>
        </thead>
        <tbody>
          {tranches.map((rung) => (
            <tr key={rung.index} className={rung.filled ? "is-filled" : undefined}>
              <th scope="row">{rung.index} · {rung.weight_pct}%</th>
              <td>{price(rung.level)}</td>
              <td>{usd(rung.usdc)}</td>
              <td>{coins(rung.coins)}</td>
              <td>
                {RUNG_BASIS[rung.basis] || rung.basis}
                {rung.filled ? " · spent" : finite(rung.remaining_usdc) && rung.remaining_usdc < rung.usdc
                  ? ` · ${usd(rung.remaining_usdc)} left` : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mw-agents-note">
        Invalid below {price(plan.invalidation_stop)}. Assumes each rung fills at its level; fees and slippage are not included.
      </p>
    </section>
  );
}

function SuggestedSize({ sizing, symbol }) {
  if (!sizing || typeof sizing !== "object") return null;
  const sized = finite(sizing.suggested_notional_usd);
  const unavailable = sizing.note === "positions_unpriced" ? "needs prices for all holdings"
    : sizing.note === "invalid_stop" ? "needs a stop below entry"
    : "needs portfolio equity";
  return (
    <>
      <div>
        <dt>Suggested Size</dt>
        <dd>
          {sized
            ? `${usd(sizing.suggested_notional_usd)}${finite(sizing.suggested_quantity) ? ` · ${coins(sizing.suggested_quantity)} ${symbol}` : ""}`
            : unavailable}
        </dd>
      </div>
      {finite(sizing.risk_budget_pct) ? (
        <div>
          <dt>Risk</dt>
          <dd>
            {Number(sizing.risk_budget_pct).toFixed(2)}%
            {finite(sizing.risk_at_stop_usd) ? ` · ${usd(sizing.risk_at_stop_usd)} at stop` : ""}
            {finite(sizing.stage_multiplier) ? ` · ${sizing.stage_multiplier}× stage` : ""}
          </dd>
        </div>
      ) : null}
    </>
  );
}

function sizingNotes(sizing) {
  if (!sizing || typeof sizing !== "object") return [];
  const notes = [];
  if (sizing.heat_capped) {
    notes.push(`Heat cap: open risk is ${finite(sizing.open_risk_pct) ? `${sizing.open_risk_pct}%` : "unknown"} of the ${sizing.max_open_risk_pct}% limit, so the size is reduced.`);
  }
  if (sizing.position_capped) notes.push("Size held to the single-position limit.");
  if (finite(sizing.funded_usd)) notes.push(`USDC funding limit ${usd(sizing.funded_usd)}.`);
  if (sizing.equity_basis === "held_positions_mark") notes.push("Equity is the marked value of held coins only; cash is not counted.");
  return notes;
}

function ProposalRow({ proposal, busy, onDecide }) {
  const symbol = String(proposal.symbol || "").toUpperCase();
  const status = proposal.status || "pending_approval";
  const blockReasons = Array.isArray(proposal.execution?.block_reasons) ? proposal.execution.block_reasons : [];
  const heldReason = typeof proposal.execution?.held_reason === "string" ? proposal.execution.held_reason : "";
  const evidence = proposal.evidence && typeof proposal.evidence === "object" ? proposal.evidence : {};
  const staleBreak = proposal.breach_state === "stale_floor_break_reassess";
  const pair = proposal.action === "ROTATE_TO_LEADER" && proposal.pair && typeof proposal.pair === "object" ? proposal.pair : null;
  const buySymbol = pair ? String(pair.buy_symbol || "").toUpperCase() : symbol;
  const notes = sizingNotes(proposal.sizing);
  return (
    <li className="mw-finding mw-proposal" aria-label={`${symbol} ${ACTION_LABEL[proposal.action] || proposal.action}`}>
      <div className="mw-finding__line">
        <span className={`mw-agents-chip ${proposal.side === "buy" ? "is-state-running" : "is-sev-warning"}`}>
          {ACTION_LABEL[proposal.action] || proposal.action}
        </span>
        <span className="mw-finding__symbol">{pair ? `${symbol} → ${buySymbol}` : symbol}</span>
        {finite(proposal.reward_to_risk_ratio) ? (
          <span className="mw-agents-chip is-sev-watch" title="Reward to the target midpoint over risk to the stop">
            R:R {Number(proposal.reward_to_risk_ratio).toFixed(2)}
          </span>
        ) : null}
        {staleBreak ? (
          <span className="mw-agents-chip is-sev-watch" title="Floor broke long ago; reassess instead of selling the low">Reassess</span>
        ) : null}
        <span className={`mw-agents-chip ${STATUS_CHIP[status] || ""}`}>{STATUS_LABEL[status] || status}</span>
      </div>
      <dl className="mw-proposal__levels">
        <div><dt>Reference</dt><dd>{price(proposal.reference_price)}</dd></div>
        {pair ? (
          <>
            <div><dt>{buySymbol} entry</dt><dd>{price(pair.leader?.reference_price)}</dd></div>
            <div><dt>{buySymbol} stop</dt><dd>{price(pair.leader?.stop_price)}</dd></div>
          </>
        ) : (
          <div><dt>Stop</dt><dd>{price(proposal.stop_price)}</dd></div>
        )}
        {finite(evidence.reclaim_resistance) ? (
          <div><dt>Reclaim</dt><dd>{price(evidence.reclaim_resistance)}</dd></div>
        ) : finite(evidence.broken_floor_price) ? (
          <div><dt>Broken floor</dt><dd>{price(evidence.broken_floor_price)}</dd></div>
        ) : null}
        {finite(proposal.target_price) ? <div><dt>Target</dt><dd>{price(proposal.target_price)}</dd></div> : null}
        {proposal.trim_pct ? <div><dt>Trim</dt><dd>{Number(proposal.trim_pct).toLocaleString(undefined, { maximumFractionDigits: 2 })}%</dd></div> : null}
        <SuggestedSize sizing={proposal.sizing} symbol={buySymbol} />
      </dl>
      {Array.isArray(proposal.reasons) && proposal.reasons.length ? (
        <p className="mw-finding__summary">{proposal.reasons.join(" · ")}</p>
      ) : null}
      {notes.length ? <p className="mw-agents-note">{notes.join(" ")}</p> : null}
      {proposal.action === "TRIM_TO_USDC" ? <ReloadPlan plan={proposal.reload_plan} symbol={symbol} /> : null}
      {blockReasons.length ? <p className="mw-agents-note">Guard: {blockReasons.join(", ").replaceAll("_", " ")}</p> : null}
      {heldReason ? <p className="mw-agents-note">Held for approval: {heldReason.replaceAll("_", " ")}</p> : null}
      <div className="mw-proposal__actions">
        {pair ? (
          <>
            <TradeLink target={pair.sell_product_id || proposal}>Sell {symbol}</TradeLink>
            <TradeLink target={pair.buy_product_id}>Buy {buySymbol}</TradeLink>
          </>
        ) : (
          <TradeLink target={proposal}>Trade</TradeLink>
        )}
        {DECIDABLE.has(status) && proposal.proposal_id ? (
          <>
            <button type="button" className="mw-button mw-button--ghost mw-button--sm"
              disabled={busy || (proposal.action === "RELOAD_ACCUMULATE" && !(proposal.sizing?.suggested_notional_usd > 0))}
              onClick={() => onDecide(proposal.proposal_id, "approve")}>Approve</button>
            <button type="button" className="mw-button mw-button--ghost mw-button--sm" disabled={busy}
              onClick={() => onDecide(proposal.proposal_id, "reject")}>Reject</button>
          </>
        ) : null}
      </div>
    </li>
  );
}

const PASS_SKIP_REASONS = {
  no_cycle_scan: "the cycle scan is still warming or out of date",
};

export default function CycleStrategistDeck() {
  const [autonomy, setAutonomy] = useState(null);
  const [proposals, setProposals] = useState([]);
  const [reloadPlans, setReloadPlans] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [capDraft, setCapDraft] = useState("");
  const [summary, setSummary] = useState(null);
  const [coverage, setCoverage] = useState(null);
  const [passNote, setPassNote] = useState("");

  const load = useCallback(async () => {
    try {
      const payload = await fetchAgentProposals({ limit: 100 });
      setSummary(payload.compounding_summary && typeof payload.compounding_summary === "object"
        ? payload.compounding_summary : null);
      setCoverage(payload.cycle_scan ?? null);
      setProposals(Array.isArray(payload.proposals) ? payload.proposals : []);
      setReloadPlans(Array.isArray(payload.reload_plans) ? payload.reload_plans : []);
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
      // Approving a trim opens its reload ladder, and approving a reload spends a rung.
      if (["TRIM_TO_USDC", "RELOAD_ACCUMULATE"].includes(payload.proposal?.action)) await load();
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  };

  const runPass = async () => {
    setBusy(true);
    setError("");
    setPassNote("Running desk pass…");
    try {
      const result = await runCycleAgentPass();
      await load();
      if (result.runs?.some((run) => run.status === "error") || result.smart_alerts?.status === "error") {
        setError("The desk pass encountered an error running Cycle Strategist or Smart Alerts.");
        setPassNote("");
      } else if (result.status === "ok") {
        const count = Array.isArray(result.proposals) ? result.proposals.length : 0;
        setPassNote(`Desk pass complete · ${count} proposal${count === 1 ? "" : "s"} from this pass`);
      } else {
        setPassNote(`Desk pass skipped · ${PASS_SKIP_REASONS[result.reason] || result.reason || "no reason given"}`);
      }
    } catch (cause) {
      setPassNote("");
      setError(cause.message || "The desk pass could not run.");
    } finally {
      setBusy(false);
    }
  };

  const extraCoins = summary
    ? Array.from(new Set([
      ...Object.keys(summary.realized_extra_coins_by_symbol || {}),
      ...Object.keys(summary.projected_extra_coins_by_symbol || {}),
    ])).sort()
    : [];
  const ladders = Number(summary?.active_ladders_count) || 0;

  const capValue = Number(capDraft);
  const capValid = capDraft !== "" && Number.isInteger(capValue) && capValue >= 0 && capValue <= MAX_CAP;
  const pending = proposals.filter((p) => DECIDABLE.has(p.status)).length;

  return (
    <>
      <section className="mw-panel mw-autonomy-deck" aria-label="Autonomy control deck">
        <div className="mw-panel__header">
          <div><h3>Autonomy Control Deck</h3><span>Cycle Strategist · dry-run only, no live orders</span></div>
          {autonomy?.emergency_pause ? <span className="mw-agents-chip is-sev-critical">Paused</span> : null}
          {autonomy ? (
            <button type="button" className="mw-pill" disabled={busy} onClick={runPass}
              title="Run the Cycle Strategist and smart alerts once from the cached cycle scan. Dry-run only.">
              Run Desk Pass
            </button>
          ) : null}
        </div>
        {finite(coverage?.ready_count) && finite(coverage?.target_universe_size) ? (
          <p className="mw-agents-note">Atlas coverage · {coverage.ready_count} / {coverage.target_universe_size} coins</p>
        ) : null}
        {passNote ? <p className="mw-agents-note" role="status">{passNote}</p> : null}
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
              ? "Mode B: trims and protective stops run through the guarded dry-run exit path; entries, reloads and rotations wait for approval."
              : "Mode A: every proposal waits for your approval. Approval records the decision; it never places an order."}
          </p>
        ) : null}
      </section>

      {summary ? (
        <section className="mw-panel" aria-label="Coin-stack compounding scoreboard">
          <div className="mw-panel__header">
            <div><h3>Coin-Stack Compounding Scoreboard</h3><span>Dry-run figures from approved and simulated trims, stops and reloads</span></div>
          </div>
          <dl className="mw-agents-scoreboard">
            <div>
              <dt>Freed Reload USDC</dt>
              <dd>{usd(summary.freed_usdc_available)} · {ladders} open ladder{ladders === 1 ? "" : "s"}</dd>
            </div>
            <div>
              <dt>Drawdown Avoided</dt>
              <dd>{summary.drawdown_priced_symbols?.length === 0 ? "—" : usd(summary.drawdown_avoided_usd)}</dd>
            </div>
            <div>
              <dt>Extra Coins Compounded / Projected</dt>
              <dd className="mw-agents-scoreboard__coins">
                {extraCoins.length ? extraCoins.map((symbol) => (
                  <span key={symbol}>
                    {symbol} {signedCoins(summary.realized_extra_coins_by_symbol?.[symbol] ?? 0)}
                    {" / "}{signedCoins(summary.projected_extra_coins_by_symbol?.[symbol] ?? 0)}
                  </span>
                )) : "None yet"}
              </dd>
            </div>
          </dl>
        </section>
      ) : null}

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

      {reloadPlans.length ? (
        <section className="mw-panel" aria-label="Open reload ladders">
          <div className="mw-panel__header">
            <div><h3>Open Reload Ladders</h3><span>USDC freed by approved or dry-run trims, waiting to rebuy lower</span></div>
          </div>
          <ul className="mw-findings">
            {reloadPlans.map((plan) => {
              const symbol = String(plan.symbol || "").toUpperCase();
              return (
                <li key={plan.plan_id} className="mw-finding mw-proposal" aria-label={`${symbol} open reload ladder`}>
                  <div className="mw-finding__line">
                    <span className="mw-finding__symbol">{symbol}</span>
                    <span className="mw-agents-chip is-sev-watch">{usd(plan.remaining_usdc)} unspent</span>
                  </div>
                  <ReloadPlan plan={plan} symbol={symbol} />
                  <div className="mw-proposal__actions">
                    <TradeLink target={plan}>Trade</TradeLink>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
    </>
  );
}
