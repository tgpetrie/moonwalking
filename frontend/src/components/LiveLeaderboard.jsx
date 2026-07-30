import { useState, useMemo } from "react";
import "../styles/live-leaderboard.css";

const COMPONENT_LABELS = {
  momentum_1m: { label: "1-min move", short: "1m", tip: "How much the price moved in the last minute" },
  momentum_3m: { label: "3-min move", short: "3m", tip: "How much the price moved in the last 3 minutes — this is the strongest weight" },
  trend_1h: { label: "1-hour trend", short: "1h", tip: "The broader direction over the last hour" },
  volume: { label: "Volume", short: "Vol", tip: "Whether trading volume is above or below normal for this coin" },
  confirmation: { label: "Alignment", short: "Align", tip: "Are alerts, spot pressure, and market context all pointing the same way?" },
  persistence: { label: "Staying power", short: "Hold", tip: "Is the move holding up or fading on repeated checks?" },
};

const FRIENDLY_LABELS = {
  Leading: "Hot right now",
  Strong: "Looking good",
  Building: "Warming up",
  Mixed: "No clear direction",
  Weak: "Cooling off",
  Fading: "Losing steam",
};

function scoreColor(score) {
  if (score >= 70) return "var(--brand-teal, #10ae9b)";
  if (score >= 55) return "var(--brand-amber, #ffb347)";
  if (score >= 45) return "rgba(255,255,255,0.4)";
  return "var(--brand-purple, #c084fc)";
}

function labelClass(label) {
  switch (label) {
    case "Leading": return "lb-label--leading";
    case "Strong": return "lb-label--strong";
    case "Building": return "lb-label--building";
    case "Mixed": return "lb-label--mixed";
    case "Weak": return "lb-label--weak";
    case "Fading": return "lb-label--fading";
    default: return "";
  }
}

function ComponentBar({ name, value }) {
  const meta = COMPONENT_LABELS[name] || { label: name, short: name, tip: "" };
  const pct = Math.max(0, Math.min(100, value ?? 50));
  const deviation = Math.abs(pct - 50);
  const color = pct >= 55
    ? "var(--brand-teal, #10ae9b)"
    : pct <= 45
      ? "var(--brand-purple, #c084fc)"
      : "rgba(255,255,255,0.2)";

  const readout = pct >= 65 ? "strong" : pct >= 55 ? "positive" : pct <= 35 ? "very weak" : pct <= 45 ? "negative" : "neutral";

  return (
    <div className="lb-comp" title={`${meta.label}: ${readout} (${pct.toFixed(0)}/100) — ${meta.tip}`}>
      <span className="lb-comp__label">{meta.short}</span>
      <div className="lb-comp__track">
        <div className="lb-comp__center" />
        <div
          className="lb-comp__fill"
          style={{
            left: pct >= 50 ? "50%" : `${pct}%`,
            width: `${deviation}%`,
            background: color,
          }}
        />
      </div>
      <span className="lb-comp__val" style={{ color }}>{pct.toFixed(0)}</span>
    </div>
  );
}

function friendlyReason(reason) {
  if (reason.includes("bullish alert")) return reason.replace("bullish alert", "bullish signal");
  if (reason.includes("bearish alert")) return reason.replace("bearish alert", "bearish signal");
  if (reason.includes("spot buying")) return "Buyers stepping in";
  if (reason.includes("spot selling")) return "Sellers stepping in";
  if (reason.includes("breaking away")) return "Moving independently of the market";
  if (reason.includes("tape hold")) return reason.replace("tape hold", "consecutive holds");
  return reason;
}

function friendlyRisk(risk) {
  if (risk === "extended move") return "Already moved a lot — risky to chase";
  if (risk === "timeframes disagree") return "Short and medium term conflict";
  if (risk === "volume fading") return "Move happening on weak volume";
  if (risk === "thin liquidity") return "Low liquidity — prices can jump";
  if (risk === "wide spread") return "Wide bid/ask spread";
  return risk;
}

function LeaderRow({ item, expanded, onToggle, onInfo }) {
  const components = item.live_components || {};
  const reasons = item.live_reasons || [];
  const risks = item.live_risks || [];
  const friendlyLabel = FRIENDLY_LABELS[item.live_label] || item.live_label;

  return (
    <div className={`lb-row ${expanded ? "lb-row--expanded" : ""}`}>
      <button
        type="button"
        className="lb-row__main"
        onClick={onToggle}
      >
        <span className="lb-row__rank">#{item.live_rank}</span>
        <span className="lb-row__symbol">{item.symbol}</span>
        <span
          className="lb-row__score"
          style={{ color: scoreColor(item.live_score) }}
        >
          {item.live_score}
        </span>
        <span className={`lb-row__label ${labelClass(item.live_label)}`}>
          {item.live_label}
        </span>
        <span className="lb-row__quality" title={`${item.observed_inputs} of ${item.expected_inputs} data sources available — more sources = more reliable score`}>
          {item.observed_inputs}/{item.expected_inputs}
        </span>
        <span className="lb-row__price">
          {item.price != null
            ? item.price >= 1
              ? `$${item.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
              : `$${item.price.toFixed(6)}`
            : "—"}
        </span>
        <span className="lb-row__chevron">{expanded ? "▾" : "▸"}</span>
      </button>

      {expanded && (
        <div className="lb-row__detail">
          <div className="lb-row__detail-summary">
            {friendlyLabel} — score {item.live_score}/100 using {item.observed_inputs} of {item.expected_inputs} data sources
          </div>

          <div className="lb-row__comp-header">What's driving the score</div>
          <div className="lb-row__components">
            {Object.entries(COMPONENT_LABELS).map(([key]) => (
              <ComponentBar key={key} name={key} value={components[key]} />
            ))}
          </div>

          <div className="lb-row__meta">
            {reasons.length > 0 && (
              <div className="lb-row__reasons">
                <span className="lb-meta-label">Why it's here</span>
                <div className="lb-chip-row">
                  {reasons.map((r, i) => (
                    <span key={i} className="lb-chip lb-chip--reason">{friendlyReason(r)}</span>
                  ))}
                </div>
              </div>
            )}
            {risks.length > 0 && (
              <div className="lb-row__risks">
                <span className="lb-meta-label">Watch out for</span>
                <div className="lb-chip-row">
                  {risks.map((r, i) => (
                    <span key={i} className="lb-chip lb-chip--risk">{friendlyRisk(r)}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <button
            type="button"
            className="lb-row__info-btn"
            onClick={(e) => { e.stopPropagation(); onInfo?.(item.symbol); }}
          >
            Full coin breakdown
          </button>
        </div>
      )}
    </div>
  );
}

export default function LiveLeaderboard({ items = [], onClose, onInfo }) {
  const [expandedSymbol, setExpandedSymbol] = useState(null);
  const [filter, setFilter] = useState("all");

  const filtered = useMemo(() => {
    if (!Array.isArray(items)) return [];
    switch (filter) {
      case "leading":
        return items.filter((i) => i.live_score >= 65);
      case "fading":
        return items.filter((i) => i.live_score <= 35);
      case "quality":
        return items.filter(
          (i) => i.observed_inputs >= (i.expected_inputs || 6) - 1
        );
      default:
        return items;
    }
  }, [items, filter]);

  const distribution = useMemo(() => {
    if (!items.length) return null;
    const leading = items.filter((i) => i.live_score >= 65).length;
    const strong = items.filter((i) => i.live_score >= 55 && i.live_score < 65).length;
    const mixed = items.filter((i) => i.live_score >= 45 && i.live_score < 55).length;
    const weak = items.filter((i) => i.live_score < 45).length;
    return { leading, strong, mixed, weak, total: items.length };
  }, [items]);

  return (
    <div className="lb-overlay" onClick={onClose}>
      <div className="lb-panel" onClick={(e) => e.stopPropagation()}>
        <div className="lb-header">
          <div className="lb-header__left">
            <h2 className="lb-header__title">Live Leaderboard</h2>
            <span className="lb-header__subtitle">
              {items.length} coins ranked by strength right now — updates every few seconds
            </span>
          </div>
          <button type="button" className="lb-header__close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="lb-explainer">
          Each coin gets a score from 1–99 based on its recent price moves, volume, alerts, and market context.
          Higher = more things lining up in the same direction. Click any row to see the breakdown.
        </div>

        {distribution && (
          <div className="lb-distribution">
            <div className="lb-dist-bar">
              <div
                className="lb-dist-seg lb-dist-seg--leading"
                style={{ flex: distribution.leading }}
                title={`${distribution.leading} coins scoring 65+ (strong setups)`}
              />
              <div
                className="lb-dist-seg lb-dist-seg--strong"
                style={{ flex: distribution.strong }}
                title={`${distribution.strong} coins scoring 55–64 (positive lean)`}
              />
              <div
                className="lb-dist-seg lb-dist-seg--mixed"
                style={{ flex: distribution.mixed }}
                title={`${distribution.mixed} coins scoring 45–54 (no clear direction)`}
              />
              <div
                className="lb-dist-seg lb-dist-seg--weak"
                style={{ flex: distribution.weak }}
                title={`${distribution.weak} coins scoring below 45 (bearish or fading)`}
              />
            </div>
            <div className="lb-dist-legend">
              <span><b>{distribution.leading}</b> Hot</span>
              <span><b>{distribution.strong}</b> Positive</span>
              <span><b>{distribution.mixed}</b> Neutral</span>
              <span><b>{distribution.weak}</b> Weak</span>
            </div>
          </div>
        )}

        <div className="lb-filters">
          {[
            { key: "all", label: "All coins" },
            { key: "leading", label: "Hot ones (65+)" },
            { key: "fading", label: "Fading (<35)" },
            { key: "quality", label: "Most data" },
          ].map((f) => (
            <button
              key={f.key}
              className={`lb-filter ${filter === f.key ? "is-active" : ""}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="lb-table-head">
          <span className="lb-th lb-th--rank">#</span>
          <span className="lb-th lb-th--symbol">Coin</span>
          <span className="lb-th lb-th--score" title="Composite strength score from 1 (weakest) to 99 (strongest)">Score</span>
          <span className="lb-th lb-th--label" title="Plain-English read on the current setup">Read</span>
          <span className="lb-th lb-th--quality" title="How many data sources are available — more is better">Data</span>
          <span className="lb-th lb-th--price">Price</span>
          <span className="lb-th lb-th--chevron" />
        </div>

        <div className="lb-list">
          {filtered.map((item) => (
            <LeaderRow
              key={item.symbol}
              item={item}
              expanded={expandedSymbol === item.symbol}
              onToggle={() =>
                setExpandedSymbol(
                  expandedSymbol === item.symbol ? null : item.symbol
                )
              }
              onInfo={onInfo}
            />
          ))}
          {filtered.length === 0 && (
            <div className="lb-empty">No coins match this filter right now.</div>
          )}
        </div>
      </div>
    </div>
  );
}
