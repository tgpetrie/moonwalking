import { useCallback, useEffect, useMemo, useState } from "react";
import { getBackendBase } from "../config/api.js";
import { describeEvidenceTier } from "../mvp/portfolioSignals.js";
import "../styles/scorecard-redesign.css";

const API_BASE = getBackendBase();

// The coin the page opens on. Its history is fetched on arrival so the coin
// zone shows something real instead of an empty prompt.
const DEFAULT_COIN = "BTC";

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

function rate(value, digits = 0) {
  const n = Number(value);
  if (value == null || !Number.isFinite(n)) return "—";
  return `${(n * 100).toFixed(digits)}%`;
}

function signedRate(value, digits = 0) {
  const n = Number(value);
  if (value == null || !Number.isFinite(n)) return "—";
  return `${n >= 0 ? "+" : ""}${(n * 100).toFixed(digits)}%`;
}

function movePct(value, digits = 2) {
  const n = Number(value);
  if (value == null || !Number.isFinite(n)) return "—";
  return `${n.toFixed(digits)}%`;
}

function count(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString();
}

function normalizeCoinSymbol(value) {
  return String(value || "")
    .trim()
    .toUpperCase()
    .replace(/\s+/g, "")
    .replace(/\/USD$/, "-USD")
    .replace(/_USD$/, "-USD");
}

// ---------------------------------------------------------------------------
// Data provenance — demo, preview, and live must never be mistaken for each
// other, so each one gets its own chip, banner headline, and explanation.
// ---------------------------------------------------------------------------

export function resolveSource(previewMode, status) {
  if (previewMode) {
    return {
      key: "preview",
      chip: "Preview data",
      headline: "You are viewing preview data.",
      note:
        "These numbers are a fixed sample so the page can be explored without an account. Nothing here was measured from real outcomes.",
    };
  }
  if (status === "demo") {
    return {
      key: "demo",
      chip: "Demo data",
      headline: "You are viewing demo data.",
      note:
        "The server returned illustrative numbers instead of measured outcomes. Do not read anything into these results.",
    };
  }
  return {
    key: "live",
    chip: "Live data",
    headline: "You are viewing live data.",
    note:
      "Every number below was measured from real recorded outcomes. The page refreshes about once a minute.",
  };
}

// ---------------------------------------------------------------------------
// Plain-English vocabulary. Past tense throughout: this page reports what
// already happened, and must never read like a live call on the selected coin.
// ---------------------------------------------------------------------------

const SETUP_NAMES = {
  STRONG_BUY: "Strong Buy",
  BUY_WATCH: "Buy Watch",
  STRONG_SELL: "Strong Sell",
  SELL_WATCH: "Sell Watch",
  UNCLASSIFIED: "Unnamed setup",
  CAUTION: "Caution",
  NEUTRAL: "Neutral",
  WATCH: "Watch",
};

/**
 * Live payloads carry shouty internal constants the map above never sees —
 * "BREAKDOWN CONFIRMED", "MIXED — NO CLEAR EDGE", "STRONG_BUY". Rendering
 * those verbatim is the loudest kind of insider terminology, so anything
 * unmapped is turned into a sentence rather than left as a shout.
 */
export function humanizeLabel(label) {
  const known = SETUP_NAMES[label];
  if (known) return known;
  const raw = String(label ?? "").trim().replace(/_/g, " ");
  if (!raw) return "Unnamed setup";
  // Already mixed case means someone wrote it for a human. Leave it be.
  if (raw !== raw.toUpperCase()) return raw;
  const lower = raw.toLowerCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

const STATE_NAMES = {
  Confirmed: "Confirmed",
  Building: "Just forming",
  Escalating: "Getting stronger",
  Cooling: "Fading",
  "Reversal Risk": "Reversal risk",
};

const BOARD_NAMES = {
  ignition_1m: "1-Minute Ignition",
  confirmation_3m_up: "3-Minute Gainers",
  confirmation_3m_down: "3-Minute Losers",
};

const BOARD_BLURBS = {
  ignition_1m: "Coins that suddenly jump inside a single minute.",
  confirmation_3m_up: "Coins climbing steadily over three minutes.",
  confirmation_3m_down: "Coins falling steadily over three minutes.",
};

// Sample-depth wording. Deliberately shares no words with the setup states
// rendered on the same card, so "Building evidence" can never be confused with
// a "Building" signal state.
const EVIDENCE_LABELS = {
  strong: "Deep evidence",
  solid: "Solid evidence",
  building: "Thin evidence",
  emerging: "Barely tested",
};

const EVIDENCE_TRUST = {
  strong: "Tested enough times that the number is worth taking seriously.",
  solid: "Enough history to be useful, but not bulletproof.",
  building: "Thin history — read it as a hint, not a conclusion.",
  emerging: "Barely any history — don't lean on this number by itself.",
  none: "No completed outcomes yet, so there is nothing to trust or distrust.",
};

export function evidenceOf(sampleSize) {
  const { key } = describeEvidenceTier(sampleSize);
  return { tier: key, label: EVIDENCE_LABELS[key] ?? null, trust: EVIDENCE_TRUST[key] };
}

function directionPhrase(direction) {
  if (direction === "up") return "predicted the price would go up";
  if (direction === "down") return "predicted the price would go down";
  return "did not predict a direction";
}

function directionChip(direction) {
  if (direction === "up") return "Predicted a rise";
  if (direction === "down") return "Predicted a drop";
  return "No direction predicted";
}

function compareToBaseline(value, baseline) {
  if (value == null || !Number.isFinite(Number(value))) {
    return "Not enough data to compare this against the average yet.";
  }
  const diff = Number(value) - (Number(baseline) || 0);
  if (diff >= 0.1) return "Well ahead of the average signal.";
  if (diff >= 0.03) return "A little better than the average signal.";
  if (diff <= -0.1) return "Well behind the average signal.";
  if (diff <= -0.03) return "A little worse than the average signal.";
  return "About the same as the average signal.";
}

function signalAction(card, baseline) {
  const { tier } = evidenceOf(card?.sample_size);
  const better = Number(card?.win_rate) - (Number(baseline) || 0) >= 0.03;
  if (tier === "emerging" || tier === "none") {
    return "Leave it alone for now. Come back once it has been tested more times.";
  }
  if (better && (tier === "strong" || tier === "solid")) {
    return "Worth watching for on the live board. When one of these fires, open the coin's live read before doing anything.";
  }
  if (better) {
    return "Promising, but thin. Track it for a while before you let it change a decision.";
  }
  return "Not a reason to act on its own. If you see this setup, look for other confirmation first.";
}

function boardAction(board) {
  const lift = Number(board?.continuation_lift_vs_control);
  if (board?.status !== "measured") {
    return "Still gathering history. Use this board as a watchlist, not as a conclusion.";
  }
  if (Number.isFinite(lift) && lift >= 0.03) {
    return "Coins here have genuinely tended to keep moving. Use it as a starting point, then check the coin's live read.";
  }
  if (Number.isFinite(lift) && lift <= -0.01) {
    return "Coins here have done worse than similar coins that never appeared. Treat an appearance as noise, not a buy signal.";
  }
  return "Appearing on this board has not beaten picking a similar coin at random. Don't treat it as a buy signal by itself.";
}

function boardHeadline(board) {
  const cont = Number(board?.continuation_rate);
  const rev = Number(board?.reversal_rate);
  if (!Number.isFinite(cont)) return "Not enough history to describe this board yet.";
  if (Number.isFinite(rev) && rev > cont + 0.05) {
    return "Moves here have flipped more often than they continued.";
  }
  if (cont >= 0.5) return "Moves here have usually kept going.";
  if (cont >= 0.35) return "Moves here have kept going some of the time.";
  return "Moves here have usually run out of steam.";
}

function stateMeaning(state) {
  switch (state) {
    case "Escalating":
      return "the setup was strengthening as it ran";
    case "Building":
      return "the setup had only just formed";
    case "Cooling":
      return "the setup was fading out";
    case "Confirmed":
      return "the setup had been confirmed by follow-up checks";
    case "Reversal Risk":
      return "the setup was warning that the move might flip";
    default:
      return "the setup had reached this stage";
  }
}

/**
 * Two categories currently on screen that point opposite ways — the pairing
 * that reads as a contradiction. Naming a real pair beats naming an invented
 * one; returns null when the data does not offer both directions.
 */
function opposingPair(cards) {
  const list = Array.isArray(cards) ? cards : [];
  const up = list.find((card) => card?.direction === "up");
  const down = list.find((card) => card?.direction === "down");
  if (!up || !down) return null;
  return [humanizeLabel(up.label), humanizeLabel(down.label)];
}

function coinSummarySentence(data) {
  const total = Number(data?.total_outcomes ?? 0);
  if (!Number.isFinite(total) || total <= 0) {
    return "We haven't finished measuring any signals on this coin yet.";
  }
  if (total < 20) {
    return `Only ${count(total)} measured signals so far — too few to put a number on.`;
  }
  const first = Number(data?.signal_types?.[0]?.win_rate);
  if (!Number.isFinite(first)) {
    return `${count(total)} measured signals so far.`;
  }
  return `${count(total)} measured signals — the most common setup worked ${rate(first)} of the time.`;
}

// ---------------------------------------------------------------------------
// Aggregation
// ---------------------------------------------------------------------------

function trustScore(card) {
  const win = Number(card?.win_rate);
  const sample = Number(card?.sample_size);
  if (!Number.isFinite(win)) return -1;
  const weight = Number.isFinite(sample) ? Math.min(1, sample / 100) : 0;
  return win * (0.35 + 0.65 * weight);
}

function groupSignalsByState(cards) {
  const groups = new Map();
  for (const card of Array.isArray(cards) ? cards : []) {
    const key = String(card?.state || "Unknown");
    if (!groups.has(key)) {
      groups.set(key, { state: key, card_count: 0, sample_size: 0, win_weight: 0 });
    }
    const bucket = groups.get(key);
    const sample = Number(card?.sample_size);
    const win = Number(card?.win_rate);
    bucket.card_count += 1;
    if (Number.isFinite(sample)) bucket.sample_size += sample;
    if (Number.isFinite(sample) && Number.isFinite(win)) bucket.win_weight += sample * win;
  }
  return [...groups.values()]
    .map((bucket) => ({
      ...bucket,
      weighted_win_rate: bucket.sample_size > 0 ? bucket.win_weight / bucket.sample_size : null,
    }))
    .sort((a, b) => b.sample_size - a.sample_size);
}

function groupBoardsByStatus(boards) {
  const groups = new Map();
  for (const board of Array.isArray(boards) ? boards : []) {
    const key = String(board?.status || "unknown");
    if (!groups.has(key)) {
      groups.set(key, { status: key, card_count: 0, sample_size: 0, continuation_weight: 0 });
    }
    const bucket = groups.get(key);
    const sample = Number(board?.sample_size);
    const cont = Number(board?.continuation_rate);
    bucket.card_count += 1;
    if (Number.isFinite(sample)) bucket.sample_size += sample;
    if (Number.isFinite(sample) && Number.isFinite(cont)) {
      bucket.continuation_weight += sample * cont;
    }
  }
  return [...groups.values()]
    .map((bucket) => ({
      ...bucket,
      weighted_continuation_rate:
        bucket.sample_size > 0 ? bucket.continuation_weight / bucket.sample_size : null,
    }))
    .sort((a, b) => b.sample_size - a.sample_size);
}

// Local copy of the demo payload. The original ScorecardPage keeps its own so
// that the baseline page stays byte-for-byte comparable with this redesign.
const DEMO_SCORECARD = {
  status: "demo",
  signals: {
    total_graded: 1500,
    overall_win_rate: 0.21,
    target_pct: 2.0,
    adverse_pct: 1.0,
    horizon_minutes: 60,
    signal_types: [
      {
        state: "Escalating",
        direction: "up",
        label: "STRONG_BUY",
        sample_size: 55,
        win_rate: 0.62,
        recent_win_rate: 0.58,
        recent_sample: 18,
        median_favorable_pct: 2.6,
        median_adverse_pct: -1.0,
        median_return: { "5m": 0.6, "15m": 0.9, "30m": 1.3, "60m": 1.9 },
      },
      {
        state: "Building",
        direction: "up",
        label: "WATCH",
        sample_size: 15,
        win_rate: 0.34,
        recent_win_rate: 0.31,
        recent_sample: 8,
        median_favorable_pct: 1.1,
        median_adverse_pct: -0.8,
        median_return: { "5m": 0.1, "15m": 0.2, "30m": 0.0, "60m": -0.3 },
      },
      {
        state: "Reversal Risk",
        direction: "down",
        label: "CAUTION",
        sample_size: 200,
        win_rate: 0.18,
        recent_win_rate: 0.14,
        recent_sample: 50,
        median_favorable_pct: 1.8,
        median_adverse_pct: -0.8,
        median_return: { "5m": 0.3, "15m": 0.5, "30m": -0.2, "60m": -0.8 },
      },
    ],
  },
  boards: {
    total_entries: 300,
    boards: {
      ignition_1m: {
        board: "ignition_1m",
        status: "measured",
        read: "No clear edge",
        sample_size: 150,
        matched_sample_size: 130,
        continuation_rate: 0.18,
        reversal_rate: 0.2,
        continuation_ci95: [0.12, 0.24],
        continuation_lift_vs_control: -0.02,
        median_directional_return: { "5m": -0.1, "15m": -0.2, "30m": 0.1, "60m": 0.3 },
      },
      confirmation_3m_up: {
        board: "confirmation_3m_up",
        status: "learning",
        read: "Tends to keep moving",
        sample_size: 45,
        matched_sample_size: 40,
        continuation_rate: 0.44,
        reversal_rate: 0.31,
        continuation_ci95: [0.33, 0.55],
        continuation_lift_vs_control: 0.08,
        median_directional_return: { "5m": 0.2, "15m": 0.4, "30m": 0.6, "60m": 0.9 },
      },
    },
  },
};

async function fetchCoinHistory(normalizedSymbol) {
  const res = await fetch(`${API_BASE}/api/coin-history/${encodeURIComponent(normalizedSymbol)}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Shared pieces
// ---------------------------------------------------------------------------

/**
 * One visual zone of the page. Each zone states what it measures, why it
 * matters, and what a user can do with it, so the four kinds of information on
 * this page (coin context, signal history, board history, internal diagnostics)
 * never blur into each other.
 */
function Zone({ step, title, tone, lede, children }) {
  return (
    <section className="scr-zone" data-tone={tone}>
      <header className="scr-zone__head">
        <span className="scr-zone__step" aria-hidden="true">
          {step}
        </span>
        <h3 className="scr-zone__title">{title}</h3>
      </header>
      <div className="scr-zone__body">
        {lede ? <p className="scr-zone__lede">{lede}</p> : null}
        {children}
      </div>
    </section>
  );
}

function CheckpointGrid({ values, title }) {
  return (
    <div className="scr-checkpoints">
      <span className="scr-checkpoints__title">{title}</span>
      <div className="scr-checkpoints__grid">
        {[
          { key: "5m", label: "5 min" },
          { key: "15m", label: "15 min" },
          { key: "30m", label: "30 min" },
          { key: "60m", label: "1 hour" },
        ].map(({ key, label }) => {
          const val = values?.[key];
          return (
            <div key={key} className="scr-checkpoints__cell">
              <span className="scr-checkpoints__time">{label}</span>
              <span
                className={`scr-checkpoints__val ${
                  Number(val ?? 0) >= 0 ? "scr-up" : "scr-down"
                }`}
              >
                {movePct(val)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cards
// ---------------------------------------------------------------------------

/**
 * The four questions every scored item has to answer: what it is, how it
 * compares, what to do about it, and what the move actually looked like.
 *
 * `showCount` drops the sample-size sentence for callers whose own layout
 * already prints it (the gauge tiles carry it as a stat).
 */
function SetupDetail({ card, baseline, name, showCount = true }) {
  const { trust } = evidenceOf(card.sample_size);
  return (
    <div className="scr-detail__grid">
      <div>
        <span className="scr-detail__dt">What this is</span>
        <p>
          Every past time BHABIT called a &ldquo;{name}&rdquo; while {stateMeaning(card.state)}, we
          followed the price and recorded whether it did what the signal{" "}
          {directionPhrase(card.direction)}.
        </p>
      </div>
      <div>
        <span className="scr-detail__dt">How it compares</span>
        <p>
          {compareToBaseline(card.win_rate, baseline)} {trust}
        </p>
      </div>
      <div>
        <span className="scr-detail__dt">What to do with it</span>
        <p>{signalAction(card, baseline)}</p>
      </div>
      <div>
        <span className="scr-detail__dt">Typical move</span>
        <p>
          {showCount ? `Called ${count(card.sample_size)} times. ` : null}Best in its favor{" "}
          <span className="scr-up">{movePct(card.median_favorable_pct)}</span>, worst against it{" "}
          <span className="scr-down">{movePct(card.median_adverse_pct)}</span>.
        </p>
        <CheckpointGrid values={card.median_return} title="Price after it fired" />
      </div>
    </div>
  );
}

/** `showReversal` is off for the gauge tiles, which print "Flipped" as a stat. */
function BoardDetail({ board, name, showReversal = true }) {
  const lift = Number(board.continuation_lift_vs_control);
  const { trust } = evidenceOf(board.sample_size);
  return (
    <div className="scr-detail__grid">
      <div>
        <span className="scr-detail__dt">What this is</span>
        <p>
          {boardHeadline(board)} Every time a coin landed on {name}, we followed the price for the
          next hour and recorded whether the move continued or flipped.
        </p>
      </div>
      <div>
        <span className="scr-detail__dt">Beat random?</span>
        <p>
          {Number.isFinite(lift)
            ? "Landing here changed the odds by " +
              signedRate(lift) +
              " against similar coins that never made the board. That gap, not the raw percentage, is what says the board is doing real work."
            : "Not enough matched history to compare against similar coins yet."}
        </p>
      </div>
      <div>
        <span className="scr-detail__dt">When to trust it</span>
        <p>
          {trust}
          {showReversal ? ` Flipped instead ${rate(board.reversal_rate)} of the time.` : null}
        </p>
      </div>
      <div>
        <span className="scr-detail__dt">What to do with it</span>
        <p>{boardAction(board)}</p>
        <CheckpointGrid
          values={board.median_directional_return}
          title="Price after landing on the board"
        />
      </div>
    </div>
  );
}

/**
 * A donut gauge. The filled arc is the percentage, so the number is the shape —
 * you read the result before you read any words.
 */
function Donut({ value, tone, size = 78, stroke = 9 }) {
  const pct = Number.isFinite(Number(value)) ? Math.max(0, Math.min(1, Number(value))) : 0;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <svg
      className="scr-donut"
      width={size}
      height={size}
      viewBox={"0 0 " + size + " " + size}
      role="img"
      aria-label={Math.round(pct * 100) + " percent"}
    >
      <circle
        className="scr-donut__track"
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        strokeWidth={stroke}
      />
      <circle
        className="scr-donut__arc"
        data-tone={tone}
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={c * pct + " " + c}
        transform={"rotate(-90 " + size / 2 + " " + size / 2 + ")"}
      />
      <text className="scr-donut__value" x="50%" y="50%" data-tone={tone}>
        {Math.round(pct * 100)}%
      </text>
    </svg>
  );
}

/**
 * One scored item.
 *
 * These were cards, then a table. Cards read as three competing verdicts on the
 * selected coin; the table read as a spreadsheet. A gauge reads as a score —
 * which is what it is — and the arc carries the magnitude before any word does.
 */
function ScoreTile({ tone, value, name, sub, metric, stats, detail, status }) {
  const [open, setOpen] = useState(false);
  return (
    <article className={"scr-tile" + (open ? " is-open" : "")}>
      <div className="scr-tile__main">
        <Donut value={value} tone={tone} />
        <div className="scr-tile__body">
          <h4 className="scr-tile__name">
            <span className="scr-tile__dot" data-tone={tone} aria-hidden="true" />
            {name}
          </h4>
          <p className="scr-tile__sub">{sub}</p>
          <p className="scr-tile__metric">{metric}</p>
          {status ? <div className="scr-tile__status">{status}</div> : null}
        </div>
      </div>

      <dl className="scr-tile__stats">
        {stats.map((stat) => (
          <div key={stat.label}>
            <dt>{stat.label}</dt>
            <dd className={stat.tone ? "scr-" + stat.tone : undefined}>{stat.value}</dd>
          </div>
        ))}
      </dl>

      <button
        type="button"
        className="scr-tile__toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "Hide detail" : "Detail"}
      </button>

      {open ? <div className="scr-tile__detail">{detail}</div> : null}
    </article>
  );
}

function SetupTile({ card, baseline }) {
  const name = humanizeLabel(card.label);
  const state = STATE_NAMES[card.state] || card.state;
  const { label: evidenceLabel } = evidenceOf(card.sample_size);
  const winPct = Number(card.win_rate);
  const tone = winPct >= 0.5 ? "good" : winPct >= 0.3 ? "mixed" : "weak";

  return (
    <ScoreTile
      tone={tone}
      value={card.win_rate}
      name={name}
      sub={state + " \u00b7 " + directionChip(card.direction)}
      metric="of these calls worked out"
      stats={[
        { label: "Times called", value: count(card.sample_size) },
        { label: "Recent 50", value: rate(card.recent_win_rate) },
        { label: "Evidence", value: evidenceLabel || "\u2014" },
      ]}
      detail={<SetupDetail card={card} baseline={baseline} name={name} showCount={false} />}
    />
  );
}

function BoardTile({ board }) {
  const name = BOARD_NAMES[board.board] || String(board.board || "").replace(/_/g, " ");
  const blurb = BOARD_BLURBS[board.board] || "Coins that met this board's entry rule.";
  const ready = board.status === "measured";
  const lift = Number(board.continuation_lift_vs_control);
  const cont = Number(board.continuation_rate);
  const tone = cont >= 0.5 ? "good" : cont >= 0.35 ? "mixed" : "weak";
  const { label: evidenceLabel } = evidenceOf(board.sample_size);

  return (
    <ScoreTile
      tone={tone}
      value={board.continuation_rate}
      name={name}
      sub={blurb}
      metric="of moves kept going"
      status={
        <span className="scr-status" data-status={board.status}>
          {ready ? "Enough history" : "Still learning"}
        </span>
      }
      stats={[
        { label: "Flipped", value: rate(board.reversal_rate) },
        {
          label: "vs. random",
          value: Number.isFinite(lift) ? signedRate(lift) : "\u2014",
          tone: Number.isFinite(lift) ? (lift >= 0 ? "up" : "down") : null,
        },
        { label: "Evidence", value: evidenceLabel || "\u2014" },
      ]}
      detail={<BoardDetail board={board} name={name} showReversal={false} />}
    />
  );
}

// ---------------------------------------------------------------------------
// Chart treatments
//
// Three ways to render the same scores, switchable at runtime so the shape can
// be chosen by looking rather than by arguing:
//   bars   - one panel, one bar per category, average marked. Best for
//            comparing independent rates against each other.
//   split  - one sectioned pie of how often each category was called, with the
//            accuracy read out beside each slice.
//   gauges - a donut per category.
// ---------------------------------------------------------------------------

const SLICE_COLORS = [
  "var(--brand-teal, #10ae9b)",
  "var(--brand-amber, #ffb347)",
  "var(--brand-purple, #c084fc)",
  "#5eead4",
  "#fca5a5",
  "#93c5fd",
];

function toneOf(value, good = 0.5, mixed = 0.3) {
  if (value == null || !Number.isFinite(Number(value))) return "none";
  const n = Number(value);
  return n >= good ? "good" : n >= mixed ? "mixed" : "weak";
}

// A live payload can carry twenty-odd categories. Showing them all at once is
// the density the redesign exists to fix, so the tail is folded away.
const BARS_VISIBLE = 8;

/** One shared panel, one bar per category, with the average marked. */
function SignalBars({ items, baseline, onSelect, selected }) {
  const [showAll, setShowAll] = useState(false);
  const avg = Number(baseline);
  // `Number(null)` is 0, which is finite — so a missing baseline would draw a
  // meaningless "avg 0%" line at the left edge. Check for absence first.
  const hasAvg = baseline != null && Number.isFinite(avg);

  const shown = showAll ? items : items.slice(0, BARS_VISIBLE);
  // Collapsing must not hide the row whose detail is open below the chart.
  const visible =
    selected && !shown.some((item) => item.key === selected)
      ? [...shown, items.find((item) => item.key === selected)].filter(Boolean)
      : shown;
  const hiddenCount = items.length - visible.length;

  return (
    <div className="scr-chart">
      <div className="scr-bars">
        {hasAvg ? (
          <div
            className="scr-bars__avg"
            style={{ left: `${Math.max(0, Math.min(100, avg * 100))}%` }}
          >
            <span className="scr-bars__avg-label">avg {rate(avg)}</span>
          </div>
        ) : null}

        {visible.map((item, i) => {
          const tone = toneOf(item.value);
          const pct =
            item.value == null ? 0 : Math.max(0, Math.min(100, Number(item.value) * 100 || 0));
          const isOpen = selected === item.key;
          return (
            <button
              type="button"
              key={item.key}
              className={"scr-barrow" + (isOpen ? " is-open" : "")}
              aria-expanded={isOpen}
              onClick={() => onSelect(isOpen ? null : item.key)}
            >
              <span className="scr-barrow__label">
                <span
                  className="scr-barrow__dot"
                  style={{ background: SLICE_COLORS[i % SLICE_COLORS.length] }}
                  aria-hidden="true"
                />
                <span className="scr-barrow__name">{item.name}</span>
                <span className="scr-barrow__sub">{item.sub}</span>
              </span>
              <span className="scr-barrow__track">
                <span
                  className="scr-barrow__fill"
                  data-tone={tone}
                  style={{ width: `${pct}%` }}
                />
              </span>
              <span className="scr-barrow__pct" data-tone={tone}>
                {rate(item.value)}
              </span>
            </button>
          );
        })}
      </div>

      {items.length > BARS_VISIBLE ? (
        <button
          type="button"
          className="scr-bars__more"
          aria-expanded={showAll}
          onClick={() => setShowAll((v) => !v)}
        >
          {showAll
            ? `Show the top ${BARS_VISIBLE} only`
            : `Show all ${items.length} categories (${hiddenCount} more)`}
        </button>
      ) : null}
    </div>
  );
}

/**
 * What to show when nothing has finished yet.
 *
 * An empty chart is theatre: it implies we measured something and found
 * nothing. In fact collection is simply still running, and the honest,
 * useful thing to show is how far along it is.
 */
function CollectingPanel({ progress, noun = "signals" }) {
  if (!progress) return null;
  const total = Number(progress.total) || 0;
  const complete = Number(progress.complete) || 0;
  const collecting = Number(progress.collecting) || Math.max(0, total - complete);
  const horizon = Number(progress.horizon_minutes) || 60;
  const pct = total > 0 ? complete / total : 0;

  return (
    <div className="scr-collecting">
      <div className="scr-collecting__head">
        <span className="scr-collecting__title">Still collecting</span>
        <span className="scr-collecting__count">
          {count(complete)} of {count(total)} graded
        </span>
      </div>
      <div className="scr-collecting__track">
        <div className="scr-collecting__fill" style={{ width: `${pct * 100}%` }} />
      </div>
      <p className="scr-collecting__note">
        {count(collecting)} {noun} recorded and waiting. Each one is graded{" "}
        {horizon} minutes after it fires, so the first results appear up to{" "}
        {horizon} minutes after collection starts. Nothing is wrong — there is
        simply nothing finished to score yet.
      </p>
    </div>
  );
}

/** Annular sector path — the wedge of a donut between two angles. */
function ringPath(cx, cy, rOuter, rInner, a0, a1) {
  const p = (r, a) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  const [x0o, y0o] = p(rOuter, a0);
  const [x1o, y1o] = p(rOuter, a1);
  const [x1i, y1i] = p(rInner, a1);
  const [x0i, y0i] = p(rInner, a0);
  const large = a1 - a0 > Math.PI ? 1 : 0;
  return [
    "M", x0o, y0o,
    "A", rOuter, rOuter, 0, large, 1, x1o, y1o,
    "L", x1i, y1i,
    "A", rInner, rInner, 0, large, 0, x0i, y0i,
    "Z",
  ].join(" ");
}

/**
 * Sectioned donut. Segments are separated by real gaps and the selected one
 * lifts out of the ring, so a section can be singled out while the rest of its
 * numbers are read alongside it.
 *
 * Depth comes from gradients and a drop shadow rather than a perspective tilt:
 * tilting a pie foreshortens the far segments and makes equal shares look
 * unequal, which would defeat the point of showing shares at all.
 */
function SignalPie({ items, onSelect, selected, centerLabel, centerSub }) {
  const total = items.reduce((sum, item) => sum + (Number(item.weight) || 0), 0);
  const size = 300;
  const cx = size / 2;
  const cy = size / 2;
  const rOuter = 128;
  const rInner = 78;
  const gap = 0.045;
  const lift = 13;

  if (total <= 0) {
    return (
      <svg
        className="scr-pie"
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label="Nothing measured yet"
      >
        <circle
          className="scr-pie__empty"
          cx={cx}
          cy={cy}
          r={(rOuter + rInner) / 2}
          fill="none"
          strokeWidth={rOuter - rInner}
        />
        <text className="scr-pie__center" x={cx} y={cy - 7}>
          0
        </text>
        <text className="scr-pie__centersub" x={cx} y={cy + 13}>
          nothing measured yet
        </text>
      </svg>
    );
  }

  let angle = -Math.PI / 2;
  const slices = items.map((item, i) => {
    const share = total > 0 ? (Number(item.weight) || 0) / total : 0;
    const sweep = share * Math.PI * 2;
    const a0 = angle + gap / 2;
    const a1 = angle + sweep - gap / 2;
    angle += sweep;
    const mid = (a0 + a1) / 2;
    const color = SLICE_COLORS[i % SLICE_COLORS.length];
    const isSel = selected === item.key;
    const dx = isSel ? Math.cos(mid) * lift : 0;
    const dy = isSel ? Math.sin(mid) * lift : 0;
    const labelR = (rOuter + rInner) / 2;
    return {
      ...item,
      share,
      color,
      isSel,
      dx,
      dy,
      d: a1 > a0 ? ringPath(cx, cy, rOuter, rInner, a0, a1) : "",
      lx: cx + labelR * Math.cos(mid) + dx,
      ly: cy + labelR * Math.sin(mid) + dy,
      gradId: `scrgrad-${i}`,
    };
  });

  return (
    <svg
      className="scr-pie"
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label="Share of calls by category"
    >
      <defs>
        {slices.map((slice) => (
          <radialGradient
            key={slice.gradId}
            id={slice.gradId}
            cx="50%"
            cy="50%"
            r="72%"
          >
            <stop offset="55%" stopColor={slice.color} stopOpacity="0.62" />
            <stop offset="100%" stopColor={slice.color} stopOpacity="1" />
          </radialGradient>
        ))}
        <filter id="scr-pie-shadow" x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="0" dy="5" stdDeviation="7" floodColor="#000" floodOpacity="0.5" />
        </filter>
      </defs>

      <g filter="url(#scr-pie-shadow)">
        {slices.map((slice) =>
          slice.d ? (
            <path
              key={slice.key}
              d={slice.d}
              fill={`url(#${slice.gradId})`}
              className={"scr-pie__slice" + (slice.isSel ? " is-selected" : "")}
              style={{ transform: `translate(${slice.dx}px, ${slice.dy}px)` }}
              opacity={selected && !slice.isSel ? 0.32 : 1}
              onClick={() => onSelect(slice.isSel ? null : slice.key)}
            />
          ) : null
        )}
      </g>

      {slices.map((slice) =>
        slice.share >= 0.07 ? (
          <text
            key={`${slice.key}-label`}
            className="scr-pie__label"
            x={slice.lx}
            y={slice.ly}
            opacity={selected && !slice.isSel ? 0.4 : 1}
          >
            {rate(slice.share)}
          </text>
        ) : null
      )}

      <text className="scr-pie__center" x={cx} y={cy - 7}>
        {centerLabel}
      </text>
      <text className="scr-pie__centersub" x={cx} y={cy + 13}>
        {centerSub}
      </text>
    </svg>
  );
}

/**
 * The legend doubles as the place a selected section is blown up.
 *
 * Its headline number is the slice size, so legend and chart always agree.
 * Accuracy is a different question and is labelled as one.
 */
function PieLegend({ items, selected, onSelect, detailFor }) {
  const total = items.reduce((sum, item) => sum + (Number(item.weight) || 0), 0);
  return (
    <ul className="scr-legend">
      {items.map((item, i) => {
        const color = SLICE_COLORS[i % SLICE_COLORS.length];
        const isSel = selected === item.key;
        const share = total > 0 ? (Number(item.weight) || 0) / total : 0;
        return (
          <li key={item.key} className={"scr-legend__item" + (isSel ? " is-open" : "")}>
            <button
              type="button"
              className="scr-legend__row"
              aria-expanded={isSel}
              onClick={() => onSelect(isSel ? null : item.key)}
            >
              <span className="scr-legend__swatch" style={{ background: color }} />
              <span className="scr-legend__text">
                <span className="scr-legend__name">{item.name}</span>
                <span className="scr-legend__sub">
                  {count(item.weight)} of {count(total)} ·{" "}
                  {item.value == null ? "not graded yet" : `worked ${rate(item.value)} of the time`}
                </span>
              </span>
              <span className="scr-legend__pct">
                {rate(share)}
                <span className="scr-legend__pct-label">of calls</span>
              </span>
            </button>
            {isSel ? <div className="scr-legend__detail">{detailFor(item)}</div> : null}
          </li>
        );
      })}
    </ul>
  );
}

const CHART_STYLES = [
  { key: "bars", label: "Bars" },
  { key: "split", label: "Volume mix" },
  { key: "gauges", label: "Gauges" },
];

function ChartStyleSwitch({ value, onChange }) {
  return (
    <div className="scr-chartswitch" role="group" aria-label="Chart style">
      <span className="scr-chartswitch__label">Chart</span>
      {CHART_STYLES.map((style) => (
        <button
          key={style.key}
          type="button"
          className={"scr-chartswitch__btn" + (value === style.key ? " is-active" : "")}
          aria-pressed={value === style.key}
          onClick={() => onChange(style.key)}
        >
          {style.label}
        </button>
      ))}
    </div>
  );
}

/** Renders a scored group in whichever treatment is selected. */
function ScoreGroup({ items, baseline, style, detailFor, centerLabel, centerSub }) {
  const [selected, setSelected] = useState(null);
  const active = items.find((item) => item.key === selected);

  if (style === "gauges") {
    return <div className="scr-tiles">{items.map((item) => item.gauge)}</div>;
  }

  if (style === "split") {
    return (
      <div className="scr-chart scr-chart--split">
        <div className="scr-piewrap">
          <span className="scr-piewrap__caption">Share of calls made — not accuracy</span>
            <SignalPie
            items={items}
            onSelect={setSelected}
            selected={selected}
            centerLabel={centerLabel}
            centerSub={centerSub}
          />
        </div>
        <PieLegend
          items={items}
          selected={selected}
          onSelect={setSelected}
          detailFor={detailFor}
        />
      </div>
    );
  }

  return (
    <>
      <SignalBars
        items={items}
        baseline={baseline}
        onSelect={setSelected}
        selected={selected}
      />
      {active ? <div className="scr-groupdetail">{detailFor(active)}</div> : null}
    </>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ScorecardRedesignPage({ previewMode = false } = {}) {
  const [data, setData] = useState(() => (previewMode ? DEMO_SCORECARD : null));
  const [error, setError] = useState(null);
  const [showingLive, setShowingLive] = useState(!previewMode);
  const [progress, setProgress] = useState(null);
  const [order, setOrder] = useState("trust");
  const [chartStyle, setChartStyle] = useState("bars");
  const [coinInput, setCoinInput] = useState(DEFAULT_COIN);
  const [coinHistory, setCoinHistory] = useState(null);
  const [coinError, setCoinError] = useState(null);
  const [coinLoading, setCoinLoading] = useState(false);
  const [coinLoadedFor, setCoinLoadedFor] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`${API_BASE}/api/scorecard`, { credentials: "include" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (cancelled) return;
        // A preview page showing an empty live payload is worse than a
        // representative sample, so keep the sample until real outcomes exist —
        // and only claim "live" once we are actually showing live numbers.
        const liveHasData =
          Number(json?.signals?.total_graded) > 0 ||
          Number(json?.boards?.total_entries) > 0;
        if (!previewMode || liveHasData) {
          setData(json);
          setShowingLive(true);
        }
      } catch (e) {
        if (!cancelled && !previewMode) setError(e.message);
      }
    }
    async function loadProgress() {
      try {
        const res = await fetch(`${API_BASE}/api/signals/outcomes/status`, {
          credentials: "include",
        });
        if (!res.ok) return;
        const json = await res.json();
        if (!cancelled) setProgress(json);
      } catch {
        /* progress is a nicety; never let it break the page */
      }
    }
    load();
    loadProgress();
    const interval = setInterval(() => {
      load();
      loadProgress();
    }, 60_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [previewMode]);

  const signals = useMemo(() => {
    const types = Array.isArray(data?.signals?.signal_types)
      ? [...data.signals.signal_types]
      : [];
    if (order === "worked") {
      types.sort((a, b) => (Number(b.win_rate) || 0) - (Number(a.win_rate) || 0));
    } else if (order === "tested") {
      types.sort((a, b) => (Number(b.sample_size) || 0) - (Number(a.sample_size) || 0));
    } else {
      types.sort((a, b) => trustScore(b) - trustScore(a));
    }
    return types;
  }, [data, order]);

  const baselineRate = Number(data?.signals?.overall_win_rate);
  const coinBaseline = Number(coinHistory?.overall_win_rate ?? baselineRate);

  const boards = useMemo(
    () => (data?.boards?.boards ? Object.values(data.boards.boards) : []),
    [data]
  );

  const readyBoards = boards.filter((board) => board?.status === "measured").length;
  const stateGroups = useMemo(() => groupSignalsByState(signals), [signals]);
  const boardGroups = useMemo(() => groupBoardsByStatus(boards), [boards]);

  const bestSetup = useMemo(() => {
    if (!signals.length) return null;
    return [...signals].sort((a, b) => trustScore(b) - trustScore(a))[0];
  }, [signals]);

  const opposing = useMemo(() => opposingPair(signals), [signals]);

  const coinCards = useMemo(() => {
    const cards = Array.isArray(coinHistory?.signal_types) ? [...coinHistory.signal_types] : [];
    cards.sort((a, b) => (Number(b.sample_size) || 0) - (Number(a.sample_size) || 0));
    return cards;
  }, [coinHistory]);

  const signalItems = useMemo(
    () =>
      signals.map((card) => ({
        key: `${card.state}-${card.direction}-${card.label}`,
        name: humanizeLabel(card.label),
        sub: `${STATE_NAMES[card.state] || card.state} \u00b7 ${directionChip(card.direction)}`,
        value: card.win_rate == null ? null : Number(card.win_rate),
        weight: Number(card.sample_size) || 0,
        card,
        gauge: (
          <SetupTile
            key={`${card.state}-${card.direction}-${card.label}`}
            card={card}
            baseline={baselineRate}
          />
        ),
      })),
    [signals, baselineRate]
  );

  const boardItems = useMemo(
    () =>
      boards.map((board) => ({
        key: String(board.board),
        name: BOARD_NAMES[board.board] || String(board.board || "").replace(/_/g, " "),
        sub: BOARD_BLURBS[board.board] || "Coins that met this board's entry rule.",
        value:
          board.continuation_rate == null ? null : Number(board.continuation_rate),
        weight: Number(board.sample_size) || 0,
        board,
        gauge: <BoardTile key={board.board} board={board} />,
      })),
    [boards]
  );

  const coinItems = useMemo(
    () =>
      coinCards.map((card) => ({
        key: `${card.state}-${card.direction}-${card.label}`,
        name: humanizeLabel(card.label),
        sub: `${STATE_NAMES[card.state] || card.state} \u00b7 ${directionChip(card.direction)}`,
        value: card.win_rate == null ? null : Number(card.win_rate),
        weight: Number(card.sample_size) || 0,
        card,
        gauge: (
          <SetupTile
            key={`${card.state}-${card.direction}-${card.label}`}
            card={card}
            baseline={coinBaseline}
          />
        ),
      })),
    [coinCards, coinBaseline]
  );

  const runCoinLookup = useCallback(async (symbol, { silent = false } = {}) => {
    const normalized = normalizeCoinSymbol(symbol);
    if (!normalized) return;
    setCoinLoading(true);
    setCoinError(null);
    setCoinLoadedFor(normalized);
    try {
      const json = await fetchCoinHistory(normalized);
      setCoinHistory(json);
    } catch (err) {
      setCoinHistory(null);
      // A silent lookup is one the page started on its own. Failing at
      // something the user never asked for should not put an error in
      // front of them — the zone's own empty state covers it.
      if (!silent) setCoinError(err?.message || "Failed to load coin history");
    } finally {
      setCoinLoading(false);
    }
  }, []);

  // The hero names a coin from the first paint, so the coin zone should be
  // showing that coin rather than asking the user to pick the one already named.
  useEffect(() => {
    runCoinLookup(DEFAULT_COIN, { silent: true });
  }, [runCoinLookup]);

  const loadCoin = (event) => {
    event.preventDefault();
    runCoinLookup(coinInput);
  };

  if (error) {
    return (
      <div className="scr-page">
        <div className="scr-error">Couldn&apos;t load the scorecard: {error}</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="scr-page">
        <div className="scr-loading">Loading the track record...</div>
      </div>
    );
  }

  const sig = data.signals || {};
  const baseline = Number(sig.overall_win_rate);
  const coinFocus = normalizeCoinSymbol(coinLoadedFor || coinInput) || DEFAULT_COIN;
  const source = resolveSource(previewMode && !showingLive, data.status);

  return (
    <div className="scr-page">
      {/* Live data is labelled by the hero chip alone. Anything that is *not*
          measured from real outcomes gets a banner as well, because mistaking
          a sample for a track record is the one error worth shouting about. */}
      {source.key !== "live" ? (
        <div className="scr-provenance" data-source={source.key} role="status">
          <strong className="scr-provenance__headline">{source.headline}</strong>
          <span className="scr-provenance__note">{source.note}</span>
        </div>
      ) : null}

      {/* ── Zone 1 — the coin you selected, and where the data came from.
             The coin IS the page title; nothing here repeats it in prose. ── */}
      <header className="scr-hero">
        <div className="scr-hero__bar">
          <div className="scr-hero__id">
            <h2 className="scr-hero__coin">{coinFocus}</h2>
            {/* The chip is the label; the full explanation is a tooltip, not a
                block of copy occupying the top of the page. */}
            <span className="scr-hero__source" data-source={source.key} title={source.note}>
              {source.chip}
            </span>
          </div>

          <form className="scr-coinpicker" onSubmit={loadCoin}>
            {/* Label kept for screen readers; the placeholder is the visible
                affordance. This is a utility control, not a hero element. */}
            <label className="scr-vh" htmlFor="scr-coin-symbol">
              Change coin
            </label>
            <input
              id="scr-coin-symbol"
              className="scr-coinpicker__input"
              value={coinInput}
              onChange={(event) => setCoinInput(event.target.value)}
              placeholder="Change coin"
              autoComplete="off"
            />
            <button className="scr-coinpicker__button" type="submit" disabled={coinLoading}>
              {coinLoading ? "…" : "Show"}
            </button>
          </form>
        </div>

        <div className="scr-headline">
          <div className="scr-headline__card">
            <span className="scr-headline__label">Signals that worked</span>
            <span className="scr-headline__value">{rate(baseline, 1)}</span>
            <span className="scr-headline__note">of {count(sig.total_graded)} finished signals</span>
          </div>
          <div className="scr-headline__card">
            <span className="scr-headline__label">Most dependable category</span>
            <span className="scr-headline__value scr-headline__value--text">
              {bestSetup ? humanizeLabel(bestSetup.label) : "None yet"}
            </span>
            <span className="scr-headline__note">
              {bestSetup
                ? `${rate(bestSetup.win_rate)} worked, ${count(bestSetup.sample_size)} tested`
                : "Not enough measured signals"}
            </span>
          </div>
          <div className="scr-headline__card">
            <span className="scr-headline__label">Boards with enough history</span>
            <span className="scr-headline__value">
              {readyBoards} of {boards.length}
            </span>
            <span className="scr-headline__note">the rest are still collecting results</span>
          </div>
        </div>

        <details className="scr-scoring">
          <summary className="scr-scoring__toggle">How a signal is scored</summary>
          <p className="scr-hero__rule">
            A signal counts as working when the price moves{" "}
            <strong>+{sig.target_pct}%</strong> in the predicted direction before it moves{" "}
            <strong>-{sig.adverse_pct}%</strong> against it, inside{" "}
            <strong>{sig.horizon_minutes} minutes</strong>.
          </p>
        </details>
      </header>

      {/* ── Zone 2 — historical signal performance ── */}
      <Zone
        step="2"
        tone="signals"
        title="Signal history"
        lede="How often each kind of BHABIT alert has actually paid off, counted across every coin. It tells you which kinds have earned trust and which have not — open any row for what to do when one fires."
      >
        {/* Two categories that sound like opposite advice sit in this list at
            once. Saying outright that they are separate buckets of past calls
            is cheaper than letting someone read them as a live contradiction. */}
        <p className="scr-scope-note">
          Each row is a <strong>separate bucket of past calls, not advice being given right now.</strong>{" "}
          {opposing ? (
            <>
              Seeing <em>{opposing[0]}</em> and <em>{opposing[1]}</em> side by side
            </>
          ) : (
            "Seeing two rows that sound like opposite advice"
          )}{" "}
          does not mean BHABIT is telling you to buy and sell at once — it means both kinds of alert
          have fired before, and each has its own track record. For what BHABIT reads on {coinFocus}{" "}
          at this moment, open that coin on the live board.
        </p>

        <div className="scr-zone__controls">
          <ChartStyleSwitch value={chartStyle} onChange={setChartStyle} />
          <label className="scr-order">
            <span className="scr-order__label">Order by</span>
            <select
              className="scr-order__select"
              value={order}
              onChange={(event) => setOrder(event.target.value)}
            >
              <option value="trust">Most dependable</option>
              <option value="worked">Highest hit rate</option>
              <option value="tested">Most tested</option>
            </select>
          </label>
        </div>

        {signals.length > 0 ? (
          <ScoreGroup
            items={signalItems}
            baseline={baseline}
            style={chartStyle}
            centerLabel={count(sig.total_graded)}
            centerSub="calls graded"
            detailFor={(item) => (
              <SetupDetail card={item.card} baseline={baseline} name={item.name} />
            )}
          />
        ) : progress && Number(progress.total) > 0 ? (
          <CollectingPanel progress={progress} noun="signals" />
        ) : (
          <div className="scr-empty">
            No signals have been recorded yet. They appear here once BHABIT fires one and its
            outcome is graded.
          </div>
        )}
      </Zone>

      {/* ── Zone 3 — historical board performance ── */}
      <Zone
        step="3"
        tone="boards"
        title="Board history"
        lede="Whether landing on one of the live boards actually meant a coin kept moving. It tells you which boards are worth reacting to — the number to judge a board by is “vs. random”, not the raw percentage."
      >
        {boards.length > 0 && boards.some((b) => Number(b.sample_size) > 0) ? (
          <ScoreGroup
            items={boardItems}
            baseline={null}
            style={chartStyle}
            centerLabel={count(data.boards?.total_entries)}
            centerSub="appearances"
            detailFor={(item) => <BoardDetail board={item.board} name={item.name} />}
          />
        ) : Number(data.boards?.total_entries) > 0 ? (
          <CollectingPanel
            progress={{
              total: Number(data.boards?.total_entries) || 0,
              complete: 0,
              collecting: Number(data.boards?.total_entries) || 0,
              horizon_minutes: sig.horizon_minutes,
            }}
            noun="board appearances"
          />
        ) : (
          <div className="scr-empty">No board results have been measured yet.</div>
        )}
      </Zone>

      {/* ── Zone 4 — the selected coin's own history ── */}
      <Zone
        step="4"
        tone="coin"
        title={`${coinFocus} history`}
        lede={`The same measurements narrowed to ${coinFocus} on its own. It tells you whether this coin has behaved like the rest of the market or gone its own way. This is its past record only — for the current read on ${coinFocus}, open it on the live board.`}
      >
        {coinError ? (
          <div className="scr-note scr-note--error">
            Couldn&apos;t load {coinLoadedFor || coinFocus}: {coinError}
          </div>
        ) : null}

        {coinHistory ? (
          <div className="scr-coin">
            <div className="scr-coin__summary">
              <strong className="scr-coin__title">
                {coinLoadedFor || coinHistory.product_id || coinFocus}
              </strong>
              <p className="scr-coin__body">{coinSummarySentence(coinHistory)}</p>
              <span className="scr-coin__meta">
                Scored the same way: +{coinHistory.target_pct}% target, -{coinHistory.adverse_pct}%
                stop, {coinHistory.horizon_minutes} minute window.
              </span>
            </div>

            {coinCards.length > 0 ? (
              <ScoreGroup
                items={coinItems}
                baseline={coinBaseline}
                style={chartStyle}
                centerLabel={count(coinHistory.total_outcomes)}
                centerSub="measured"
                detailFor={(item) => (
                  <SetupDetail card={item.card} baseline={coinBaseline} name={item.name} />
                )}
              />
            ) : (
              <div className="scr-empty">
                Nothing measured on this coin yet. That is not a bad sign — it just means no signal
                on this asset has finished its window.
              </div>
            )}
          </div>
        ) : !coinLoading ? (
          <div className="scr-empty scr-empty--compact">
            Pick a coin at the top of the page to see whether it has behaved like the rest of the
            market.
          </div>
        ) : null}
      </Zone>

      {/* ── Zone 5 — internal diagnostics, collapsed ── */}
      <Zone
        step="5"
        tone="diagnostics"
        title="Internal diagnostics"
        lede="Raw totals, grouped rollups, and the exact scoring rules behind everything above. Useful for checking the maths or filing a bug; not needed to read any of the other sections."
      >
        <details className="scr-advanced">
          <summary className="scr-advanced__toggle">
            Show internal diagnostics
            <span className="scr-advanced__hint">Grouped totals and scoring rules</span>
          </summary>
          <div className="scr-advanced__body">
            <section className="scr-advanced__block">
              <h4>How outcomes are scored</h4>
              <ul className="scr-keyvals">
                <li>
                  <span>Finished signals measured</span>
                  <strong>{count(sig.total_graded)}</strong>
                </li>
                <li>
                  <span>Target move (counts as a win)</span>
                  <strong>+{sig.target_pct}%</strong>
                </li>
                <li>
                  <span>Stop level (counts as a loss)</span>
                  <strong>-{sig.adverse_pct}%</strong>
                </li>
                <li>
                  <span>Time allowed</span>
                  <strong>{sig.horizon_minutes} min</strong>
                </li>
                <li>
                  <span>Board appearances measured</span>
                  <strong>{count(data.boards?.total_entries)}</strong>
                </li>
                <li>
                  <span>Data source</span>
                  <strong>{source.chip}</strong>
                </li>
              </ul>
            </section>

            <section className="scr-advanced__block">
              <h4>Setups grouped by stage</h4>
              <p className="scr-advanced__note">
                Every setup card above rolled up by how mature the setup was when it fired.
              </p>
              <table className="scr-table">
                <thead>
                  <tr>
                    <th>Stage</th>
                    <th>Cards</th>
                    <th>Tested</th>
                    <th>Worked</th>
                  </tr>
                </thead>
                <tbody>
                  {stateGroups.map((row) => (
                    <tr key={row.state}>
                      <td>{STATE_NAMES[row.state] || row.state}</td>
                      <td>{row.card_count}</td>
                      <td>{count(row.sample_size)}</td>
                      <td>{rate(row.weighted_win_rate)}</td>
                    </tr>
                  ))}
                  {stateGroups.length === 0 && (
                    <tr>
                      <td colSpan={4}>Nothing measured yet.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </section>

            <section className="scr-advanced__block">
              <h4>Boards grouped by readiness</h4>
              <p className="scr-advanced__note">
                &ldquo;Enough history&rdquo; boards have been measured often enough that the number
                is fairly stable. &ldquo;Still learning&rdquo; boards can still swing.
              </p>
              <table className="scr-table">
                <thead>
                  <tr>
                    <th>Readiness</th>
                    <th>Boards</th>
                    <th>Appearances</th>
                    <th>Kept going</th>
                  </tr>
                </thead>
                <tbody>
                  {boardGroups.map((row) => (
                    <tr key={row.status}>
                      <td>
                        {row.status === "measured"
                          ? "Enough history"
                          : row.status === "learning"
                            ? "Still learning"
                            : row.status}
                      </td>
                      <td>{row.card_count}</td>
                      <td>{count(row.sample_size)}</td>
                      <td>{rate(row.weighted_continuation_rate)}</td>
                    </tr>
                  ))}
                  {boardGroups.length === 0 && (
                    <tr>
                      <td colSpan={4}>Nothing measured yet.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </section>
          </div>
        </details>
      </Zone>
    </div>
  );
}
