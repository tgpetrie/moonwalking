import { useCallback, useState } from "react";
import {
  createSmartAlertRule,
  deleteSmartAlertRule,
  fetchSmartAlertHistory,
  fetchSmartAlertRules,
  sendSmartAlertTest,
  updateSmartAlertRule,
} from "../api.js";

// Owner-only smart wake-up rules (/api/smart-alerts/*). Rules are evaluated on
// each local agent pass; this panel only edits them and shows what fired.

const URGENCY_LABEL = { wake_up: "Wake-up", action_queue: "Action queue", watch: "Watch" };
const chip = (urgency) => `bh-smart-alerts__chip is-${urgency}`;
const SCOPE_LABEL = {
  market: "Market (industry)",
  held: "Held positions",
  watchlist: "Watchlist",
  universe: "Whole universe",
  symbols: "Specific symbols",
};
const PREDICATE_HINT = {
  cycle_bucket: "e.g. deep_accumulation_exhaustion",
  liquidity_rotation_stage: "minimum stage, e.g. 3",
  rsi_regime: "e.g. growth_expansion",
  weekly_stoch_rsi_turn: "e.g. oversold_turn_up",
  daily_macd_kiss: "fires when true",
  weekly_macd_cross: "fires when true",
  fib_zone_hit: "rollover_target_box or at_multi_year_support",
  confirmation_pivot_break: "fires when true",
  stop_proximity_pct: "max % from stop, e.g. 3",
  price_above: "price level",
  price_below: "price level",
};
const BOOLEAN_PREDICATES = new Set(["daily_macd_kiss", "weekly_macd_cross", "confirmation_pivot_break"]);
const NUMERIC_PREDICATES = new Set(["price_above", "price_below"]);

/** Turn the form's text value into the shape each backend predicate expects. */
export function buildConditionValue(predicate, raw) {
  const text = String(raw ?? "").trim();
  if (BOOLEAN_PREDICATES.has(predicate)) return true;
  const number = Number(text);
  const isNumber = text !== "" && Number.isFinite(number);
  if (NUMERIC_PREDICATES.has(predicate)) return isNumber ? number : null;
  if (predicate === "stop_proximity_pct") return isNumber ? { max: number } : null;
  if (predicate === "liquidity_rotation_stage") return isNumber ? { min: number } : text || null;
  if (predicate === "weekly_stoch_rsi_turn") return text || "oversold_turn_up";
  if (predicate === "fib_zone_hit") return text || "rollover_target_box";
  return text || null;
}

function describeCondition({ predicate, value }) {
  if (value === undefined || value === null || value === true) return predicate;
  if (Array.isArray(value)) return predicate + ": " + value.join(", ");
  if (typeof value === "object") {
    if (value.regime) {
      const regimes = Array.isArray(value.regime) ? value.regime.join(", ") : value.regime;
      return (value.timeframe || "1w").toUpperCase() + " " + predicate + ": " + regimes;
    }
    const parts = [];
    if (value.min !== undefined) parts.push(`≥ ${value.min}`);
    if (value.max !== undefined) parts.push(`≤ ${value.max}`);
    if (value.low !== undefined || value.high !== undefined) parts.push(`${value.low}–${value.high}`);
    return `${predicate} ${parts.join(" ") || JSON.stringify(value)}`;
  }
  return `${predicate}: ${value}`;
}

const EMPTY_FORM = { name: "", urgency: "wake_up", scope: "watchlist", symbols: "", predicate: "price_above", value: "" };

function when(ts) {
  return ts ? new Date(Number(ts) * 1000).toLocaleString() : "—";
}

export default function SmartAlertRulesPanel() {
  const [loaded, setLoaded] = useState(false);
  const [rules, setRules] = useState([]);
  const [history, setHistory] = useState([]);
  const [predicates, setPredicates] = useState(Object.keys(PREDICATE_HINT));
  const [ntfyConfigured, setNtfyConfigured] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [testUrgency, setTestUrgency] = useState("wake_up");
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoadError("");
    setLoaded(false);
    try {
      const [rulePayload, historyPayload] = await Promise.all([
        fetchSmartAlertRules(),
        fetchSmartAlertHistory({ limit: 25 }),
      ]);
      setRules(Array.isArray(rulePayload.rules) ? rulePayload.rules : []);
      if (Array.isArray(rulePayload.predicates) && rulePayload.predicates.length) setPredicates(rulePayload.predicates);
      setNtfyConfigured(Boolean(rulePayload.ntfy_configured));
      setHistory(Array.isArray(historyPayload.history) ? historyPayload.history : []);
      setError("");
    } catch (cause) {
      setLoadError(cause.status === 401 || cause.status === 403
        ? "Smart alert rules are available to the configured portfolio owner."
        : cause.message || "Smart alert rules are unavailable.");
    } finally {
      setLoaded(true);
    }
  }, []);

  const run = async (action, successNotice) => {
    setBusy(true);
    try {
      const result = await action();
      setError("");
      setNotice(result || successNotice || "");
    } catch (cause) {
      setError(cause.message);
      setNotice("");
    } finally {
      setBusy(false);
    }
  };

  const toggle = (rule) => run(async () => {
    const { rule: next } = await updateSmartAlertRule(rule.id, { enabled: !rule.enabled });
    setRules((rows) => rows.map((row) => (row.id === rule.id ? next : row)));
  });

  const remove = (rule) => run(async () => {
    await deleteSmartAlertRule(rule.id);
    setRules((rows) => rows.filter((row) => row.id !== rule.id));
  }, `Deleted “${rule.name}”.`);

  const value = buildConditionValue(form.predicate, form.value);
  const symbols = form.symbols.split(/[\s,]+/).map((s) => s.trim().toUpperCase()).filter(Boolean);
  const formValid = form.name.trim() && value !== null && (form.scope !== "symbols" || symbols.length);

  const create = (event) => {
    event.preventDefault();
    if (!formValid) return;
    run(async () => {
      const { rule } = await createSmartAlertRule({
        name: form.name.trim(),
        urgency: form.urgency,
        scope: form.scope,
        ...(form.scope === "symbols" ? { symbols } : {}),
        conditions: [{ predicate: form.predicate, value }],
      });
      setRules((rows) => [...rows, rule]);
      setForm(EMPTY_FORM);
    }, "Rule created.");
  };

  const fireTest = () => run(async () => {
    const { alert } = await sendSmartAlertTest({ urgency: testUrgency });
    if (alert) setHistory((rows) => [alert, ...rows].slice(0, 25));
    const { ntfy, dispatcher } = alert?.delivered || {};
    const sent = ntfy === "sent" || (typeof dispatcher === "number" && dispatcher > 0);
    const failed = [ntfy, dispatcher].some((status) => typeof status === "string" && status.startsWith("failed"));
    if (sent) return failed ? "Test alert sent. A delivery channel failed." : "Test alert sent.";
    if (failed) return "Test alert recorded. Delivery failed.";
    return testUrgency === "watch" ? "Test alert recorded." : "Test alert recorded. No delivery was reported.";
  });

  return (
    <details className="mw-panel bh-smart-alerts" onToggle={(e) => { if (e.currentTarget.open && !loaded) load(); }}>
      <summary className="mw-panel__header">
        <div><h3>Smart Wake-Up Rules &amp; History</h3><span>Cycle rules checked on every agent pass</span></div>
      </summary>
      {!loaded ? <p className="bh-smart-alerts__note">Loading rules…</p> : null}
      {loadError ? (
        <div>
          <p className="bh-smart-alerts__error" role="alert">{loadError}</p>
          <button type="button" className="mw-button mw-button--ghost mw-button--sm" onClick={load}>Retry</button>
        </div>
      ) : null}
      {error ? <p className="bh-smart-alerts__error" role="alert">{error}</p> : null}
      {notice ? <p className="bh-smart-alerts__note" role="status">{notice}</p> : null}
      {loaded && !loadError && ntfyConfigured === false ? (
        <p className="bh-smart-alerts__note">No ntfy push destination is configured.</p>
      ) : null}

      {loaded && rules.length ? (
        <ul className="bh-smart-alerts__rules" aria-label="Smart alert rules">
          {rules.map((rule) => (
            <li key={rule.id} className={rule.enabled ? "" : "is-disabled"} aria-label={rule.name}>
              <div className="bh-smart-alerts__line">
                <span className={chip(rule.urgency)}>{URGENCY_LABEL[rule.urgency] || rule.urgency}</span>
                <strong>{rule.name}</strong>
                <span className="bh-smart-alerts__scope">
                  {SCOPE_LABEL[rule.scope] || rule.scope}{rule.symbols?.length ? ` · ${rule.symbols.join(", ")}` : ""}
                </span>
              </div>
              <p className="bh-smart-alerts__conditions">
                {(rule.conditions || []).map(describeCondition).join(rule.match === "any" ? " or " : " and ")}
              </p>
              <div className="bh-smart-alerts__actions">
                <label>
                  <input type="checkbox" checked={Boolean(rule.enabled)} disabled={busy} onChange={() => toggle(rule)}
                    aria-label={`Enable ${rule.name}`} /> Enabled
                </label>
                <button type="button" className="mw-button mw-button--ghost mw-button--sm" disabled={busy}
                  onClick={() => remove(rule)} aria-label={`Delete ${rule.name}`}>Delete</button>
              </div>
            </li>
          ))}
        </ul>
      ) : loaded && !loadError ? <p className="bh-smart-alerts__note">No rules yet.</p> : null}

      {loaded && !loadError ? (
        <>
          <form className="bh-smart-alerts__form" aria-label="New smart alert rule" onSubmit={create}>
            <label><span>Name</span>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </label>
            <label><span>Urgency</span>
              <select value={form.urgency} onChange={(e) => setForm({ ...form, urgency: e.target.value })}>
                {Object.entries(URGENCY_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <label><span>Scope</span>
              <select value={form.scope} onChange={(e) => setForm({ ...form, scope: e.target.value })}>
                {Object.entries(SCOPE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            {form.scope === "symbols" ? (
              <label><span>Symbols</span>
                <input value={form.symbols} placeholder="RENDER, SOL" onChange={(e) => setForm({ ...form, symbols: e.target.value })} />
              </label>
            ) : null}
            <label><span>Condition</span>
              <select value={form.predicate} onChange={(e) => setForm({ ...form, predicate: e.target.value, value: "" })}>
                {predicates.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </label>
            {BOOLEAN_PREDICATES.has(form.predicate) ? null : (
              <label><span>Value</span>
                <input value={form.value} placeholder={PREDICATE_HINT[form.predicate] || ""}
                  onChange={(e) => setForm({ ...form, value: e.target.value })} />
              </label>
            )}
            <button type="submit" className="mw-button mw-button--ghost mw-button--sm" disabled={busy || !formValid}>Add rule</button>
          </form>

          <div className="bh-smart-alerts__test">
            <label><span>Test urgency</span>
              <select value={testUrgency} onChange={(e) => setTestUrgency(e.target.value)} aria-label="Test alert urgency">
                {Object.entries(URGENCY_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <button type="button" className="mw-button mw-button--ghost mw-button--sm" disabled={busy} onClick={fireTest}>
              Send test alert
            </button>
          </div>

          <h4 className="bh-smart-alerts__subhead">Recent alerts</h4>
          {history.length ? (
            <ul className="bh-smart-alerts__history" aria-label="Smart alert history">
              {history.map((row) => (
                <li key={row.id ?? `${row.rule_id}-${row.symbol}-${row.fired_ts}`}>
                  <span className={chip(row.urgency)}>{URGENCY_LABEL[row.urgency] || row.urgency}</span>
                  <span className="bh-smart-alerts__symbol">{row.symbol}</span>
                  <span>{row.message}</span>
                  <time>{when(row.fired_ts)}</time>
                </li>
              ))}
            </ul>
          ) : <p className="bh-smart-alerts__note">Nothing has fired yet.</p>}
        </>
      ) : null}
    </details>
  );
}
