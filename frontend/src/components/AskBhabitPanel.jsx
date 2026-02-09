import { useMemo, useState } from "react";
import { fetchData, getApiBaseUrl } from "../api.js";

const SYMBOL_RE = /\b[A-Z]{2,10}\b/g;

const extractSymbols = (query) => {
  const out = [];
  const seen = new Set();
  const tokens = String(query || "").toUpperCase().match(SYMBOL_RE) || [];
  for (const token of tokens) {
    if (["WHAT", "WITH", "FROM", "THIS", "THAT", "RIGHT", "NOW", "THE", "AND"].includes(token)) {
      continue;
    }
    if (!seen.has(token)) {
      seen.add(token);
      out.push(token);
    }
  }
  return out.slice(0, 8);
};

const fmtPct = (v) => {
  const n = Number(v);
  if (!Number.isFinite(n)) return "NA";
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
};

const fmtPx = (v) => {
  const n = Number(v);
  if (!Number.isFinite(n)) return "NA";
  return `$${n.toFixed(n >= 100 ? 2 : 4)}`;
};

export default function AskBhabitPanel() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("What is happening with BTC and SOL right now?");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const apiBase = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);
  const endpoint = `${apiBase}/api/ask-codex`;
  const mode = String(result?.mode || "deterministic").toUpperCase();
  const structured = result?.structured || {};
  const moved = Array.isArray(structured.what_moved) ? structured.what_moved : [];
  const riskFlags = Array.isArray(structured.risk_flags) ? structured.risk_flags : [];
  const levels = Array.isArray(structured.levels) ? structured.levels : [];

  const submit = async (e) => {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setError("");
    try {
      const data = await fetchData(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: q,
          symbols: extractSymbols(q),
          narrate: true,
        }),
      });
      setResult(data || null);
    } catch (err) {
      setError(err?.message || "Ask request failed");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bh-ask-dock" data-open={open ? "1" : "0"}>
      <button
        type="button"
        className="bh-ask-btn"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        title="Ask Bhabit"
      >
        <span className="bh-ask-btn-label">ASK BHABIT</span>
      </button>

      {open ? (
        <div className="bh-ask-panel" role="dialog" aria-label="Ask Bhabit">
          <div className="bh-ask-head">
            <div className="bh-ask-title">Ask Bhabit</div>
            <button type="button" className="bh-ask-close" onClick={() => setOpen(false)} aria-label="Close">
              x
            </button>
          </div>

          <form onSubmit={submit} className="bh-ask-form">
            <textarea
              className="bh-ask-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask about movers, alerts, risk, and levels..."
            />
            <div className="bh-ask-actions">
              <button type="submit" className="bh-ask-submit" disabled={loading || !query.trim()}>
                {loading ? "Asking..." : "Ask"}
              </button>
              <button
                type="button"
                className="bh-ask-clear"
                onClick={() => {
                  setQuery("");
                  setError("");
                  setResult(null);
                }}
              >
                Clear
              </button>
              <span className="bh-ask-mode">mode: {mode}</span>
            </div>
          </form>

          {error ? <div className="bh-ask-error">{error}</div> : null}

          {result ? (
            <div className="bh-ask-body">
              <div className="bh-ask-answer">{result.answer || result.reply || "No answer available."}</div>

              {moved.length > 0 ? (
                <div className="bh-ask-section">
                  <div className="bh-ask-section-title">What moved</div>
                  <div className="bh-ask-list">
                    {moved.slice(0, 6).map((row, idx) => (
                      <div key={`${row.symbol || "S"}-${idx}`} className="bh-ask-list-row">
                        <span>{row.symbol || "UNK"}</span>
                        <span>{fmtPct(row.change_1m ?? row.change_3m)}</span>
                        <span>{fmtPx(row.price_now)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {riskFlags.length > 0 ? (
                <div className="bh-ask-section">
                  <div className="bh-ask-section-title">Risk flags</div>
                  <div className="bh-ask-tags">
                    {riskFlags.slice(0, 5).map((item, idx) => (
                      <span key={`${idx}-${item}`} className="bh-ask-tag">
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}

              {levels.length > 0 ? (
                <div className="bh-ask-section">
                  <div className="bh-ask-section-title">Levels</div>
                  <div className="bh-ask-levels">
                    {levels.slice(0, 4).map((item, idx) => (
                      <div key={`${idx}-${item}`}>{item}</div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
