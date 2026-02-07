import React, { useEffect, useMemo, useState } from "react";
import { API_ENDPOINTS, fetchData } from "../../api";

const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, n));

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

const formatTime = (ts) => {
  if (!ts) return "--";
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "--";
  }
};

function useBasicSentiment(pollMs = 15000) {
  const [state, setState] = useState({ data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    let timer = null;

    const load = async () => {
      if (!cancelled) {
        setState((prev) => ({ ...prev, loading: prev.data == null }));
      }
      try {
        const json = await fetchData(API_ENDPOINTS.sentimentBasic, { cache: "no-store" });
        if (cancelled) return;
        setState({ data: json, loading: false, error: null });
      } catch (err) {
        if (cancelled) return;
        setState((prev) => ({ data: prev.data, loading: false, error: err }));
      } finally {
        if (!cancelled && pollMs) {
          timer = setTimeout(load, pollMs);
        }
      }
    };

    load();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [pollMs]);

  return state;
}

function mapBasicSentiment(payload) {
  const heat = payload?.market_heat || {};
  const scoreNum = Number(heat?.score);
  const overallSentiment = Number.isFinite(scoreNum) ? scoreNum / 100 : null;
  const confidenceNum = Number(heat?.confidence);
  const sourceBreakdown = Number.isFinite(confidenceNum)
    ? { tier1: Math.round(confidenceNum * 100), tier2: 0, tier3: 0, fringe: 0 }
    : {};

  return {
    overallSentiment,
    fearGreedIndex: payload?.fear_greed?.value ?? null,
    updatedAt: payload?.timestamp ?? null,
    sourceBreakdown,
  };
}

export function SentimentCardBody({ d, symbol }) {
  const hasUpdatedAt = Boolean(d.updatedAt);
  const hasSources = (() => {
    const s = d.sourceBreakdown || {};
    return [s.tier1, s.tier2, s.tier3, s.fringe].some((v) => Number.isFinite(Number(v)) && Number(v) > 0);
  })();
  const fresh = useMemo(() => (hasUpdatedAt ? freshnessLabel(d.updatedAt) : null), [d.updatedAt, hasUpdatedAt]);
  const conf = useMemo(() => (hasSources ? confidenceFromSources(d.sourceBreakdown) : null), [d.sourceBreakdown, hasSources]);

  const overallTone =
    d.overallSentiment == null
      ? "muted"
      : d.overallSentiment >= 0.7
      ? "good"
      : d.overallSentiment >= 0.45
      ? "mid"
      : "bad";

  const fgRaw = d.fearGreedIndex;
  const fearGreedPct = Number.isFinite(Number(fgRaw))
    ? clamp(Number(fgRaw) <= 1 ? Number(fgRaw) * 100 : Number(fgRaw), 0, 100)
    : null;

  const stats = [
    d.overallSentiment == null
      ? null
      : {
          label: "Overall",
          value: d.overallSentiment.toFixed(2),
          tone:
            overallTone === "good" ? "mint" : overallTone === "mid" ? "gold" : "purple",
        },
    fearGreedPct == null
      ? null
      : {
          label: "Fear & Greed",
          value: `${Math.round(fearGreedPct)}`,
          suffix: "%",
          tone: "gold",
        },
  ].filter(Boolean);

  return (
    <div className="sentiment-card">
      <header className="sentiment-header">
        <div>
          <div className="title">Sentiment Pulse</div>
          <div className="subtitle">
            {symbol ? `${symbol.toUpperCase()} aggregate` : "Market-wide composite"}
          </div>
        </div>
        {(fresh || conf || hasUpdatedAt) && (
          <div className="right-meta">
            {fresh && <span>freshness: {fresh.label}</span>}
            {conf && <span>confidence: {conf.label}</span>}
            {hasUpdatedAt && <span>{formatTime(d.updatedAt)}</span>}
          </div>
        )}
      </header>

      {stats.length > 0 ? (
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
      ) : (
        <div className="state-copy">No actionable sentiment data yet.</div>
      )}

      {fearGreedPct != null && (
        <div className="sentiment-meter">
          <div className="meter-label">Fear &amp; Greed</div>
          <div className="bar">
            <div
              className="bar-fill"
              style={{ width: `${fearGreedPct}%` }}
            />
          </div>
          <div className="pct">{`${fearGreedPct.toFixed(0)}%`}</div>
        </div>
      )}

    </div>
  );
}

export default function SentimentCard({ symbol }) {
  const { data, loading, error } = useBasicSentiment();
  const mapped = useMemo(() => mapBasicSentiment(data), [data]);

  if (loading) {
    return <div className="state-copy">Loading sentiment…</div>;
  }
  if (error && !data) {
    return <div className="state-copy">Sentiment offline.</div>;
  }
  return <SentimentCardBody d={mapped} symbol={symbol} />;
}
