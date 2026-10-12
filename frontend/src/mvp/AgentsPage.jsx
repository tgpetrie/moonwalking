import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getBackendBase } from "../config/api.js";
import "../styles/agents-page.css";

// Read-only view of the local agent ledger (/api/agents/*). Nothing on this
// page runs an agent, edits code, or changes board data: agents run on demand
// from scripts/run_local_agents.py and only record findings with evidence.

const POLL_MS = 30000;
const SEVERITY_ORDER = ["critical", "warning", "watch", "info"];
const SEVERITY_LABEL = { critical: "Critical", warning: "Warning", watch: "Watch", info: "Info" };

const STATE_META = {
  running: { label: "Running", note: (ts) => `Started ${ago(ts)}` },
  idle: { label: "Idle", note: (ts) => `Last run completed ${ago(ts)}` },
  failed: { label: "Failed", note: (ts) => `Last run failed ${ago(ts)}` },
  interrupted: { label: "Interrupted", note: (ts) => `Started ${ago(ts)} and never finished` },
  never_run: { label: "Never run", note: () => "Hasn't run on this machine yet" },
};

// Where a finding's source lives in the app, when there's a page for it.
const SURFACE_LINKS = {
  board: { href: "/", label: "Live Board" },
  portfolio_risk_board: { href: "/app/risk-board", label: "Risk Board" },
};

const AUDIT_GROUPS = [
  { kind: "audit_problem", title: "Problems found" },
  { kind: "audit_recommended_change", title: "Recommended changes" },
  { kind: "audit_implementation_step", title: "Implementation steps" },
  { kind: "audit_unparsed", title: "Couldn't parse" },
];

export function ago(ts, now = Date.now()) {
  if (!ts) return "never";
  const seconds = Math.max(0, Math.round(now / 1000 - Number(ts)));
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} hr ago`;
  return `${Math.round(hours / 24)} days ago`;
}

function isExpired(observation, now = Date.now()) {
  return Boolean(observation.expires_ts) && Number(observation.expires_ts) * 1000 <= now;
}

function formatEvidenceValue(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "none";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

async function getJson(path, signal) {
  const response = await fetch(`${getBackendBase()}${path}`, {
    credentials: "include",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const payload = await response.json();
  if (payload?.status !== "live") throw new Error(payload?.error || "The agent ledger is unavailable.");
  return payload;
}

function SeverityChip({ severity }) {
  return (
    <span className={`mw-agents-chip is-sev-${severity}`}>{SEVERITY_LABEL[severity] || severity}</span>
  );
}

function AgentCard({ summary }) {
  const meta = STATE_META[summary.state] || STATE_META.never_run;
  const counts = summary.latest_findings_by_severity || {};
  const breakdown = SEVERITY_ORDER.filter((sev) => counts[sev]).map((sev) => `${counts[sev]} ${SEVERITY_LABEL[sev].toLowerCase()}`);
  const run = summary.latest_run;
  return (
    <article className={`mw-panel mw-agent-card is-${summary.state}`} aria-label={`${summary.label} agent`}>
      <header className="mw-agent-card__head">
        <h3>{summary.label}</h3>
        <span className={`mw-agents-chip is-state-${summary.state}`}>{meta.label}</span>
      </header>
      {summary.purpose ? <p className="mw-agent-card__purpose">{summary.purpose}</p> : null}
      <dl className="mw-agent-card__facts">
        <div><dt>Last activity</dt><dd>{meta.note(summary.last_activity_ts)}</dd></div>
        <div><dt>Runs</dt><dd>{summary.run_count}</dd></div>
        <div>
          <dt>Latest run found</dt>
          <dd>{!run ? "—" : breakdown.length ? breakdown.join(" · ") : "Nothing to report"}</dd>
        </div>
      </dl>
      {summary.state === "failed" && run?.error ? (
        <p className="mw-agent-card__error" role="note">{run.error}</p>
      ) : null}
    </article>
  );
}

function FindingRow({ observation, label, expired }) {
  const evidence = observation.evidence || {};
  const source = observation.source || {};
  const link = SURFACE_LINKS[source.surface];
  const evidenceEntries = Object.entries(evidence);
  return (
    <li className={`mw-finding${expired ? " is-expired" : ""}`}>
      <div className="mw-finding__line">
        <SeverityChip severity={observation.severity} />
        <span className="mw-finding__agent">{label}</span>
        {observation.symbol ? <span className="mw-finding__symbol">{observation.symbol}</span> : null}
        <span className="mw-finding__time" title={new Date(observation.created_ts * 1000).toLocaleString()}>
          {ago(observation.created_ts)}{expired ? " · expired" : ""}
        </span>
      </div>
      <p className="mw-finding__summary">{observation.summary}</p>
      {evidenceEntries.length || source.surface ? (
        <details className="mw-finding__evidence">
          <summary>Evidence</summary>
          {evidenceEntries.length ? (
            <dl>
              {evidenceEntries.map(([key, value]) => (
                <div key={key}><dt>{key}</dt><dd>{formatEvidenceValue(value)}</dd></div>
              ))}
            </dl>
          ) : <p>No evidence fields recorded.</p>}
          {source.surface ? (
            <p className="mw-finding__source">
              Source: {link ? <a href={link.href}>{link.label}</a> : source.surface}
              {source.table ? ` · ${source.table}` : ""}
              {source.path ? <> · <code>{source.path}</code></> : null}
            </p>
          ) : null}
        </details>
      ) : null}
    </li>
  );
}

export default function AgentsPage() {
  const [status, setStatus] = useState(null);
  const [observations, setObservations] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [agentFilter, setAgentFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [showExpired, setShowExpired] = useState(false);
  const active = useRef(null);

  const load = useCallback(async () => {
    if (active.current) return;
    const controller = new AbortController();
    active.current = controller;
    setLoading(true);
    try {
      const [nextStatus, nextObservations] = await Promise.all([
        getJson("/api/agents/status", controller.signal),
        getJson("/api/agents/observations?limit=250", controller.signal),
      ]);
      setStatus(nextStatus);
      setObservations(Array.isArray(nextObservations.observations) ? nextObservations.observations : []);
      setError("");
    } catch (cause) {
      if (cause.name !== "AbortError") setError(cause.message || "The agent ledger is unavailable.");
    } finally {
      // Only clear the slot if it's still ours: an unmount may already have
      // aborted this request and let a newer one start.
      if (active.current === controller) active.current = null;
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(() => { if (!document.hidden) load(); }, POLL_MS);
    return () => {
      clearInterval(timer);
      // Abort AND free the slot. Without freeing it, React's dev double-mount
      // aborted the first load and the in-flight guard then skipped the
      // second, so nothing ever loaded.
      active.current?.abort();
      active.current = null;
    };
  }, [load]);

  const summaries = status?.agent_summaries || [];
  const labels = useMemo(
    () => Object.fromEntries(summaries.map((s) => [s.agent, s.label])),
    [summaries]
  );
  const now = Date.now();
  const current = observations.filter((o) => !isExpired(o, now));
  const attention = current.filter((o) => o.severity === "critical" || o.severity === "warning").length;
  const ranCount = summaries.filter((s) => s.state !== "never_run").length;
  const lastPass = status?.last_run?.finished_ts || status?.last_run?.started_ts || null;

  const visible = observations
    .filter((o) => o.agent !== "audit_triage")
    .filter((o) => showExpired || !isExpired(o, now))
    .filter((o) => agentFilter === "all" || o.agent === agentFilter)
    .filter((o) => severityFilter === "all" || o.severity === severityFilter);
  const audit = observations.filter((o) => o.agent === "audit_triage");

  // No status yet and no error means we simply haven't heard back. Show
  // loading, never a zero-agent page that looks like a real empty ledger.
  if (!status && !error) {
    return (
      <section className="mw-panel mw-agents-state" aria-live="polite">
        <p className="mw-eyebrow">Local agents</p>
        <p>Loading the agent ledger…</p>
      </section>
    );
  }
  if (!status && error) {
    return (
      <section className="mw-panel mw-agents-state">
        <p className="mw-eyebrow">Local agents</p>
        <h2>Agent ledger unavailable</h2>
        <p className="mw-agents-error">{error}</p>
        <p>The page reads the backend at <code>/api/agents/status</code>. Make sure the local backend is running.</p>
        <button type="button" className="mw-button mw-button--ghost mw-button--sm" onClick={load}>Try again</button>
      </section>
    );
  }

  const llm = status?.local_llm || {};

  return (
    <div className="mw-stack mw-agents">
      <section className="mw-panel mw-agents-intro">
        <div>
          <p className="mw-eyebrow">Local agents</p>
          <p>
            Agents run on demand on this machine and record what they find, with evidence. They don&apos;t change the
            app, fix code, or place orders. Between runs every agent is idle.
          </p>
        </div>
        <div className="mw-agents-intro__actions">
          <span className="mw-agents-updated" role="status">
            {error ? `${error} Showing the last snapshot.` : loading ? "Refreshing…" : `Updated ${ago(status?.generated_ts)}`}
          </span>
          <button type="button" className="mw-button mw-button--ghost mw-button--sm" onClick={load} disabled={loading}>
            Refresh
          </button>
        </div>
      </section>

      <section className="mw-stat-grid mw-agents-stats" aria-label="Agent summary">
        <article className="mw-panel mw-stat-card"><span>Agents</span><strong>{summaries.length}</strong><small>{ranCount} have run here</small></article>
        <article className="mw-panel mw-stat-card"><span>Last pass</span><strong>{lastPass ? ago(lastPass) : "Never"}</strong><small>{status?.last_run ? `by ${labels[status.last_run.agent] || status.last_run.agent}` : "No runs recorded"}</small></article>
        <article className="mw-panel mw-stat-card"><span>Current findings</span><strong>{current.length}</strong><small>{observations.length - current.length} expired</small></article>
        <article className="mw-panel mw-stat-card"><span>Need attention</span><strong className={attention ? "is-attention" : ""}>{attention}</strong><small>Critical and warning</small></article>
      </section>

      {ranCount === 0 ? (
        <section className="mw-panel mw-agents-empty">
          <h3>No agent has run on this machine yet</h3>
          <p>With the backend running, start one pass from the repository root:</p>
          <code className="mw-agents-command">python scripts/run_local_agents.py</code>
          <p>Add <code>--audit-file path\to\AUDIT.md</code> to load an audit, or <code>--symbols BTC,ETH</code> for the risk-board fallback.</p>
        </section>
      ) : null}

      <section aria-label="Agents">
        <div className="mw-agents-grid">
          {summaries.map((summary) => <AgentCard key={summary.agent} summary={summary} />)}
        </div>
      </section>

      <section className="mw-panel" aria-label="Findings">
        <div className="mw-panel__header">
          <div><h3>Findings</h3><span>Newest first, with the evidence each one cites</span></div>
        </div>
        <div className="mw-agents-filters">
          <label>
            <span>Agent</span>
            <select value={agentFilter} onChange={(e) => setAgentFilter(e.target.value)}>
              <option value="all">All agents</option>
              {summaries.filter((s) => s.agent !== "audit_triage").map((s) => <option key={s.agent} value={s.agent}>{s.label}</option>)}
            </select>
          </label>
          <div className="mw-pill-row" role="group" aria-label="Severity">
            {["all", ...SEVERITY_ORDER].map((sev) => (
              <button key={sev} type="button" className={`mw-pill${severityFilter === sev ? " is-active" : ""}`} aria-pressed={severityFilter === sev} onClick={() => setSeverityFilter(sev)}>
                {sev === "all" ? "All" : SEVERITY_LABEL[sev]}
              </button>
            ))}
          </div>
          <label className="mw-agents-check">
            <input type="checkbox" checked={showExpired} onChange={(e) => setShowExpired(e.target.checked)} /> Show expired
          </label>
        </div>
        {visible.length ? (
          <ul className="mw-findings">
            {visible.map((o) => <FindingRow key={o.id} observation={o} label={labels[o.agent] || o.agent} expired={isExpired(o, now)} />)}
          </ul>
        ) : (
          <p className="mw-agents-note">{observations.length ? "No findings match these filters." : "No findings recorded yet."}</p>
        )}
      </section>

      <section className="mw-panel" aria-label="Audit queue">
        <div className="mw-panel__header">
          <div><h3>Audit queue</h3><span>From the last AUDIT.md the audit agent read</span></div>
          <span className="mw-agents-chip is-state-never_run">Identified, not tracked</span>
        </div>
        <p className="mw-agents-note">
          The audit agent lists work; it doesn&apos;t fix it or track progress yet. Queued → working → awaiting
          review → verified status, and the changes and checks behind each fix, come next.
        </p>
        {audit.length ? AUDIT_GROUPS.map(({ kind, title }) => {
          const items = audit.filter((o) => o.kind === kind);
          if (!items.length) return null;
          return (
            <div key={kind} className="mw-audit-group">
              <h4>{title} <span>{items.length}</span></h4>
              <ul className="mw-findings">
                {items.map((o) => <FindingRow key={o.id} observation={o} label={labels[o.agent] || o.agent} expired={isExpired(o, now)} />)}
              </ul>
            </div>
          );
        }) : <p className="mw-agents-note">No audit loaded. Run the agents with <code>--audit-file</code> to fill this in.</p>}
      </section>

      <section className="mw-panel mw-agents-llm" aria-label="Local model">
        <span className="mw-eyebrow">Local model narrator</span>
        <p>
          {llm.enabled
            ? <>On · {llm.provider}{llm.model ? ` · ${llm.model}` : ""}. Summaries only; findings above stay the source of truth.</>
            : "Off. Findings come from the deterministic agents only."}
        </p>
      </section>
    </div>
  );
}
