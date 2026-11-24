import { useCallback, useEffect, useState } from "react";
import {
  approveAgentProposal,
  fetchAgentProposals,
  rejectAgentProposal,
  runCycleAgentPass,
  updateAgentAutonomy,
  updateAgentSettings,
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
const CLUSTER_GUARD_REASON = {
  cluster_count_cap_exceeded: "Cluster position limit reached",
  cluster_heat_cap_exceeded: "Cluster heat cap exceeded",
  beta_adjusted_heat_cap_exceeded: "Beta-adjusted portfolio heat cap exceeded",
  risk_unavailable: "Risk unavailable",
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
const MISSION_STANCES = [
  ["autopilot", "Auto-Pilot (AI)"],
  ["bunker", "Lunar Bunker"],
  ["orbit", "Low-Lunar Orbit"],
  ["gravity_assist", "Gravity Assist"],
  ["full_burn", "Full Burn"],
];
const STANCE_LABEL = Object.fromEntries(MISSION_STANCES);
// Mirrors backend STANCE_PROFILES until the API readout arrives.
const FALLBACK_STANCE_PROFILES = {
  bunker: { max_total_heat_pct: 2.5, max_cluster_heat_pct: 1.0, max_positions_per_cluster: 1, risk_per_trade_pct: 0.5, trim_fraction: 0.5, base_ladder_weights: [0.15, 0.3, 0.55] },
  orbit: { max_total_heat_pct: 5.0, max_cluster_heat_pct: 2.0, max_positions_per_cluster: 2, risk_per_trade_pct: 1.0, trim_fraction: 0.35, base_ladder_weights: [0.25, 0.35, 0.4] },
  gravity_assist: { max_total_heat_pct: 7.5, max_cluster_heat_pct: 3.0, max_positions_per_cluster: 3, risk_per_trade_pct: 1.5, trim_fraction: 0.25, base_ladder_weights: [0.4, 0.35, 0.25] },
  full_burn: { max_total_heat_pct: 10.0, max_cluster_heat_pct: 4.0, max_positions_per_cluster: 4, risk_per_trade_pct: 2.0, trim_fraction: 0.15, base_ladder_weights: [0.5, 0.3, 0.2] },
};

function readStance(payload) {
  if (!payload || typeof payload.effective_stance !== "string") return undefined;
  return {
    configured: payload.configured_stance,
    effective: payload.effective_stance,
    reason: payload.effective_stance_reason,
    profiles: payload.stance_profiles && typeof payload.stance_profiles === "object" ? payload.stance_profiles : null,
  };
}

const pct = (value) => `${Math.round(Number(value) * 100)}%`;

function MissionStance({ autonomy, stance, busy, onSelect }) {
  const configured = stance?.configured ?? autonomy?.stance ?? "orbit";
  const effective = stance?.effective ?? (configured === "autopilot" ? null : configured);
  const profile = effective ? (stance?.profiles?.[effective] ?? FALLBACK_STANCE_PROFILES[effective]) : null;
  return (
    <div className="mw-mission-stance">
      <div className="mw-pill-row" role="group" aria-label="Mission stance">
        {MISSION_STANCES.map(([value, label]) => (
          <button key={value} type="button" disabled={busy}
            className={`mw-pill${configured === value ? " is-active" : ""}`}
            aria-pressed={configured === value}
            onClick={() => onSelect(value)}>{label}</button>
        ))}
      </div>
      {configured === "autopilot" ? (
        <p className="mw-agents-note" role="status" aria-label="Auto-Pilot status">
          Auto-Pilot engaged · {effective ? `flying ${STANCE_LABEL[effective] || effective}` : "awaiting a cycle scan"}
          {stance?.reason ? ` · ${stance.reason}` : ""}
        </p>
      ) : null}
      {profile ? (
        <dl className="mw-agents-scoreboard" aria-label="Active stance limits">
          <div><dt>Heat Cap</dt><dd>{profile.max_total_heat_pct}% of equity</dd></div>
          <div><dt>Cluster Limit</dt><dd>{profile.max_positions_per_cluster} coins · {profile.max_cluster_heat_pct}% heat</dd></div>
          <div><dt>Trim</dt><dd>{pct(profile.trim_fraction)}</dd></div>
          <div><dt>Base Ladder Split</dt><dd>{(profile.base_ladder_weights || []).map(pct).join(" / ")}</dd></div>
        </dl>
      ) : null}
    </div>
  );
}

function FlightManual() {
  return (
    <div className="mw-flight-manual" aria-label="Flight manual and settings guide">
      <h4>1 · Workflow</h4>
      <ol>
        <li><strong>Off</strong> — tick Emergency Pause. The strategist still records proposals but nothing auto-executes.</li>
        <li><strong>Mode A · Recommend</strong> (Approval Queue) — every proposal waits for you. Approval records the decision; it never places an order.</li>
        <li><strong>Mode B · Auto Paper</strong> (Auto-Protect Exits) — trims and protective stops run through the guarded dry-run exit path; entries, reloads and rotations still wait for approval.</li>
        <li>Press <strong>Run Desk Pass</strong> to refresh desk findings and evaluate the cached cycle scan.</li>
        <li>Approve a <strong>TRIM_TO_USDC</strong>: the freed USDC opens a 3-rung reload ladder under Open Reload Ladders. Approve each <strong>RELOAD_ACCUMULATE</strong> as price reaches a rung.</li>
      </ol>
      <h4>2 · Mission Stances</h4>
      <table className="mw-flight-manual__table">
        <thead>
          <tr><th>Stance</th><th>Heat cap</th><th>Cluster</th><th>Risk / trade</th><th>Trim</th><th>Ladder</th><th>Use when</th></tr>
        </thead>
        <tbody>
          <tr><td>Lunar Bunker</td><td>2.5%</td><td>1 coin · 1%</td><td>0.5%</td><td>50%</td><td>15/30/55</td><td>Risk-off or rollover; new entries only from deep accumulation or confluence ≥ 75.</td></tr>
          <tr><td>Low-Lunar Orbit</td><td>5%</td><td>2 coins · 2%</td><td>1%</td><td>35%</td><td>25/35/40</td><td>Default, mixed or choppy regime.</td></tr>
          <tr><td>Gravity Assist</td><td>7.5%</td><td>3 coins · 3%</td><td>1.5%</td><td>25%</td><td>40/35/25</td><td>Alt rotation with aligned breadth.</td></tr>
          <tr><td>Full Burn</td><td>10%</td><td>4 coins · 4%</td><td>2%</td><td>15%</td><td>50/30/20</td><td>Broad expansion; also low-confirmation breakout / early markup at confluence ≥ 55.</td></tr>
          <tr><td>Auto-Pilot (AI)</td><td colSpan={5}>Uses the selected gear&apos;s limits</td><td>Lets the macro regime and Atlas bucket mix pick the gear on every pass.</td></tr>
        </tbody>
      </table>
      <h4>3 · Risk concepts</h4>
      <ul>
        <li><strong>Downside BTC Beta Heat</strong> — each position&apos;s risk-to-stop is multiplied by max(1, downside BTC beta ÷ 1.25), so an alt that falls harder than BTC on red days uses more of the heat cap.</li>
        <li><strong>11-Cluster Concentration Caps</strong> — coins are grouped into 11 narrative sector clusters plus majors (an unmapped coin is its own cluster); the stance caps coins and raw heat per cluster so one narrative cannot dominate.</li>
        <li><strong>Adaptive Wick-Tilted Ladders</strong> — <code>weight_source: ladder_optimizer</code> means past wick depth tilted the rung weights; <code>default</code> means the stance&apos;s base split was used.</li>
        <li><strong>Cost modeling</strong> — every paper fill assumes a 60 bps fee plus 10 bps slippage per side.</li>
        <li><strong>Net-of-Fees Coin-Stack Compounding</strong> — extra coins are counted only after both the trim&apos;s and each reload&apos;s fees and slippage.</li>
      </ul>
      <p className="mw-agents-note">Full manual: docs/AGENT_FLIGHT_MANUAL.md</p>
    </div>
  );
}

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
const riskPct = (value) => `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 })}%`;

function LadderWeights({ plan, proposal }) {
  const source = plan?.weight_source ?? proposal?.weight_source;
  const advice = plan?.ladder_optimizer ?? proposal?.ladder_optimizer;
  const applied = advice?.applied_to_tranches;
  const estimate = plan?.expected_extra_coins_vs_flat_weights
    ?? proposal?.expected_extra_coins_vs_flat_weights ?? advice?.expected_extra_coins_vs_flat_weights;
  let adaptive;
  if (source === "ladder_optimizer" || source === "default") adaptive = source === "ladder_optimizer";
  else if (typeof applied === "boolean") adaptive = applied;
  else if (finite(estimate)) adaptive = advice?.regime !== "default";
  else return null;

  if (adaptive) return <span className="mw-agents-chip">Adaptive wick-tilted weights</span>;
  const partial = plan?.tranches?.length > 0 && plan.tranches.length < 3;
  const base = Array.isArray(plan?.base_ladder_weights) && plan.base_ladder_weights.length
    ? plan.base_ladder_weights.join("/") : "25/35/40";
  return (
    <span className="mw-agents-chip">
      {partial ? `Base weights · normalized ${base}` : `Base weights · ${base}`}
    </span>
  );
}

function readClusterGuard(payload) {
  if (Array.isArray(payload.suppressed_proposals)) {
    return {
      ...payload.cluster_guard,
      suppressed_proposals: payload.cluster_guard?.suppressed_proposals ?? payload.suppressed_proposals,
    };
  }
  return payload.cluster_guard;
}

function ClusterGuardNote({ guard }) {
  const suppressed = Array.isArray(guard?.suppressed_proposals) ? guard.suppressed_proposals : [];
  const heat = guard?.total_beta_adjusted_risk_pct;
  const cap = guard?.limits?.max_total_heat_pct;
  if (!suppressed.length && !finite(heat)) return null;
  return (
    <div role="group" aria-label="Cluster guard">
      <span className="mw-agents-chip">
        Cluster guard{finite(heat) ? ` · ${riskPct(heat)} beta-adjusted heat` : ""}
        {finite(heat) && finite(cap) ? ` of ${riskPct(cap)}` : ""}
      </span>
      {suppressed.map((entry) => {
        const action = ACTION_LABEL[entry.action];
        const cluster = entry.cluster_guard?.cluster;
        const reason = entry.suppression_reason ?? entry.cluster_guard?.suppression_reason;
        const label = CLUSTER_GUARD_REASON[reason] || reason?.replaceAll("_", " ") || "Guard limit reached";
        const symbol = entry.sell_symbol ? `${entry.sell_symbol} → ${entry.symbol}` : entry.symbol;
        return (
          <p className="mw-agents-note" key={`${symbol}-${entry.action}-${reason}`}>
            Held back · {symbol}{action ? ` ${action.toLowerCase()}` : ""}
            {cluster && !cluster.startsWith("uncategorized:") ? ` (${cluster})` : ""} · {label}
          </p>
        );
      })}
    </div>
  );
}

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
        Invalid below {price(plan.invalidation_stop)}. Each rung uses the recorded paper assumptions.
        {plan.cost_model ? ` Fee ${plan.cost_model.fee_bps} bps and slippage ${plan.cost_model.slippage_bps} bps per side.` : " Historical fee and slippage assumptions are unavailable."}
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
  const clusterGuard = proposal.cluster_guard ?? evidence.cluster_guard;
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
        {proposal.action === "TRIM_TO_USDC" ? <LadderWeights plan={proposal.reload_plan} proposal={proposal} /> : null}
        {finite(clusterGuard?.beta_adjusted_risk_pct) ? (
          <span className="mw-agents-chip">
            {riskPct(clusterGuard.beta_adjusted_risk_pct)} beta-adjusted entry risk
          </span>
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

export default function CycleStrategistDeck({ lastCycleRun, onPassComplete } = {}) {
  const [autonomy, setAutonomy] = useState(null);
  const [proposals, setProposals] = useState([]);
  const [reloadPlans, setReloadPlans] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [capDraft, setCapDraft] = useState("");
  const [summary, setSummary] = useState(null);
  const [coverage, setCoverage] = useState(null);
  const [passNote, setPassNote] = useState("");
  const [clusterGuard, setClusterGuard] = useState(null);
  const [stance, setStance] = useState(null);
  const [manualOpen, setManualOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      const payload = await fetchAgentProposals({ limit: 100 });
      setSummary(payload.compounding_summary && typeof payload.compounding_summary === "object"
        ? payload.compounding_summary : null);
      setCoverage(payload.cycle_scan ?? null);
      setProposals(Array.isArray(payload.proposals) ? payload.proposals : []);
      setReloadPlans(Array.isArray(payload.reload_plans) ? payload.reload_plans : []);
      const guard = readClusterGuard(payload);
      if (guard !== undefined) setClusterGuard(guard);
      const readout = readStance(payload);
      if (readout !== undefined) setStance(readout);
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

  useEffect(() => { load(); }, [load, lastCycleRun]);

  const save = async (changes) => {
    setBusy(true);
    try {
      const payload = await ("stance" in changes ? updateAgentSettings : updateAgentAutonomy)(changes);
      if (payload.autonomy) {
        setAutonomy(payload.autonomy);
        setCapDraft(String(payload.autonomy.daily_order_cap ?? ""));
      }
      const readout = readStance(payload);
      if (readout !== undefined) setStance(readout);
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
    setClusterGuard(null);
    try {
      const result = await runCycleAgentPass();
      await Promise.all([load(), onPassComplete?.()]);
      if (result.runs?.some((run) => run.status === "error") || result.smart_alerts?.status === "error") {
        setError("The desk pass encountered an error. Check the agent summaries for details.");
        setPassNote("");
      } else if (result.status === "ok") {
        const guard = readClusterGuard(result);
        if (guard !== undefined) setClusterGuard(guard);
        const readout = readStance(result);
        if (readout !== undefined) setStance(readout);
        const count = Array.isArray(result.proposals) ? result.proposals.length : 0;
        setPassNote(`Desk pass complete · ${count} proposal${count === 1 ? "" : "s"} from this pass`);
      } else {
        const activity = result.runs?.length ? "Desk agents refreshed · Cycle Strategist skipped" : "Desk pass skipped";
        setPassNote(`${activity} · ${PASS_SKIP_REASONS[result.reason] || result.reason || "no reason given"}`);
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
              title="Refresh the desk agents once. Cycle Strategist and smart alerts use the cached cycle scan.">
              Run Desk Pass
            </button>
          ) : null}
        </div>
        {finite(coverage?.ready_count) && finite(coverage?.target_universe_size) ? (
          <p className="mw-agents-note">Atlas coverage · {coverage.ready_count} / {coverage.target_universe_size} coins</p>
        ) : null}
        {passNote ? <p className="mw-agents-note" role="status">{passNote}</p> : null}
        <ClusterGuardNote guard={clusterGuard} />
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
        {autonomy ? (
          <MissionStance autonomy={autonomy} stance={stance} busy={busy}
            onSelect={(value) => save({ stance: value })} />
        ) : null}
        <button type="button" className="mw-button mw-button--ghost mw-button--sm"
          aria-expanded={manualOpen} onClick={() => setManualOpen((open) => !open)}>
          {manualOpen ? "Hide Flight Manual & Settings Guide" : "Flight Manual & Settings Guide"}
        </button>
        {manualOpen ? <FlightManual /> : null}
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
              <dd>{summary.valuation_complete === false || summary.drawdown_priced_symbols?.length === 0 ? "—" : usd(summary.drawdown_avoided_usd)}</dd>
            </div>
            {"strategy_value_usd" in summary ? (
              <>
                <div><dt>Remaining Inventory Value</dt><dd>{usd(summary.remaining_inventory_value_usd)}</dd></div>
                <div><dt>Paper Cash + Inventory</dt><dd>{usd(summary.strategy_value_usd)}</dd></div>
                <div><dt>Net Value vs Hold</dt><dd>{usd(summary.net_value_vs_hold_usd)}</dd></div>
                <div><dt>Fees / Slippage Deducted</dt><dd>{usd(summary.fees_deducted_usd)} / {usd(summary.slippage_deducted_usd)}</dd></div>
              </>
            ) : null}
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
          {summary.mark_snapshot?.as_of_ts ? (
            <p className="mw-agents-note">Marked at the UTC daily close · {new Date(summary.mark_snapshot.as_of_ts * 1000).toISOString()}</p>
          ) : null}
          {summary.valuation_complete === false ? (
            <p className="mw-agents-note">Valuation unavailable for {summary.unpriced_symbols?.join(", ")}.</p>
          ) : null}
          {summary.legacy_costs_unrecorded?.length ? (
            <p className="mw-agents-note">Historical costs unavailable for {summary.legacy_costs_unrecorded.length} paper decisions.</p>
          ) : null}
          {Object.keys(summary.reload_funding_shortfall_by_symbol || {}).length ? (
            <p className="mw-agents-note">
              Reload funding needs reconciliation for {Object.keys(summary.reload_funding_shortfall_by_symbol).join(", ")}.
            </p>
          ) : null}
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
                    <LadderWeights plan={plan} />
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
