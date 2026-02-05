import React, { useState, useMemo } from 'react';
import PropTypes from 'prop-types';
import { useSentiment } from '../hooks/useSentiment.js';

const TABS = ['Charts', 'Sentiment', 'Social', 'Info'];

export default function InsightPanel({ isOpen, token, insights, onClose }) {
  const [activeTab, setActiveTab] = useState('Charts');

  const hasData = !!token;

  const tokenSymbol = token?.symbol || token?.base || '';
  const tokenName = token?.name || tokenSymbol;
  const price = token?.price;
  const change1m = token?.change_1m;
  const change3m = token?.change_3m;

  // prefer passed-in insights, but fall back to per-symbol sentiment fetch
  const symbol = tokenSymbol;
  const { data: sData, error: sError, isLoading: sLoading } = useSentiment(symbol, 30);

  const sentimentSummary = insights?.sentimentSummary ?? (sData?.overview ? {
    score: sData.overview.score,
    label: sData.overview.label,
    text: sData.overview.note || '',
  } : undefined);
  const socialSummary = insights?.socialSummary ?? sData?.social;
  const chartData = insights?.chartData ?? undefined;
  const extraInfo = insights?.extraInfo ?? { news: sData?.news };

  const badgeIntensity = useMemo(() => {
    const score = sentimentSummary?.score ?? 0;
    if (score >= 0.35) return 'strong-bull';
    if (score >= 0.1) return 'moderate-bull';
    if (score <= -0.35) return 'strong-bear';
    if (score <= -0.1) return 'moderate-bear';
    return 'neutral';
  }, [sentimentSummary]);

  if (!isOpen || !hasData) return null;

  return (
    <div className="insight-overlay" onClick={onClose}>
      <div
        className="insight-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="insight-header">
          <div className="insight-title-block">
            <div className="insight-symbol-row">
              <span className="insight-symbol">{tokenSymbol}</span>
              {tokenName && tokenName !== tokenSymbol && (
                <span className="insight-name">· {tokenName}</span>
              )}
            </div>
            <div className="insight-price-row">
              {price != null && (
                <span className="insight-price">
                  ${Number(price).toLocaleString(undefined, {
                    minimumFractionDigits: 0,
                    maximumFractionDigits: 8,
                  })}
                </span>
              )}
              <span className="insight-change-pills">
                {change1m != null && (
                  <span
                    className={[
                      'insight-pill',
                      change1m >= 0 ? 'is-gain' : 'is-loss',
                    ].join(' ')}
                  >
                    1m {change1m >= 0 ? '+' : ''}
                    {change1m.toFixed(2)}%
                  </span>
                )}
                {change3m != null && (
                  <span
                    className={[
                      'insight-pill',
                      change3m >= 0 ? 'is-gain' : 'is-loss',
                    ].join(' ')}
                  >
                    3m {change3m >= 0 ? '+' : ''}
                    {change3m.toFixed(2)}%
                  </span>
                )}
              </span>
            </div>
          </div>

          <button
            type="button"
            className="insight-close"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <div className="insight-tabs">
          {TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              className={
                'insight-tab' + (activeTab === tab ? ' is-active' : '')
              }
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </div>

        <div className="insight-body">
          {activeTab === 'Charts' && (
            <div className="insight-section insight-charts">
              {chartData ? (
                <div className="insight-chart-placeholder">[chart goes here]</div>
              ) : (
                <p className="insight-empty">No chart data yet.</p>
              )}
            </div>
          )}

          {activeTab === 'Sentiment' && (
            <div className="insight-section insight-sentiment">
              <div className={`insight-sentiment-badge ${badgeIntensity}`}>
                {sentimentSummary?.label || 'Neutral'}
              </div>
              <p className="insight-sentiment-text">
                {sentimentSummary?.text || 'No sentiment summary yet.'}
              </p>
              {sentimentSummary?.sources && (
                <ul className="insight-source-list">
                  {sentimentSummary.sources.map((s) => (
                    <li key={s.id || s.label}>
                      <span className="source-label">{s.label}</span>
                      <span className="source-score">{s.score > 0 ? '+' : ''}{s.score.toFixed(2)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {activeTab === 'Social' && (
            <div className="insight-section insight-social">
              <p className="insight-social-text">{socialSummary?.text || 'No social activity summary yet.'}</p>
              {socialSummary?.metrics && (
                <div className="insight-metric-row">
                  {socialSummary.metrics.map((m) => (
                    <div key={m.label} className="insight-metric-pill">
                      <span className="metric-label">{m.label}</span>
                      <span className="metric-value">{m.value}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'Info' && (
            <div className="insight-section insight-info">
              <p className="insight-info-text">{extraInfo?.description || 'No additional token info wired in yet.'}</p>
              {extraInfo?.links && extraInfo.links.length > 0 && (
                <ul className="insight-link-list">
                  {extraInfo.links.map((link) => (
                    <li key={link.href}>
                      <a href={link.href} target="_blank" rel="noreferrer">{link.label || link.href}</a>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

InsightPanel.propTypes = {
  isOpen: PropTypes.bool,
  token: PropTypes.object,
  insights: PropTypes.shape({
    sentimentSummary: PropTypes.object,
    socialSummary: PropTypes.object,
    chartData: PropTypes.any,
    extraInfo: PropTypes.object,
  }),
  onClose: PropTypes.func,
};
