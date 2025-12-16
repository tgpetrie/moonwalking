import React, { useEffect, useState } from "react";
import "../../styles/sentiment-panel.css";
import { useSentimentLatest } from "../../hooks/useSentimentLatest";
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
  } = useSentimentLatest();
  const sentiment = data || {};

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
  const socialVolumeChange =
    typeof sentiment.socialMetrics?.volumeChange === "number"
      ? sentiment.socialMetrics.volumeChange
      : null;
  const reddit = sentiment.socialBreakdown?.reddit ?? 0;
  const twitter = sentiment.socialBreakdown?.twitter ?? 0;
  const telegram = sentiment.socialBreakdown?.telegram ?? 0;
  const chan = sentiment.socialBreakdown?.chan ?? 0;
  const trendingTopics = Array.isArray(sentiment.trendingTopics)
    ? sentiment.trendingTopics
    : [];
  const divergenceAlerts = Array.isArray(sentiment.divergenceAlerts)
    ? sentiment.divergenceAlerts
    : [];
  const sentimentHistory = Array.isArray(sentiment.sentimentHistory)
    ? sentiment.sentimentHistory
    : [];
  const socialHistory = Array.isArray(sentiment.socialHistory)
    ? sentiment.socialHistory
    : [];

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
              {tab === "social" && "Social Sentiment"}
              {tab === "charts" && "Charts"}
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
                  What is Sentiment Intelligence?
                </h3>
                <p>
                  This panel blends your token’s short-term move with a
                  multi-tier sentiment feed from news, social, and fringe
                  communities. It’s built to flag when narrative heat and price
                  action rhyme – and when they don’t.
                </p>
              </div>

              <div className="sentiment-info-section">
                <h3>Current Market Sentiment</h3>
                <div className="sentiment-metric-grid">
                  <div className="sentiment-metric-card">
                    <div className="sentiment-metric-label">Overall Score</div>
                    <div
                      className={
                        "sentiment-metric-value " +
                        (overallScore == null
                          ? "neutral"
                          : overallScore >= 55
                          ? "positive"
                          : overallScore <= 45
                          ? "negative"
                          : "neutral")
                      }
                    >
                      {overallScore != null ? overallScore : "--"}
                    </div>
                  </div>

                  <div className="sentiment-metric-card">
                    <div className="sentiment-metric-label">
                      Social Volume (24h)
                    </div>
                    <div className="sentiment-metric-value neutral">
                      {socialVolumeChange != null
                        ? `${socialVolumeChange > 0 ? "+" : ""}${Number(
                            socialVolumeChange
                          ).toFixed(1)}%`
                        : "--"}
                    </div>
                  </div>

                  <div className="sentiment-metric-card">
                    <div className="sentiment-metric-label">
                      Fear &amp; Greed
                    </div>
                    <div className="sentiment-metric-value positive">
                      {fearGreedIndex != null
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

                <div className="sentiment-bar-container">
                  <span className="sentiment-bar-label">Sentiment:</span>
                  <div className="sentiment-bar">
                    <div
                      className="sentiment-bar-fill"
                      style={{
                        width:
                          overallScore != null ? `${overallScore}%` : "0%",
                      }}
                    />
                  </div>
                  <span className="sentiment-bar-score">
                    {overallScore != null ? `${overallScore}%` : "--"}
                  </span>
                </div>
              </div>

              <div className="sentiment-info-section">
                <h3>How we weigh the crowd</h3>
                <p>
                  Tier 1 sources (Fear &amp; Greed, CoinGecko, Binance/major
                  feeds) anchor the score. Tier 2 (Reddit, mainstream crypto
                  media) tracks the retail tide. Tier 3 and fringe feeds watch
                  early-signal chaos for hints of what’s coming next.
                </p>
              </div>
            </div>
          )}

          {activeTab === "social" && (
            <div className="sentiment-tab-panel">
              <div className="sentiment-info-section">
                <h3>Social Breakdown</h3>
                <div className="sentiment-metric-grid">
                  <div className="sentiment-metric-card">
                    <div className="sentiment-metric-label">Reddit</div>
                    <div className="sentiment-metric-value positive">
                      {sentiment.socialBreakdown?.reddit != null
                        ? `${Math.round(sentiment.socialBreakdown.reddit * 100)}%`
                        : "--"}
                    </div>
                  </div>
                  <div className="sentiment-metric-card">
                    <div className="sentiment-metric-label">Twitter / X</div>
                    <div className="sentiment-metric-value neutral">
                      {sentiment.socialBreakdown?.twitter != null
                        ? `${Math.round(sentiment.socialBreakdown.twitter * 100)}%`
                        : "--"}
                    </div>
                  </div>
                  <div className="sentiment-metric-card">
                    <div className="sentiment-metric-label">Telegram</div>
                    <div className="sentiment-metric-value positive">
                      {sentiment.socialBreakdown?.telegram != null
                        ? `${Math.round(sentiment.socialBreakdown.telegram * 100)}%`
                        : "--"}
                    </div>
                  </div>
                  <div className="sentiment-metric-card">
                    <div className="sentiment-metric-label">Fringe / chan</div>
                    <div className="sentiment-metric-value negative">
                      {sentiment.socialBreakdown?.chan != null
                        ? `${Math.round(sentiment.socialBreakdown.chan * 100)}%`
                        : "--"}
                    </div>
                  </div>
                </div>
              </div>

              <div className="sentiment-info-section">
                <h3>Trending Topics</h3>
                <div className="sentiment-tag-container">
                  {trendingTopics.slice(0, 10).map((topic, idx) => (
                    <span
                      key={topic?.tag || topic?.sentiment || `topic-${idx}`}
                      className="sentiment-tag sentiment-tag-neutral"
                    >
                      {topic?.tag || topic?.sentiment || topic || "topic"}
                    </span>
                  ))}
                  {!trendingTopics.length && (
                    <span className="sentiment-tag sentiment-tag-neutral">
                      No hot topics detected in the last window.
                    </span>
                  )}
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
                  The score here is not a gut feeling. It’s a weighted blend of
                  institutional, mainstream, and retail signals pulled from
                  multiple tiers, updated continuously in the background.
                </p>

                <div className="sentiment-source-list">
                  <div className="sentiment-source-item">
                    <div>
                      <div className="sentiment-source-name">
                        Fear &amp; Greed Index
                      </div>
                      <div className="sentiment-source-desc">
                        Macro market sentiment gauge
                      </div>
                    </div>
                    <span className="sentiment-tier-badge tier-1">
                      TIER 1
                    </span>
                  </div>

                  <div className="sentiment-source-item">
                    <div>
                      <div className="sentiment-source-name">CoinGecko</div>
                      <div className="sentiment-source-desc">
                        Market data &amp; dominance shifts
                      </div>
                    </div>
                    <span className="sentiment-tier-badge tier-1">
                      TIER 1
                    </span>
                  </div>

                  <div className="sentiment-source-item">
                    <div>
                      <div className="sentiment-source-name">Binance RSS</div>
                      <div className="sentiment-source-desc">
                        Exchange-driven news &amp; updates
                      </div>
                    </div>
                    <span className="sentiment-tier-badge tier-1">
                      TIER 1
                    </span>
                  </div>

                  <div className="sentiment-source-item">
                    <div>
                      <div className="sentiment-source-name">
                        Reddit r/CryptoCurrency, r/Bitcoin, etc.
                      </div>
                      <div className="sentiment-source-desc">
                        Mainstream retail sentiment
                      </div>
                    </div>
                    <span className="sentiment-tier-badge tier-2">
                      TIER 2
                    </span>
                  </div>

                  <div className="sentiment-source-item">
                    <div>
                      <div className="sentiment-source-name">
                        Crypto media RSS (CoinDesk, CryptoSlate, Bitcoin
                        Magazine)
                      </div>
                      <div className="sentiment-source-desc">
                        Long-form narratives &amp; coverage
                      </div>
                    </div>
                    <span className="sentiment-tier-badge tier-2">
                      TIER 2
                    </span>
                  </div>

                  <div className="sentiment-source-item">
                    <div>
                      <div className="sentiment-source-name">
                        r/SatoshiStreetBets, r/CryptoMoonShots
                      </div>
                      <div className="sentiment-source-desc">
                        Speculative, early-signal retail chatter
                      </div>
                    </div>
                    <span className="sentiment-tier-badge tier-3">
                      TIER 3
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "charts" && (
            <div className="sentiment-tab-panel">
              <div className="sentiment-info-section">
                <h3>Sentiment History</h3>
                {!sentimentHistory.length && !socialHistory.length ? (
                  <div className="sentiment-empty">Sentiment history warming up.</div>
                ) : (
                  <div className="sentiment-history-list">
                    {sentimentHistory.slice(-10).map((entry, idx) => (
                      <div key={`sent-h-${idx}`} className="sentiment-history-row">
                        <span>{entry.label || entry.tag || "Composite"}</span>
                        <span className="tabular-nums">
                          {entry.sentiment != null
                            ? Math.round(Number(entry.sentiment) * 100) / 100
                            : entry.score != null
                            ? Math.round(Number(entry.score) * 100) / 100
                            : entry.value ?? "—"}
                        </span>
                        <span className="sentiment-history-ts">
                          {entry.timestamp
                            ? new Date(entry.timestamp).toLocaleTimeString()
                            : entry.ts
                            ? new Date(entry.ts).toLocaleTimeString()
                            : "recent"}
                        </span>
                      </div>
                    ))}
                    {socialHistory.length ? (
                      <div className="sentiment-history-row muted">
                        Social sample: {socialHistory.length} points
                      </div>
                    ) : null}
                  </div>
                )}
              </div>

              <div className="sentiment-info-section">
                <h3>Trending Topics Snapshot</h3>
                {trendingTopics.length ? (
                  <div className="sentiment-tag-container">
                    {trendingTopics.slice(0, 10).map((topic, idx) => (
                      <span
                        key={`chart-topic-${topic?.tag || topic?.sentiment || idx}`}
                        className="sentiment-tag sentiment-tag-neutral"
                      >
                        {topic?.tag || topic?.sentiment || topic || "topic"}
                      </span>
                    ))}
                  </div>
                ) : (
                  <div className="sentiment-empty">Waiting for trending topics.</div>
                )}
              </div>
            </div>
          )}

          {loading && (
            <div className="sentiment-loading">Loading sentiment…</div>
          )}
          {fetchError && !data && (
            <div className="sentiment-error">
              Sentiment API is not responding right now. Panel will fall back
              gracefully once it’s back online.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
