import { useEffect, useState } from "react";
import { getBackendBase } from "../config/api.js";

const MODES = [
  ["advisory", "Advisory"],
  ["guardian", "Guardian"],
  ["autonomous", "Autonomous (Paper)"],
];

async function request(path, options = {}) {
  const response = await fetch(`${getBackendBase()}${path}`, {
    credentials: "include",
    ...options,
    headers: { Accept: "application/json", ...options.headers },
  });
  const data = await response.json();
  if (!response.ok || data.status !== "live") {
    const error = new Error(data.error || `HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return data;
}

const display = (value) => value === null || value === undefined ? "—" : String(value);

export default function PaperExecutionControls({ productId = null, preview = null, collapsible = false }) {
  const [mode, setMode] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [paperPrice, setPaperPrice] = useState("");
  const [restricted, setRestricted] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const query = productId ? `?product_id=${encodeURIComponent(productId)}` : "";
    Promise.all([
      request("/api/execution-agent/mode", { signal: controller.signal }),
      request(`/api/execution-agent/tickets${query}`, { signal: controller.signal }),
    ]).then(([settings, result]) => {
      if (!MODES.some(([value]) => value === settings.mode) || !Array.isArray(result.tickets)) {
        throw new Error("Paper execution state unavailable.");
      }
      setMode(settings.mode);
      setRestricted(false);
      setTickets(result.tickets);
      setError("");
    }).catch((cause) => {
      if ([401, 403].includes(cause.status)) setRestricted(true);
      else if (cause.name !== "AbortError") setError(cause.message);
    });
    return () => controller.abort();
  }, [productId]);

  const ticket = tickets[0] || preview;
  const update = async (path, body) => {
    setBusy(true);
    try {
      const result = await request(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (result.mode) setMode(result.mode);
      if (result.ticket) {
        setTickets((current) => [result.ticket, ...current.filter((item) => item.id !== result.ticket.id)]);
        setPaperPrice("");
      }
      setError("");
    } catch (cause) {
      if ([401, 403].includes(cause.status)) setRestricted(true);
      else setError(cause.message);
    } finally {
      setBusy(false);
    }
  };

  if (restricted || (!mode && !error)) return null;
  const controls = (
    <section className="mw-panel" aria-label="Paper execution">
      <h3>Paper execution</h3>
      <p>Paper simulation only. No Coinbase orders are submitted.</p>
      {mode ? (
        <label>
          Execution mode{" "}
          <select aria-label="Execution mode" value={mode} disabled={busy}
            onChange={(event) => update("/api/execution-agent/mode", { mode: event.target.value })}>
            {MODES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
      ) : <p>Paper controls are available to the configured portfolio owner.</p>}
      {error ? <p role="alert">{error}</p> : null}
      {mode && ticket ? (
        <div aria-label="Paper order ticket">
          <strong>{ticket.product_id} · {display(ticket.status)}</strong>
          {ticket.multi_year_context?.is_multi_year && Number.isFinite(ticket.multi_year_context.cycle_range_position_pct) ? (
            <p>Cycle range: {Math.round(ticket.multi_year_context.cycle_range_position_pct)}% (latest daily close)</p>
          ) : null}
          <dl>
            <div><dt>Entry</dt><dd>{display(ticket.entry_price)}</dd></div>
            <div><dt>Stop Trigger</dt><dd>{display(ticket.stop_trigger_price)}</dd></div>
            <div><dt>Stop Limit</dt><dd>{display(ticket.stop_limit_price)}</dd></div>
            <div><dt>Target</dt><dd>{display(ticket.target_price)}</dd></div>
            <div><dt>Size USD</dt><dd>{display(ticket.notional_usd)}</dd></div>
            <div><dt>Planned R:R</dt><dd>{display(ticket.rr_planned)}</dd></div>
          </dl>
          {ticket.status === "staged_for_approval" ? (
            <button type="button" disabled={busy}
              onClick={() => update("/api/execution-agent/tickets", ticket.id
                ? { action: "approve", ticket_id: ticket.id }
                : { action: "stage", ticket })}>
              {ticket.id ? "Approve (Paper)" : "Stage (Paper)"}
            </button>
          ) : null}
          {ticket.id && ticket.side === "buy" && ["approved_paper", "auto_approved_autonomous", "filled_paper"].includes(ticket.status) ? (
            <div>
              <label>
                {ticket.status === "filled_paper" ? "Paper exit price" : "Paper fill price"}
                <input type="number" min="0" step="any" value={paperPrice}
                  onChange={(event) => setPaperPrice(event.target.value)} />
              </label>
              <button type="button" disabled={busy || !Number.isFinite(Number(paperPrice)) || Number(paperPrice) <= 0}
                onClick={() => update("/api/execution-agent/tickets", ticket.status === "filled_paper"
                  ? { action: "close", ticket_id: ticket.id, exit_price: Number(paperPrice) }
                  : { action: "fill", ticket_id: ticket.id, fill_price: Number(paperPrice) })}>
                {ticket.status === "filled_paper" ? "Close position (Paper)" : "Record fill (Paper)"}
              </button>
            </div>
          ) : null}
          {ticket.id && ["staged_for_approval", "approved_paper", "auto_approved_autonomous", "auto_approved_guardian"].includes(ticket.status) ? (
            <button type="button" disabled={busy}
              onClick={() => update("/api/execution-agent/tickets", { action: "cancel", ticket_id: ticket.id })}>
              Cancel ticket (Paper)
            </button>
          ) : null}
        </div>
      ) : mode ? <p>No paper ticket available.</p> : null}
    </section>
  );
  return collapsible ? <details className="cp-dossier-section"><summary>Owner paper controls</summary>{controls}</details> : controls;
}
