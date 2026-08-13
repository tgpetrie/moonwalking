import { useEffect, useState, useMemo } from "react";
import { getBackendBase } from "../config/api.js";
import { describeEvidenceTier } from "../mvp/portfolioSignals.js";
import "../styles/scorecard.css";

const API_BASE = getBackendBase();

function fmt(n, decimals = 1) {
  if (n == null) return "—";
  return (n * 100).toFixed(decimals) + "%";
}

function fmtPct(n, decimals = 2) {
  if (n == null) return "—";
  return n.toFixed(decimals) + "%";
}

function Tip({ text }) {
  return (
    <span className="sc-tip" title={text}>?</span>
  );
}

// Sample-depth wording, deliberately sharing no vocabulary with the event
// states rendered on the same card — "Building evidence" sat directly beside
// event-state "Building (early)" and read as a description of the move.
const EVIDENCE_LABELS = {
  strong:   "Deep evidence",
  solid:    "Solid evidence",
  building: "Thin evidence",
  emerging: "Emerging evidence",
};

export function evidenceTier(n) {
  const { key } = describeEvidenceTier(n);
  const label = EVIDENCE_LABELS[key] ?? null;
  return { label, tier: key };
}

function EvidenceTier({ n }) {
  const { label, tier } = evidenceTier(n);
  if (!label) return null;
  return (
    <span className="sc-evidence-tier" data-tier={tier}>{label}</span>
  );
}

const FRIENDLY_LABELS = {
  STRONG_BUY: "Strong Buy",
  BUY_WATCH: "Buy Watch",
  UNCLASSIFIED: "Unclassified",
  STRONG_SELL: "Strong Sell",
  SELL_WATCH: "Sell Watch",
  CAUTION: "Caution",
  NEUTRAL: "Neutral",
  WATCH: "Watch",
};

const FRIENDLY_STATES = {
  Confirmed: "Confirmed signal",
  Building: "Building (early)",
  Escalating: "Escalating",
  Cooling: "Cooling down",
};

const FRIENDLY_BOARDS = {
  ignition_1m: "1-Minute Ignition",
  confirmation_3m_up: "3-Minute Gainers",
  confirmation_3m_down: "3-Minute Losers",
};

const FRIENDLY_READS = {
  "Continuation edge": "Tends to keep moving",
  "Reversal tendency": "Tends to reverse",
  "No clear edge": "No clear pattern yet",
  "Learning": "Still collecting data",
};

function WinRateBar({ rate, recent, label, tip }) {
  const pct = rate != null ? Math.round(rate * 100) : 0;
  const recentPct = recent != null ? Math.round(recent * 100) : null;
  const color =
    pct >= 55
      ? "var(--brand-teal, #10ae9b)"
      : pct >= 45
        ? "var(--brand-amber, #ffb347)"
        : "var(--brand-purple, #c084fc)";

  return (
    <div className="sc-win-bar">
      <div className="sc-win-bar__label">
        {label}
        {tip && <Tip text={tip} />}
      </div>
      <div className="sc-win-bar__track">
        <div
          className="sc-win-bar__fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <div className="sc-win-bar__value" style={{ color }}>
        {pct}%
      </div>
      {recentPct != null && (
        <div className="sc-win-bar__recent">
          <span className="sc-win-bar__recent-label">Last 50</span>
          <span>{recentPct}%</span>
        </div>
      )}
    </div>
  );
}

function SignalCard({ card }) {
  const dirColor =
    card.direction === "up"
      ? "var(--brand-teal, #10ae9b)"
      : card.direction === "down"
        ? "var(--brand-purple, #c084fc)"
        : "var(--brand-amber, #ffb347)";

  const friendlyLabel = FRIENDLY_LABELS[card.label] || card.label;
  const friendlyState = FRIENDLY_STATES[card.state] || card.state;
  const dirLabel = card.direction === "up" ? "Bullish" : card.direction === "down" ? "Bearish" : "Neutral";

  return (
    <div className="sc-card">
      <div className="sc-card__header">
        <div className="sc-card__title">
          <span className="sc-card__label">{friendlyLabel}</span>
          <span className="sc-card__state">{friendlyState}</span>
        </div>
        <span
          className="sc-card__direction"
          style={{ color: dirColor, borderColor: dirColor }}
        >
          {dirLabel}
        </span>
      </div>

      <WinRateBar
        rate={card.win_rate}
        recent={card.recent_win_rate}
        label="Played out?"
        tip="How often the price moved in the predicted direction by the target amount within the time window"
      />

      <div className="sc-card__stats">
        <div className="sc-stat">
          <span className="sc-stat__label">
            Times tested
            <Tip text="How many times we've seen this exact signal type and graded the result" />
          </span>
          <span className="sc-stat__value">{card.sample_size.toLocaleString()}</span>
          <EvidenceTier n={card.sample_size} />
        </div>
        <div className="sc-stat">
          <span className="sc-stat__label">
            Best move (typical)
            <Tip text="The typical best price move in the signal's favor before the window closed" />
          </span>
          <span className="sc-stat__value sc-stat--positive">
            {fmtPct(card.median_favorable_pct)}
          </span>
        </div>
        <div className="sc-stat">
          <span className="sc-stat__label">
            Worst dip (typical)
            <Tip text="The typical worst price move against the signal before the window closed" />
          </span>
          <span className="sc-stat__value sc-stat--negative">
            {fmtPct(card.median_adverse_pct)}
          </span>
        </div>
      </div>

      <div className="sc-card__returns">
        <span className="sc-returns__title">
          Where price typically lands
          <Tip text="Typical price change at each checkpoint after this signal fires" />
        </span>
        <div className="sc-returns__grid">
          {[
            { key: "5m", label: "5 min" },
            { key: "15m", label: "15 min" },
            { key: "30m", label: "30 min" },
            { key: "60m", label: "1 hour" },
          ].map(({ key, label }) => (
            <div key={key} className="sc-returns__cell">
              <span className="sc-returns__time">{label}</span>
              <span
                className={`sc-returns__val ${
                  (card.median_return?.[key] ?? 0) >= 0
                    ? "sc-stat--positive"
                    : "sc-stat--negative"
                }`}
              >
                {fmtPct(card.median_return?.[key])}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function BoardCard({ board }) {
  if (!board || board.sample_size === 0) return null;

  const friendlyBoard = FRIENDLY_BOARDS[board.board] || board.board.replace(/_/g, " ");
  const friendlyRead = FRIENDLY_READS[board.read] || board.read;

  return (
    <div className="sc-card sc-card--board">
      <div className="sc-card__header">
        <div className="sc-card__title">
          <span className="sc-card__label">{friendlyBoard}</span>
          <span className="sc-card__state">{friendlyRead}</span>
        </div>
        <span
          className="sc-card__status-chip"
          data-status={board.status}
        >
          {board.status === "measured" ? "Ready" : "Learning"}
        </span>
      </div>

      <div className="sc-card__explainer">
        When a coin appears on this board, does the move keep going?
      </div>

      <div className="sc-card__stats">
        <div className="sc-stat">
          <span className="sc-stat__label">
            Times tested
          </span>
          <span className="sc-stat__value">{board.sample_size.toLocaleString()}</span>
          <EvidenceTier n={board.sample_size} />
        </div>
        <div className="sc-stat">
          <span className="sc-stat__label">
            Kept moving
            <Tip text="How often the price kept moving in the same direction after appearing on this board" />
          </span>
          <span className="sc-stat__value">{fmt(board.continuation_rate)}</span>
        </div>
        <div className="sc-stat">
          <span className="sc-stat__label">
            Reversed
            <Tip text="How often the price reversed direction after appearing on this board" />
          </span>
          <span className="sc-stat__value">{fmt(board.reversal_rate)}</span>
        </div>
        {board.continuation_lift_vs_control != null && (
          <div className="sc-stat">
            <span className="sc-stat__label">
              Edge vs random
              <Tip text="How much better (or worse) these coins perform compared to similar coins that didn't make the board" />
            </span>
            <span
              className={`sc-stat__value ${
                board.continuation_lift_vs_control >= 0
                  ? "sc-stat--positive"
                  : "sc-stat--negative"
              }`}
            >
              {board.continuation_lift_vs_control >= 0 ? "+" : ""}
              {fmt(board.continuation_lift_vs_control)}
            </span>
          </div>
        )}
      </div>

      {board.continuation_ci95 && (
        <div className="sc-card__ci">
          <span className="sc-ci__label">
            Confidence range
            <Tip text="We're 95% confident the true continuation rate falls within this range — wider means less certain" />
          </span>
          <span className="sc-ci__range">
            {fmt(board.continuation_ci95[0])} – {fmt(board.continuation_ci95[1])}
          </span>
        </div>
      )}

      <div className="sc-card__returns">
        <span className="sc-returns__title">
          Typical price move after hitting the board
        </span>
        <div className="sc-returns__grid">
          {[
            { key: "5m", label: "5 min" },
            { key: "15m", label: "15 min" },
            { key: "30m", label: "30 min" },
            { key: "60m", label: "1 hour" },
          ].map(({ key, label }) => {
            const val = board.median_directional_return?.[key];
            return (
              <div key={key} className="sc-returns__cell">
                <span className="sc-returns__time">{label}</span>
                <span
                  className={`sc-returns__val ${
                    (val ?? 0) >= 0 ? "sc-stat--positive" : "sc-stat--negative"
                  }`}
                >
                  {fmtPct(val)}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function ScorecardPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [sortBy, setSortBy] = useState("sample_size");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`${API_BASE}/api/scorecard`, {
          credentials: "include",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) setData(json);
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    }
    load();
    const interval = setInterval(load, 60_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const sortedSignals = useMemo(() => {
    if (!data?.signals?.signal_types) return [];
    const types = [...data.signals.signal_types];
    if (sortBy === "win_rate") {
      types.sort((a, b) => (b.win_rate ?? 0) - (a.win_rate ?? 0));
    } else if (sortBy === "recent") {
      types.sort(
        (a, b) => (b.recent_win_rate ?? 0) - (a.recent_win_rate ?? 0)
      );
    }
    return types;
  }, [data, sortBy]);

  const boards = useMemo(() => {
    if (!data?.boards?.boards) return [];
    return Object.values(data.boards.boards);
  }, [data]);

  if (error) {
    return (
      <div className="sc-page">
        <div className="sc-error">Failed to load scorecard: {error}</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="sc-page">
        <div className="sc-loading">Loading outcome scorecard…</div>
      </div>
    );
  }

  const sig = data.signals;

  return (
    <div className="sc-page">
      <div className="sc-hero">
        <h2 className="sc-hero__title">Outcome Scorecard</h2>
        <p className="sc-hero__subtitle">
          Are our alerts and board picks actually right? Here's the data.
        </p>
      </div>

      <div className="sc-explainer-box">
        Every time BHABIT fires a signal or a coin hits a board, we track what the price does over the next hour.
        Below you can see how often each signal type played out, and how the boards perform against random coins.
      </div>

      <div className="sc-overview">
        <div className="sc-overview__card">
          <span className="sc-overview__label">
            Signals graded
            <Tip text="Total number of completed signal outcomes we've measured" />
          </span>
          <span className="sc-overview__value">
            {sig.total_graded?.toLocaleString() ?? "—"}
          </span>
        </div>
        <div className="sc-overview__card">
          <span className="sc-overview__label">
            Overall follow-through
            <Tip text="Across all signal types, how often the price hit the target before hitting the stop" />
          </span>
          <span className="sc-overview__value">{fmt(sig.overall_win_rate)}</span>
        </div>
        <div className="sc-overview__card">
          <span className="sc-overview__label">
            Target move
            <Tip text="A signal 'wins' if the price moves this much in the right direction" />
          </span>
          <span className="sc-overview__value">+{sig.target_pct}%</span>
        </div>
        <div className="sc-overview__card">
          <span className="sc-overview__label">
            Stop level
            <Tip text="A signal 'loses' if the price moves this much in the wrong direction" />
          </span>
          <span className="sc-overview__value">-{sig.adverse_pct}%</span>
        </div>
        <div className="sc-overview__card">
          <span className="sc-overview__label">
            Time window
            <Tip text="How long we wait after a signal fires to grade the outcome" />
          </span>
          <span className="sc-overview__value">{sig.horizon_minutes} min</span>
        </div>
      </div>

      <section className="sc-section">
        <div className="sc-section__header">
          <h3>Signal Performance</h3>
          <div className="sc-sort">
            <button
              className={sortBy === "sample_size" ? "is-active" : ""}
              onClick={() => setSortBy("sample_size")}
            >
              Most tested
            </button>
            <button
              className={sortBy === "win_rate" ? "is-active" : ""}
              onClick={() => setSortBy("win_rate")}
            >
              Best follow-through
            </button>
            <button
              className={sortBy === "recent" ? "is-active" : ""}
              onClick={() => setSortBy("recent")}
            >
              Hot right now
            </button>
          </div>
        </div>
        <div className="sc-grid">
          {sortedSignals.map((card) => (
            <SignalCard
              key={`${card.state}-${card.direction}-${card.label}`}
              card={card}
            />
          ))}
          {sortedSignals.length === 0 && (
            <div className="sc-empty">
              No signal types with enough data yet — they need at least 5 outcomes to appear here.
            </div>
          )}
        </div>
      </section>

      <section className="sc-section">
        <div className="sc-section__header">
          <h3>Board Performance</h3>
        </div>
        <p className="sc-section__explainer">
          When a coin appears on one of the live boards (Ignition, Gainers, Losers), does the move
          tend to continue or reverse? We compare against similar coins that didn't make the board.
        </p>
        <div className="sc-grid">
          {boards.map((board) => (
            <BoardCard key={board.board} board={board} />
          ))}
          {boards.length === 0 && (
            <div className="sc-empty">No board outcome data yet.</div>
          )}
        </div>
      </section>
    </div>
  );
}
