import React, { useMemo } from "react";
import useSentimentLatest from "../../hooks/useSentimentLatest";

const pct = (x, digits = 0) => (x == null ? "—" : `${(x * 100).toFixed(digits)}%`);
const num = (x) => (x == null ? "—" : Number(x).toLocaleString());
const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, n));

const toPairs = (record = {}) =>
  Object.entries(record)
    .filter(([, value]) => value != null)
    .map(([key, value]) => ({
      name: key.charAt(0).toUpperCase() + key.slice(1),
      value,
    }));

function freshnessLabel(updatedAt) {
  if (!updatedAt) return { label: "unknown", tone: "muted" };
  const ageMs = Date.now() - new Date(updatedAt).getTime();
  const ageMin = ageMs / 60000;
  if (ageMin < 2) return { label: "fresh", tone: "good" };
  if (ageMin < 10) return { label: "recent", tone: "mid" };
  return { label: "stale", tone: "bad" };
}

function confidenceFromSources(sourceBreakdown = {}) {
  const tier1 = Number(sourceBreakdown.tier1) || 0;
  const tier2 = Number(sourceBreakdown.tier2) || 0;
  const fringe = Number(sourceBreakdown.fringe) || 0;

  const top = tier1 + tier2;
  const conf = clamp((top - fringe) / 100, 0, 1);
  if (conf > 0.7) return { label: "high", tone: "good" };
  if (conf > 0.4) return { label: "medium", tone: "mid" };
  return { label: "low", tone: "bad" };
}

const toneClass = (sentiment = "") => {
  const s = sentiment.toLowerCase();
  if (s.includes("bull")) return "bullish";
  if (s.includes("bear")) return "bearish";
  return "neutral";
};

const alertTone = (type = "") => {
  const t = type.toLowerCase();
  if (t.includes("warn") || t.includes("risk")) return "warning";
  return "info";
};

const formatTime = (ts) => {
  if (!ts) return "--";
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "--";
  }
};

export function SentimentCardBody({ d, symbol }) {
  const fresh = useMemo(() => freshnessLabel(d.updatedAt), [d.updatedAt]);
  const conf = useMemo(() => confidenceFromSources(d.sourceBreakdown), [d.sourceBreakdown]);
  const socialBreakdownPairs = useMemo(() => toPairs(d.socialBreakdown), [d.socialBreakdown]);

  const overallTone =
    d.overallSentiment == null
      ? "muted"
      : d.overallSentiment >= 0.7
      ? "good"
      : d.overallSentiment >= 0.45
      ? "mid"
      : "bad";

  const trending = d.trendingTopics ?? [];
  const alerts = d.divergenceAlerts ?? [];

  const fgRaw = d.fearGreedIndex;
  const fearGreedPct = Number.isFinite(Number(fgRaw))
    ? clamp(Number(fgRaw) <= 1 ? Number(fgRaw) * 100 : Number(fgRaw), 0, 100)
    : null;

  const stats = [
    {
      label: "Overall",
      value: d.overallSentiment == null ? "—" : d.overallSentiment.toFixed(2),
      tone:
        overallTone === "good" ? "mint" : overallTone === "mid" ? "gold" : "purple",
    },
    {
      label: "Fear & Greed",
      value: fearGreedPct == null ? "—" : `${Math.round(fearGreedPct)}`,
      suffix: fearGreedPct == null ? "" : "%",
      tone: "gold",
    },
    {
      label: "Mentions 24h",
      value: num(d.socialMetrics?.mentions24h),
      tone: "mint",
    },
    {
      label: "Engagement",
      value: pct(d.socialMetrics?.engagementRate, 1),
      tone: "purple",
    },
  ];

  return (
    <div className="sentiment-card">
      <header className="sentiment-header">
        <div>
          <div className="title">Sentiment Pulse</div>
          <div className="subtitle">
            {symbol ? `${symbol.toUpperCase()} aggregate` : "Market-wide composite"}
          </div>
        </div>
        <div className="right-meta">
          <span>freshness: {fresh.label}</span>
          <span>confidence: {conf.label}</span>
          <span>{formatTime(d.updatedAt)}</span>
        </div>
      </header>

      <div className="sentiment-stats-grid">
        {stats.map((s) => (
          <div key={s.label} className="sentiment-stat">
            <div className="label">{s.label}</div>
            <div className={`value ${s.tone}`}>
              {s.value}
              {s.suffix}
            </div>
          </div>
        ))}
      </div>

      <div className="sentiment-meter">
        <div className="meter-label">Fear &amp; Greed</div>
        <div className="bar">
          <div
            className="bar-fill"
            style={{ width: fearGreedPct == null ? "0%" : `${fearGreedPct}%` }}
          />
        </div>
        <div className="pct">{fearGreedPct == null ? "--" : `${fearGreedPct.toFixed(0)}%`}</div>
      </div>

      <section>
        <div className="sentiment-section-title">Social Breakdown</div>
        <div className="sentiment-section-sub">Share of mentions by channel</div>
        {socialBreakdownPairs.length > 0 ? (
          <div className="trending-grid">
            {socialBreakdownPairs.map((s) => (
              <div key={s.name} className="trending-pill neutral">
                <span>{s.name}</span>
                <span>{pct(s.value)}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="insights-empty-card">No social split yet.</div>
        )}
      </section>

      <section>
        <div className="sentiment-section-title">Trending Topics</div>
        <div className="sentiment-section-sub">What the street is leaning into</div>
        {trending.length > 0 ? (
          <div className="trending-grid">
            {trending.map((t, i) => (
              <div key={`${t.tag ?? "topic"}-${i}`} className={`trending-pill ${toneClass(t.sentiment)}`}>
                <span>{t.tag ?? "--"}</span>
                <span>{t.sentiment ?? "--"}</span>
                {t.volume != null && <span>{t.volume}</span>}
              </div>
            ))}
          </div>
        ) : (
          <div className="insights-empty-card">Quiet right now.</div>
        )}
      </section>

      {alerts.length > 0 && (
        <section>
          <div className="sentiment-section-title">Divergence Alerts</div>
          <div className="sentiment-section-sub">Momentum vs chatter</div>
          <div className="divergence-list">
            {alerts.map((a, i) => (
              <div key={`${a.type ?? "alert"}-${i}`} className={`divergence-item ${alertTone(a.type ?? "")}`}>
                {a.message}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export default function SentimentCard({ symbol }) {
  const { data, loading, error } = useSentimentLatest(symbol);

  if (loading) {
    return <div className="state-copy">Loading sentiment…</div>;
  }
  if (error) {
    return <div className="state-copy">Sentiment offline.</div>;
  }
  return <SentimentCardBody d={data} symbol={symbol} />;
}
