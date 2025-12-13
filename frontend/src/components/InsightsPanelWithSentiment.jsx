import React, { useState } from "react";
import useInsights from "../hooks/useInsights";
import { formatPrice, formatPct } from "../utils/format";
import SentimentTriggerButton from "./SentimentTriggerButton";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "price", label: "Price & Momentum" },
  { id: "social", label: "Social & Sentiment" },
  { id: "macro", label: "Market Mood" },
];

/**
 * Enhanced InsightsPanel with Advanced Sentiment Popup Integration
 *
 * This is an example showing how to integrate the SentimentTriggerButton
 * into the existing InsightsPanel component.
 */
export default function InsightsPanelWithSentiment({ symbol, onClose }) {
  const { data, loading, error } = useInsights(symbol);
  const [activeTab, setActiveTab] = useState("overview");

  if (!symbol) return null;

  const safeData = data || {};

  const {
    price,
    change_1m,
    change_3m,
    volume_change_1h,
    heat_score,
    trend,
    social,
    market_sentiment,
  } = safeData;

  const trendLabel = trend || "FLAT";

  const fmtPct = (value) => {
    if (value == null) return "–";
    return formatPct(value, { sign: true });
  };

  const fmtPrice = (value) => {
    if (value == null) return "–";
    return formatPrice(value);
  };

  const renderBody = () => {
    if (loading && !data) {
      return (
        <div className="insights-body">
          <div className="insights-placeholder">Loading insights…</div>
        </div>
      );
    }

    if (error) {
      return (
        <div className="insights-body">
          <div className="insights-placeholder">Unable to load insights for this asset.</div>
        </div>
      );
    }

    if (!data) {
      return (
        <div className="insights-body">
          <div className="insights-placeholder">No insight data for this asset yet.</div>
        </div>
      );
    }

    switch (activeTab) {
      case "overview":
        return (
          <div className="insights-body">
            <div className="insights-row">
              <div className="insights-label">Symbol</div>
              <div className="insights-value">{safeData.symbol || "–"}</div>
            </div>
            <div className="insights-row">
              <div className="insights-label">Price</div>
              <div className="insights-value">{fmtPrice(price)}</div>
            </div>
            <div className="insights-row">
              <div className="insights-label">Heat Score</div>
              <div className="insights-value">{heat_score == null ? "–" : `${heat_score.toFixed(1)} / 100`}</div>
            </div>
            <div className="insights-row">
              <div className="insights-label">Short-Term Trend</div>
              <div className="insights-value">{trendLabel}</div>
            </div>
          </div>
        );

      case "price":
        return (
          <div className="insights-body">
            <div className="insights-row">
              <div className="insights-label">1-min change</div>
              <div className="insights-value">{fmtPct(change_1m)}</div>
            </div>
            <div className="insights-row">
              <div className="insights-label">3-min change</div>
              <div className="insights-value">{fmtPct(change_3m)}</div>
            </div>
            <div className="insights-row">
              <div className="insights-label">1-hour volume change</div>
              <div className="insights-value">{fmtPct(volume_change_1h)}</div>
            </div>
          </div>
        );

      case "social":
        return (
          <div className="insights-body">
            {!social ? (
              <div className="insights-placeholder">No external social / sentiment data available.</div>
            ) : (
              <>
                <div className="insights-row">
                  <div className="insights-label">Up-vote sentiment</div>
                  <div className="insights-value">
                    {social.sentiment_votes_up_percentage == null ? "–" : `${social.sentiment_votes_up_percentage.toFixed(1)}%`}
                  </div>
                </div>
                <div className="insights-row">
                  <div className="insights-label">Reddit subscribers</div>
                  <div className="insights-value">
                    {social.reddit_subscribers == null ? "–" : social.reddit_subscribers.toLocaleString()}
                  </div>
                </div>
                <div className="insights-row">
                  <div className="insights-label">Posts (48h avg)</div>
                  <div className="insights-value">
                    {social.reddit_posts_48h == null ? "–" : social.reddit_posts_48h.toFixed(1)}
                  </div>
                </div>
                <div className="insights-row">
                  <div className="insights-label">Comments (48h avg)</div>
                  <div className="insights-value">
                    {social.reddit_comments_48h == null ? "–" : social.reddit_comments_48h.toFixed(1)}
                  </div>
                </div>
              </>
            )}
          </div>
        );

      case "macro":
        return (
          <div className="insights-body">
            {!market_sentiment ? (
              <div className="insights-placeholder">No global market sentiment data available.</div>
            ) : (
              <>
                {/* ENHANCED: Add header with sentiment trigger button */}
                <div className="insights-row" style={{ paddingBottom: '0.75rem', marginBottom: '0.75rem' }}>
                  <div className="insights-label" style={{ fontSize: '0.9rem', fontWeight: 600 }}>
                    Market Sentiment
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '0.7rem', color: '#a3a3a3' }}>View Details</span>
                    <SentimentTriggerButton symbol={symbol} />
                  </div>
                </div>

                <div className="insights-row">
                  <div className="insights-label">Fear &amp; Greed</div>
                  <div className="insights-value">{market_sentiment.value != null ? `${market_sentiment.value} / 100` : "–"}</div>
                </div>
                <div className="insights-row">
                  <div className="insights-label">Classification</div>
                  <div className="insights-value">{market_sentiment.classification || "–"}</div>
                </div>

                {/* ENHANCED: Add call-to-action hint */}
                <div className="insights-row" style={{ marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                  <div style={{
                    fontSize: '0.75rem',
                    color: '#a3a3a3',
                    fontStyle: 'italic',
                    textAlign: 'center',
                    width: '100%'
                  }}>
                    💡 Click the info button above for detailed sentiment analysis with charts, sources, and insights
                  </div>
                </div>
              </>
            )}
          </div>
        );

      default:
        return (
          <div className="insights-body">
            <div className="insights-placeholder">Unknown tab.</div>
          </div>
        );
    }
  };

  return (
    <div className="insights-card" role="dialog" aria-label={`Insights for ${symbol}`}>
      <div className="insights-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={tab.id === activeTab ? "active" : ""}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}

        {onClose && (
          <button type="button" className="insights-close-btn" onClick={onClose} style={{ marginLeft: "auto", fontSize: "0.7rem" }}>
            Close
          </button>
        )}
      </div>

      {renderBody()}
    </div>
  );
}
