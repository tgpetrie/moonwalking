import React, { useEffect, useState } from "react";
import "../../styles/sentiment-panel.css";
import { useMarketHeat } from "../../hooks/useMarketHeat";
import { baselineOrNull, displayOrDash } from "../../utils/num.js";

function normalizeSymbol(symbol) {
  return (symbol || "")
    .replace(/-USDT?$/i, "")
    .replace(/-USD$/i, "");
}

function getFearGreedLabel(index) {
  if (index == null) return "—";
  if (index >= 75) return "Extreme Greed";
  if (index >= 55) return "Greed";
  if (index >= 45) return "Neutral";
  if (index >= 25) return "Fear";
  return "Extreme Fear";
}

export default function SentimentPanel({ open, onClose, row, interval = "3m" }) {
  const [activeTab, setActiveTab] = useState("overview");
  const {
    data,
    raw,
    loading: hookLoading,
    error,
    refresh,
    pipelineStatus,
  } = useMarketHeat();
  const sentiment = data || {};

  // Pipeline status: LIVE, STALE, or OFFLINE
  // When OFFLINE, don't show fake placeholder values
  const isOffline = pipelineStatus === "OFFLINE";
  const isStale = pipelineStatus === "STALE";

  const symbol = normalizeSymbol(row?.symbol);
  const price = row?.current_price ?? null;
  const prev = baselineOrNull(row?.initial_price_3min ?? row?.initial_price_1min ?? row?.initial_price ?? row?.previous_price ?? null);
  const pct =
    row?.price_change_percentage_3min ??
    row?.price_change_percentage_1min ??
    null;

  const trendDirection =
    row?.trend_direction ??
    (typeof pct === "number"
      ? pct > 0
        ? "Bullish"
        : pct < 0
        ? "Bearish"
        : "Flat"
      : null);

  // Defensive reads with fallbacks so partial/slow payloads don't crash the UI
  const overallScore =
    sentiment.overallSentiment != null
      ? Math.round(Number(sentiment.overallSentiment) * 100)
      : null;
  const fearGreedIndex =
    sentiment.fearGreedIndex == null ? null : Number(sentiment.fearGreedIndex);
  const divergenceAlerts = Array.isArray(sentiment.divergenceAlerts)
    ? sentiment.divergenceAlerts
    : [];
  const sentimentHistory = Array.isArray(sentiment.sentimentHistory)
    ? sentiment.sentimentHistory
    : [];
  const components = sentiment.components || {};
  const heatLabel = sentiment.heatLabel || "NEUTRAL";
  const regimeRaw = (sentiment.regime || "unknown").toString();
  const regimeDisplay = regimeRaw.replace(/_/g, " ").toUpperCase();
  const confidenceVal = Number.isFinite(sentiment.confidence) ? sentiment.confidence : null;
  const reasonLines = Array.isArray(sentiment.reasons) ? sentiment.reasons.slice(0, 2) : [];

  const loading = hookLoading && !raw;
  const fetchError = error;

  // On open we rely on SWR's background revalidation; hook preserves last-good snapshot.
  useEffect(() => {
    if (open && typeof refresh === "function") {
      refresh();
    }
  }, [open, refresh]);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (e.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="sentiment-popup-overlay"
      onClick={(e) => {
        if (e.target.classList.contains("sentiment-popup-overlay")) {
          onClose?.();
        }
      }}
    >
      <div className="sentiment-popup-card">
        <div className="sentiment-popup-header">
          <div className="sentiment-popup-title">
            <svg width="24" height="24" viewBox="0 0 24 24">
              <path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm3.5-9c.83 0 1.5-.67 1.5-1.5S16.33 8 15.5 8 14 8.67 14 9.5s.67 1.5 1.5 1.5zm-7 0c.83 0 1.5-.67 1.5-1.5S9.33 8 8.5 8 7 8.67 7 9.5 7.67 11 8.5 11zm3.5 6.5c2.33 0 4.31-1.46 5.11-3.5H6.89c.8 2.04 2.78 3.5 5.11 3.5z" />
            </svg>
            <div className="sentiment-title-text">
              <span>Sentiment Intelligence</span>
              {symbol ? (
                <span className="sentiment-subtitle">
                  {symbol} · {interval.toUpperCase()} snapshot
                </span>
              ) : null}
            </div>
            {/* Pipeline status badge */}
            <span
              className={
                "sentiment-status-badge " +
                (isOffline
                  ? "sentiment-status-offline"
                  : isStale
                  ? "sentiment-status-stale"
                  : "sentiment-status-live")
              }
              title={
                isOffline
                  ? "Pipeline offline - no data available"
                  : isStale
                  ? "Data may be stale"
                  : "Live data"
              }
            >
              {isOffline ? "OFFLINE" : isStale ? "STALE" : "LIVE"}
            </span>
          </div>

          <div className="sentiment-header-right">
            {symbol ? (
              <div className="sentiment-header-price">
                <span className="sentiment-header-symbol">{symbol}</span>
                <span className="sentiment-header-price-main">
                  {price != null ? `$${Number(price).toLocaleString()}` : "--"}
                </span>
                <span className="sentiment-header-prev">
                  prev {interval}:{" "}
                  {displayOrDash(prev, (value) => `$${Number(value).toLocaleString()}`)}
                </span>
              </div>
            ) : null}

            <button
              type="button"
              className="sentiment-close-btn"
              onClick={onClose}
            >
              <svg width="18" height="18" viewBox="0 0 24 24">
                <path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
              </svg>
            </button>
          </div>
        </div>

        <div className="sentiment-tab-nav">
          {["overview", "social", "charts", "sources"].map((tab) => (
            <button
              key={tab}
              type="button"
              className={
                "sentiment-tab-btn" +
                (activeTab === tab ? " sentiment-tab-btn-active" : "")
              }
              onClick={() => setActiveTab(tab)}
            >
              {tab === "overview" && "Overview"}
              {tab === "social" && "Tape Components"}
              {tab === "charts" && "History"}
              {tab === "sources" && "Data Sources"}
            </button>
          ))}
        </div>

        <div className="sentiment-tab-content">
          {activeTab === "overview" && (
            <div className="sentiment-tab-panel">
              <div className="sentiment-info-section">
                <h3>
                  <svg viewBox="0 0 24 24">
                    <path d="M12 2 15.09 8.26 22 9.27l-5 4.87L18.18 21 12 17.77 5.82 21 7 14.14 2 9.27l6.91-1.01z" />
                  </svg>
                  Market Heat
                </h3>
                <p>
                  Live market heat computed from Coinbase tape data across{" "}
                  {components.total_symbols ?? 0} symbols. Combines breadth,
                  momentum alignment, and volatility into a composite score.
                </p>
              </div>

              <div className="sentiment-info-section">
                <h3>Current Market Sentiment</h3>
                <div className="sentiment-metric-grid">
                  <div className={"sentiment-metric-card" + (isOffline ? " sentiment-metric-offline" : "")}>
                    <div className="sentiment-metric-label">Overall Score</div>
                    <div
                      className={
                        "sentiment-metric-value " +
                        (isOffline || overallScore == null
                          ? "neutral"
                          : overallScore >= 55
                          ? "positive"
                          : overallScore <= 45
                          ? "negative"
                          : "neutral")
                      }
                    >
                      {isOffline ? "--" : overallScore != null ? overallScore : "--"}
                    </div>
                  </div>

                  <div className={"sentiment-metric-card" + (isOffline ? " sentiment-metric-offline" : "")}>
                    <div className="sentiment-metric-label">Heat Label</div>
                    <div className={"sentiment-metric-value " + (overallScore != null && overallScore >= 55 ? "positive" : overallScore != null && overallScore <= 35 ? "negative" : "neutral")}>
                      {isOffline ? "--" : heatLabel}
                    </div>
                  </div>

                  <div className={"sentiment-metric-card" + (isOffline ? " sentiment-metric-offline" : "")}>
                    <div className="sentiment-metric-label">
                      Fear &amp; Greed
                    </div>
                    <div className="sentiment-metric-value positive">
                      {isOffline
                        ? "--"
                        : fearGreedIndex != null
                        ? `${getFearGreedLabel(fearGreedIndex)} (${fearGreedIndex})`
                        : "--"}
                    </div>
                  </div>

                  <div className="sentiment-metric-card">
                    <div className="sentiment-metric-label">Trend</div>
                    <div
                      className={
                        "sentiment-metric-value " +
                        (trendDirection === "Bullish"
                          ? "positive"
                          : trendDirection === "Bearish"
                          ? "negative"
                          : "neutral")
                      }
                    >
                      {trendDirection ? trendDirection : "—"}
                    </div>
                  </div>
                </div>

                <div className={"sentiment-bar-container" + (isOffline ? " sentiment-bar-offline" : "")}>
                  <span className="sentiment-bar-label">Sentiment:</span>
                  <div className="sentiment-bar">
                    <div
                      className="sentiment-bar-fill"
                      style={{
                        width:
                          isOffline ? "0%" : overallScore != null ? `${overallScore}%` : "0%",
                      }}
                    />
                  </div>
                  <span className="sentiment-bar-score">
                    {isOffline ? "--" : overallScore != null ? `${overallScore}%` : "--"}
                  </span>
                </div>
              </div>

              <div className="sentiment-info-section">
                <h3>Regime: {regimeDisplay}</h3>
                <p>
                  Confidence: {confidenceVal != null ? confidenceVal.toFixed(2) : "--"}.{" "}
                  Breadth (3m): {components.breadth_3m != null ? `${components.breadth_3m.toFixed(0)}%` : "--"},{" "}
                  Momentum: {components.momentum_alignment != null ? `${(components.momentum_alignment * 100).toFixed(0)}%` : "--"},{" "}
                  Volatility: {components.volatility != null ? `${components.volatility.toFixed(2)}%` : "--"}.
                </p>
                {reasonLines.map((r, idx) => (
                  <p key={`reason-${idx}`} style={{margin: '0.25rem 0', opacity: 0.8, fontSize: '0.85em'}}>{r}</p>
                ))}
              </div>
            </div>
          )}

          {activeTab === "social" && (
            <div className="sentiment-tab-panel">
              <div className="sentiment-info-section">
                <h3>Tape Components</h3>
                <div className="sentiment-metric-grid">
                  <div className="sentiment-metric-card">
                    <div className="sentiment-metric-label">Breadth (3m)</div>
                    <div className={"sentiment-metric-value " + ((components.breadth_3m ?? 50) >= 55 ? "positive" : (components.breadth_3m ?? 50) <= 45 ? "negative" : "neutral")}>
                      {components.breadth_3m != null ? `${components.breadth_3m.toFixed(0)}%` : "--"}
                    </div>
                  </div>
                  <div className="sentiment-metric-card">
                    <div className="sentiment-metric-label">Breadth (1m)</div>
                    <div className={"sentiment-metric-value " + ((components.breadth_1m ?? 50) >= 55 ? "positive" : (components.breadth_1m ?? 50) <= 45 ? "negative" : "neutral")}>
                      {components.breadth_1m != null ? `${components.breadth_1m.toFixed(0)}%` : "--"}
                    </div>
                  </div>
                  <div className="sentiment-metric-card">
                    <div className="sentiment-metric-label">Momentum</div>
                    <div className={"sentiment-metric-value " + ((components.momentum_alignment ?? 0) > 0 ? "positive" : (components.momentum_alignment ?? 0) < 0 ? "negative" : "neutral")}>
                      {components.momentum_alignment != null ? `${(components.momentum_alignment * 100).toFixed(0)}%` : "--"}
                    </div>
                  </div>
                  <div className="sentiment-metric-card">
                    <div className="sentiment-metric-label">Volatility</div>
                    <div className="sentiment-metric-value neutral">
                      {components.volatility != null ? `${components.volatility.toFixed(2)}%` : "--"}
                    </div>
                  </div>
                </div>
              </div>

              <div className="sentiment-info-section">
                <h3>Avg Returns</h3>
                <div className="sentiment-metric-grid">
                  <div className="sentiment-metric-card">
                    <div className="sentiment-metric-label">Avg Return (3m)</div>
                    <div className={"sentiment-metric-value " + ((components.avg_return_3m ?? 0) >= 0 ? "positive" : "negative")}>
                      {components.avg_return_3m != null ? `${components.avg_return_3m.toFixed(3)}%` : "--"}
                    </div>
                  </div>
                  <div className="sentiment-metric-card">
                    <div className="sentiment-metric-label">Avg Return (1m)</div>
                    <div className={"sentiment-metric-value " + ((components.avg_return_1m ?? 0) >= 0 ? "positive" : "negative")}>
                      {components.avg_return_1m != null ? `${components.avg_return_1m.toFixed(3)}%` : "--"}
                    </div>
                  </div>
                </div>
              </div>

              {divergenceAlerts.length ? (
                <div className="sentiment-info-section">
                  <h3>Divergence Alerts</h3>
                  {divergenceAlerts.map((alert, idx) => (
                    <div
                      key={idx}
                      className={
                        "sentiment-alert-box " +
                        (alert.type === "critical"
                          ? "sentiment-alert-critical"
                          : "sentiment-alert-warning")
                      }
                    >
                      {alert.message}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          )}

          {activeTab === "sources" && (
            <div className="sentiment-tab-panel">
              <div className="sentiment-info-section">
                <h3>Active Data Sources</h3>
                <p className="sentiment-subcopy">
                  Market heat is computed locally from real-time Coinbase tape
                  data, supplemented by an external Fear &amp; Greed signal.
                </p>

                <div className="sentiment-source-list">
                  <div className="sentiment-source-item">
                    <div>
                      <div className="sentiment-source-name">
                        Coinbase Price Tape
                      </div>
                      <div className="sentiment-source-desc">
                        Real-time prices for {components.total_symbols ?? 0} symbols. Breadth, momentum &amp; volatility.
                      </div>
                    </div>
                    <span className="sentiment-tier-badge tier-1">
                      PRIMARY
                    </span>
                  </div>

                  <div className="sentiment-source-item">
                    <div>
                      <div className="sentiment-source-name">Coinbase Volume Candles</div>
                      <div className="sentiment-source-desc">
                        1-minute candles for whale &amp; stealth detection
                      </div>
                    </div>
                    <span className="sentiment-tier-badge tier-2">
                      VOLUME
                    </span>
                  </div>

                  <div className="sentiment-source-item">
                    <div>
                      <div className="sentiment-source-name">
                        Fear &amp; Greed Index
                      </div>
                      <div className="sentiment-source-desc">
                        External macro signal (alternative.me), 5-min cache
                      </div>
                    </div>
                    <span className={"sentiment-tier-badge " + (fearGreedIndex != null ? "tier-1" : "tier-3")}>
                      {fearGreedIndex != null ? "LIVE" : "N/A"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "charts" && (
            <div className="sentiment-tab-panel">
              <div className="sentiment-info-section">
                <h3>Heat History</h3>
                {!sentimentHistory.length ? (
                  <div className="sentiment-empty">Warming up — collecting heat history...</div>
                ) : (
                  <div className="sentiment-history-list">
                    {sentimentHistory.slice(-10).map((entry, idx) => (
                      <div key={`sent-h-${idx}`} className="sentiment-history-row">
                        <span>{entry.label || "Heat"}</span>
                        <span className="tabular-nums">
                          {entry.sentiment != null
                            ? (Number(entry.sentiment) * 100).toFixed(0)
                            : entry.score != null
                            ? Number(entry.score).toFixed(0)
                            : "—"}
                        </span>
                        <span className="sentiment-history-ts">
                          {entry.timestamp
                            ? new Date(entry.timestamp).toLocaleTimeString()
                            : "recent"}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {loading && (
            <div className="sentiment-loading">Loading sentiment…</div>
          )}
          {fetchError && !data && (
            <div className="sentiment-error">
              Market heat data unavailable. Will recover automatically once
              tape data starts flowing.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
