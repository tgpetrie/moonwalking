import React, { useState, useMemo, useRef, useEffect } from 'react';
import { TrendingUp, Activity, AlertTriangle } from 'lucide-react';
import { useTieredSentiment } from '../hooks/useTieredSentiment';
import TradingViewChart from './charts/TradingViewChart';
import { Chart as ChartJS, registerables } from 'chart.js';

// Register Chart.js components
ChartJS.register(...registerables);

const TIER_ICONS = {
  tier1: 'T1',
  tier2: 'T2',
  tier3: 'T3',
  fringe: 'FX'
};

const TIER_ORDER = {
  tier1: 1,
  tier2: 2,
  tier3: 3,
  fringe: 4
};

const TIER_LABELS = {
  tier1: 'Tier 1 · Institutional',
  tier2: 'Tier 2 · Professional',
  tier3: 'Tier 3 · Retail',
  fringe: 'Fringe · Schizo'
};

/**
 * Advanced Sentiment Analysis Popup
 * Multi-tab interface with live data, charts, and insights
 */
const SentimentPopupAdvanced = ({ isOpen, onClose, symbol = 'BTC' }) => {
  const [activeTab, setActiveTab] = useState('overview');
  const { data: sentimentData, loading, error, refresh, pipelineHealth, tieredData, sources: pipelineSources } = useTieredSentiment(symbol);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Chart references
  const trendChartRef = useRef(null);
  const pieChartRef = useRef(null);
  const tierChartRef = useRef(null);
  const correlationChartRef = useRef(null);

  const chartInstancesRef = useRef({});

  const sortedSources = useMemo(() => {
    if (!pipelineSources || !pipelineSources.length) return [];
    return [...pipelineSources].sort((a, b) => {
      const tierA = TIER_ORDER[a.tier] ?? 99;
      const tierB = TIER_ORDER[b.tier] ?? 99;
      if (tierA !== tierB) return tierA - tierB;
      return (b.trust_weight ?? 0) - (a.trust_weight ?? 0);
    });
  }, [pipelineSources]);

  const formatTimestamp = (value) => {
    if (!value) return '--:--';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const getTierBadgeLabel = (tier) => {
    if (!tier) return 'UNKNOWN';
    if (tier === 'fringe') return 'FRINGE';
    const match = tier.match(/tier(\d)/i);
    if (match) return `TIER ${match[1]}`;
    return tier.replace('-', ' ').toUpperCase();
  };

  const getSourceScoreLabel = (score) => {
    if (typeof score !== 'number') return '--';
    return `${(score * 100).toFixed(1)}%`;
  };

  // Close on Escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  // Initialize charts when switching to charts tab
  useEffect(() => {
    if (activeTab === 'charts' && sentimentData && isOpen) {
      setTimeout(() => initCharts(), 100);
    }

    return () => {
      // Cleanup charts on unmount or tab change
      if (activeTab !== 'charts') {
        Object.values(chartInstancesRef.current).forEach(chart => {
          if (chart) chart.destroy();
        });
        chartInstancesRef.current = {};
      }
    };
  }, [activeTab, sentimentData, isOpen]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refresh();
    setTimeout(() => setIsRefreshing(false), 1000);
  };

  const handleOverlayClick = (e) => {
    if (e.target.classList.contains('sentiment-overlay')) {
      onClose();
    }
  };

  const getSentimentClass = (score) => {
    if (score >= 60) return 'positive';
    if (score <= 40) return 'negative';
    return 'neutral';
  };

  const getFearGreedLabel = (fg) => {
    if (fg >= 90) return 'Extreme Greed';
    if (fg >= 75) return 'Greed';
    if (fg >= 55) return 'Mild Greed';
    if (fg >= 45) return 'Neutral';
    if (fg >= 25) return 'Fear';
    return 'Extreme Fear';
  };

  const getFearGreedClass = (fg) => {
    if (fg >= 55) return 'positive';
    if (fg <= 45) return 'negative';
    return 'neutral';
  };

  const generateTopInsight = (score, fg) => {
    if (fg > 80) {
      return {
        type: 'alert',
        icon: <AlertTriangle size={16} />,
        title: 'Extreme Greed Detected',
        message: `Fear & Greed at ${fg} suggests market euphoria. Historical data shows this often precedes corrections. Consider taking profits on winning positions.`
      };
    }

    if (fg < 20) {
      return {
        type: 'bullish',
        icon: <TrendingUp size={16} />,
        title: 'Extreme Fear = Opportunity',
        message: `Fear & Greed at ${fg} indicates maximum fear. Warren Buffett: "Be greedy when others are fearful." This could be a buying opportunity for long-term holders.`
      };
    }

    if (score > 75) {
      return {
        type: 'bullish',
        icon: <TrendingUp size={16} />,
        title: 'Strong Bullish Sentiment',
        message: `Overall sentiment at ${score}/100 shows broad market optimism. Momentum favors buyers, but watch for overbought conditions.`
      };
    }

    if (score < 35) {
      return {
        type: 'bearish',
        icon: <Activity size={16} />,
        title: 'Bearish Sentiment Prevailing',
        message: `Sentiment at ${score}/100 indicates widespread pessimism. This could mean continued downside or a contrarian buying opportunity.`
      };
    }

    return {
      type: 'neutral',
      icon: <Activity size={16} />,
      title: 'Market in Equilibrium',
      message: `Sentiment at ${score}/100 with F&G at ${fg} shows balanced market conditions. Good time to research and build positions gradually.`
    };
  };

  const updateGaugePosition = (score) => {
    // Calculate needle position (180° to 0°)
    const angle = 180 - (score / 100 * 180);
    const radians = angle * Math.PI / 180;
    const cx = 100 + 80 * Math.cos(radians);
    const cy = 100 - 80 * Math.sin(radians);

    const offset = 251.2 - (251.2 * score / 100);

    return { cx, cy, offset };
  };

  const initCharts = () => {
    if (!sentimentData) return;

    try {
      initTrendChart();
      initPieChart();
      initTierChart();
      initCorrelationChart();
    } catch (error) {
      console.error('Error initializing charts:', error);
    }
  };

  const initTrendChart = () => {
    const canvas = trendChartRef.current;
    if (!canvas) return;

    if (chartInstancesRef.current.trend) {
      chartInstancesRef.current.trend.destroy();
    }

    const history = sentimentData.sentimentHistory || [];

    const labels = history.map(h => {
      const date = new Date(h.timestamp);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    });

    const sentimentScores = history.map(h => h.sentiment * 100);
    const fgScores = history.map(h => h.fearGreed || h.sentiment * 100);

    chartInstancesRef.current.trend = new ChartJS(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Overall Sentiment',
            data: sentimentScores,
            borderColor: '#ae4bf5',
            backgroundColor: 'rgba(174, 75, 245, 0.1)',
            fill: true,
            tension: 0.4,
            pointRadius: 0,
            pointHoverRadius: 4
          },
          {
            label: 'Fear & Greed',
            data: fgScores,
            borderColor: '#45ffb3',
            backgroundColor: 'transparent',
            borderDash: [5, 5],
            tension: 0.4,
            pointRadius: 0,
            pointHoverRadius: 4
          }
        ]
      },
      options: getChartOptions('Sentiment Score')
    });
  };

  const initPieChart = () => {
    const canvas = pieChartRef.current;
    if (!canvas) return;

    if (chartInstancesRef.current.pie) {
      chartInstancesRef.current.pie.destroy();
    }

    const breakdown = sentimentData.sourceBreakdown || { tier1: 2, tier2: 3, tier3: 0 };

    chartInstancesRef.current.pie = new ChartJS(canvas, {
      type: 'doughnut',
      data: {
        labels: ['Tier 1', 'Tier 2', 'Tier 3'],
        datasets: [{
          data: [breakdown.tier1 || 0, breakdown.tier2 || 0, breakdown.tier3 || 0],
          backgroundColor: ['#45ffb3', '#f1b43a', '#ae4bf5'],
          borderColor: '#141414',
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              color: '#a3a3a3',
              font: { family: 'Raleway', size: 11 },
              padding: 15
            }
          }
        },
        cutout: '60%'
      }
    });
  };

  const initTierChart = () => {
    const canvas = tierChartRef.current;
    if (!canvas) return;

    if (chartInstancesRef.current.tier) {
      chartInstancesRef.current.tier.destroy();
    }

    // Calculate average sentiment by tier from social breakdown
    const avgScores = [
      sentimentData.fearGreedIndex || 65,
      ((sentimentData.socialBreakdown?.news || 0.7) * 100),
      ((sentimentData.socialBreakdown?.reddit || 0.65) * 100 +
       (sentimentData.socialBreakdown?.twitter || 0.6) * 100 +
       (sentimentData.socialBreakdown?.telegram || 0.5) * 100 +
       (sentimentData.socialBreakdown?.stocktwits || 0.5) * 100 +
       (sentimentData.socialBreakdown?.custom || 0.5) * 100) / 5
    ];

    chartInstancesRef.current.tier = new ChartJS(canvas, {
      type: 'bar',
      data: {
        labels: ['Tier 1', 'Tier 2', 'Tier 3'],
        datasets: [{
          label: 'Avg. Sentiment',
          data: avgScores,
          backgroundColor: ['rgba(69, 255, 179, 0.6)', 'rgba(241, 180, 58, 0.6)', 'rgba(174, 75, 245, 0.6)'],
          borderColor: ['#45ffb3', '#f1b43a', '#ae4bf5'],
          borderWidth: 1,
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: {
            beginAtZero: true,
            max: 100,
            grid: { color: 'rgba(255,255,255,0.05)' },
            ticks: { color: '#666' }
          },
          x: {
            grid: { display: false },
            ticks: { color: '#a3a3a3', font: { family: 'Raleway', size: 10 } }
          }
        }
      }
    });
  };

  const initCorrelationChart = () => {
    const canvas = correlationChartRef.current;
    if (!canvas) return;

    if (chartInstancesRef.current.correlation) {
      chartInstancesRef.current.correlation.destroy();
    }

    const history = sentimentData.sentimentHistory || [];

    const labels = history.map(h => {
      const date = new Date(h.timestamp);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    });

    const sentimentScores = history.map(h => h.sentiment * 100);
    const priceData = history.map(h => h.price || 45000);

    chartInstancesRef.current.correlation = new ChartJS(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'BTC Price',
            data: priceData,
            borderColor: '#f1b43a',
            backgroundColor: 'rgba(241, 180, 58, 0.1)',
            fill: true,
            tension: 0.4,
            pointRadius: 0,
            yAxisID: 'y'
          },
          {
            label: 'Sentiment',
            data: sentimentScores,
            borderColor: '#ae4bf5',
            backgroundColor: 'transparent',
            tension: 0.4,
            pointRadius: 0,
            yAxisID: 'y1'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false
        },
        plugins: {
          legend: {
            position: 'top',
            labels: { color: '#a3a3a3', font: { family: 'Raleway', size: 11 } }
          }
        },
        scales: {
          y: {
            type: 'linear',
            position: 'left',
            grid: { color: 'rgba(255,255,255,0.05)' },
            ticks: {
              color: '#f1b43a',
              callback: v => '$' + v.toLocaleString()
            }
          },
          y1: {
            type: 'linear',
            position: 'right',
            min: 0,
            max: 100,
            grid: { display: false },
            ticks: { color: '#ae4bf5' }
          },
          x: {
            grid: { display: false },
            ticks: { color: '#666', maxTicksLimit: 8 }
          }
        }
      }
    });
  };

  const getChartOptions = (yLabel) => {
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          position: 'top',
          labels: {
            color: '#a3a3a3',
            font: { family: 'Raleway', size: 11 },
            usePointStyle: true
          }
        },
        tooltip: {
          backgroundColor: 'rgba(20, 20, 20, 0.95)',
          titleColor: '#f8f8f8',
          bodyColor: '#a3a3a3',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          padding: 12
        }
      },
      scales: {
        y: {
          min: 0,
          max: 100,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: {
            color: '#666666',
            font: { family: 'Raleway', size: 10 }
          },
          title: {
            display: true,
            text: yLabel,
            color: '#666666'
          }
        },
        x: {
          grid: { display: false },
          ticks: {
            color: '#666666',
            maxTicksLimit: 8
          }
        }
      }
    };
  };

  if (!isOpen) return null;

  const score = sentimentData ? Math.round((sentimentData.overallSentiment || sentimentData.overall || 0) * 100) : 0;
  const fg = sentimentData?.fearGreedIndex || 50;
  const insight = generateTopInsight(score, fg);
  const gaugePos = updateGaugePosition(score);

  const fallbackSourceCount = sentimentData?.sourceBreakdown
    ? Object.values(sentimentData.sourceBreakdown).reduce((a, b) => a + b, 0)
    : 5;
  const sourceCount = pipelineSources?.length || fallbackSourceCount;

  const lastUpdate = sentimentData?.timestamp
    ? new Date(sentimentData.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '--:--';

  return (
    <div
      className={`sentiment-overlay ${isOpen ? 'active' : ''}`}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="sentimentTitle"
    >
      <div className="sentiment-popup" data-sentiment-symbol={symbol}>
        {/* Header */}
        <header className="popup-header">
          <div className="header-left">
            <div className="header-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="currentColor" strokeWidth="1.5"/>
                <path d="M2 17l10 5 10-5" stroke="currentColor" strokeWidth="1.5"/>
                <path d="M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.5"/>
              </svg>
            </div>
            <div className="header-text">
              <h1 id="sentimentTitle">Sentiment Analysis</h1>
              <p className="subtitle">Multi-source market intelligence</p>
            </div>
          </div>
          <div className="header-right">
            <div className="live-indicator" role="status" aria-live="polite">
              <span className="pulse" aria-hidden="true"></span>
              <span className="live-text">LIVE</span>
            </div>
            <button className="close-btn" onClick={onClose} aria-label="Close sentiment analysis">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>
        </header>

        {/* Tab Navigation */}
        <nav className="tab-nav" role="tablist">
          <button
            className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
            role="tab"
            aria-selected={activeTab === 'overview'}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <rect x="3" y="3" width="7" height="7" rx="1"/>
              <rect x="14" y="3" width="7" height="7" rx="1"/>
              <rect x="3" y="14" width="7" height="7" rx="1"/>
              <rect x="14" y="14" width="7" height="7" rx="1"/>
            </svg>
            Overview
          </button>
          <button
            className={`tab-btn ${activeTab === 'sources' ? 'active' : ''}`}
            onClick={() => setActiveTab('sources')}
            role="tab"
            aria-selected={activeTab === 'sources'}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M12 2a10 10 0 100 20 10 10 0 000-20z"/>
              <path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10"/>
            </svg>
            Live Sources
          </button>
          <button
            className={`tab-btn ${activeTab === 'charts' ? 'active' : ''}`}
            onClick={() => setActiveTab('charts')}
            role="tab"
            aria-selected={activeTab === 'charts'}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M3 3v18h18"/>
              <path d="M7 16l4-4 4 4 6-6"/>
            </svg>
            Charts
          </button>
          <button
            className={`tab-btn ${activeTab === 'insights' ? 'active' : ''}`}
            onClick={() => setActiveTab('insights')}
            role="tab"
            aria-selected={activeTab === 'insights'}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="12" r="4"/>
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83"/>
            </svg>
            Key Insights
          </button>
        </nav>

        {/* Tab Content */}
        <main className="tab-content">
          {/* OVERVIEW TAB */}
          {activeTab === 'overview' && (
            <section className="tab-panel active" role="tabpanel">
              <div className="stats-grid">
                <div className="stat-card primary">
                  <div className="stat-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/>
                    </svg>
                  </div>
                  <div className="stat-content">
                    <span className="stat-label">Overall Sentiment</span>
                    <span className={`stat-value ${getSentimentClass(score)}`}>{score}</span>
                    <span className="stat-change">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M12 19V5M5 12l7-7 7 7"/>
                      </svg>
                      <span>Trending</span>
                    </span>
                  </div>
                </div>

                <div className="stat-card">
                  <div className="stat-icon fear-greed">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <circle cx="12" cy="12" r="10"/>
                      <path d="M8 14s1.5 2 4 2 4-2 4-2M9 9h.01M15 9h.01"/>
                    </svg>
                  </div>
                  <div className="stat-content">
                    <span className="stat-label">Fear & Greed</span>
                    <span className={`stat-value ${getFearGreedClass(fg)}`}>{fg}</span>
                    <span className="stat-sublabel">{getFearGreedLabel(fg)}</span>
                  </div>
                </div>

                <div className="stat-card">
                  <div className="stat-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <circle cx="12" cy="12" r="10"/>
                      <path d="M2 12h20"/>
                    </svg>
                  </div>
                  <div className="stat-content">
                    <span className="stat-label">Active Sources</span>
                    <span className="stat-value">{sourceCount}</span>
                    <span className="stat-sublabel">
                      T1: {sentimentData?.sourceBreakdown?.tier1 || 0} |
                      T2: {sentimentData?.sourceBreakdown?.tier2 || 0} |
                      T3: {sentimentData?.sourceBreakdown?.tier3 || 0}
                    </span>
                  </div>
                </div>

                <div className="stat-card">
                  <div className="stat-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <circle cx="12" cy="12" r="10"/>
                      <path d="M12 6v6l4 2"/>
                    </svg>
                  </div>
                  <div className="stat-content">
                    <span className="stat-label">Last Updated</span>
                    <span className="stat-value small">{lastUpdate}</span>
                    <span className="stat-sublabel">Auto-refresh: 30s</span>
                  </div>
                </div>
              </div>

              <div className="gauge-section">
                <div className="gauge-container">
                  <svg className="gauge" viewBox="0 0 200 120" role="img" aria-label="Sentiment gauge">
                    <defs>
                      <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" style={{ stopColor: '#ae4bf5' }}/>
                        <stop offset="50%" style={{ stopColor: '#f1b43a' }}/>
                        <stop offset="100%" style={{ stopColor: '#45ffb3' }}/>
                      </linearGradient>
                    </defs>
                    <path className="gauge-bg" d="M 20 100 A 80 80 0 0 1 180 100"/>
                    <path
                      className="gauge-fill"
                      d="M 20 100 A 80 80 0 0 1 180 100"
                      style={{ strokeDashoffset: gaugePos.offset }}
                    />
                    <circle
                      className="gauge-needle"
                      cx={gaugePos.cx}
                      cy={gaugePos.cy}
                      r="8"
                    />
                  </svg>
                  <div className="gauge-labels">
                    <span className="gauge-label bearish">Bearish</span>
                    <span className="gauge-label neutral">Neutral</span>
                    <span className="gauge-label bullish">Bullish</span>
                  </div>
                </div>
              </div>

              {/* Tiered Sentiment Breakdown */}
              {sentimentData?.hasTieredData && sentimentData?.tierScores && (
                <div className="info-section">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z"/>
                    </svg>
                    Who's Buying? Whale vs Retail Sentiment
                  </h3>
                  <div className="tier-breakdown-grid">
                    <div className="tier-card tier-1">
                      <div className="tier-header">
                        <span className="tier-icon">T1</span>
                        <span className="tier-label">Whales & Institutions</span>
                      </div>
                      <div className="tier-score">
                        {(sentimentData.tierScores.tier1 * 100).toFixed(0)}%
                      </div>
                      <div className="tier-bar">
                        <div
                          className="tier-bar-fill tier-1-fill"
                          style={{ width: `${sentimentData.tierScores.tier1 * 100}%` }}
                        />
                      </div>
                      <div className="tier-meta">Smart Money: CoinGecko, Fear & Greed, Binance</div>
                    </div>

                    <div className="tier-card tier-2">
                      <div className="tier-header">
                        <span className="tier-icon">T2</span>
                        <span className="tier-label">Mainstream Normies</span>
                      </div>
                      <div className="tier-score">
                        {(sentimentData.tierScores.tier2 * 100).toFixed(0)}%
                      </div>
                      <div className="tier-bar">
                        <div
                          className="tier-bar-fill tier-2-fill"
                          style={{ width: `${sentimentData.tierScores.tier2 * 100}%` }}
                        />
                      </div>
                      <div className="tier-meta">News & Big Reddit: CoinDesk, r/CC</div>
                    </div>

                    <div className="tier-card tier-3">
                      <div className="tier-header">
                        <span className="tier-icon">T3</span>
                        <span className="tier-label">Diamond Hands & Degens</span>
                      </div>
                      <div className="tier-score">
                        {(sentimentData.tierScores.tier3 * 100).toFixed(0)}%
                      </div>
                      <div className="tier-bar">
                        <div
                          className="tier-bar-fill tier-3-fill"
                          style={{ width: `${sentimentData.tierScores.tier3 * 100}%` }}
                        />
                      </div>
                      <div className="tier-meta">Apes Strong Together: r/SSB, CT, Telegram</div>
                    </div>

                    <div className="tier-card tier-fringe">
                      <div className="tier-header">
                        <span className="tier-icon">FX</span>
                        <span className="tier-label">Moonboys & Schizos</span>
                      </div>
                      <div className="tier-score">
                        {(sentimentData.tierScores.fringe * 100).toFixed(0)}%
                      </div>
                      <div className="tier-bar">
                        <div
                          className="tier-bar-fill tier-fringe-fill"
                          style={{ width: `${sentimentData.tierScores.fringe * 100}%` }}
                        />
                      </div>
                      <div className="tier-meta">Anon Intel: /biz/, BitcoinTalk, Weibo</div>
                    </div>
                  </div>

                  {/* Pipeline Status Indicator */}
                  {pipelineHealth?.running && (
                    <div className="pipeline-status success">
                      <span className="status-indicator">OK</span>
                      <span>LIVE: Scanning {sentimentData.totalDataPoints || 0} sources across all tiers - Data is healthy</span>
                    </div>
                  )}
                  {!pipelineHealth?.running && pipelineHealth?.checked && (
                    <div className="pipeline-status warning">
                      <span className="status-indicator">!</span>
                      <span>Pipeline offline - showing cached data. Start: ./start_sentiment_pipeline.sh</span>
                    </div>
                  )}
                </div>
              )}

              {/* Divergence Alerts */}
              {sentimentData?.divergenceAlerts && sentimentData.divergenceAlerts.length > 0 && (
                <div className="info-section">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                      <path d="M12 9v4M12 17h.01"/>
                    </svg>
                    Divergence Alerts
                  </h3>
                  <div className="divergence-alerts">
                    {sentimentData.divergenceAlerts.map((alert, idx) => (
                      <div key={idx} className={`alert-box ${alert.type}`}>
                        <span className="alert-icon">
                          {alert.type === 'warning' ? '!' : 'i'}
                        </span>
                        <div className="alert-content">
                          <p>{alert.message}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="info-section">
                <h3>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <circle cx="12" cy="12" r="4"/>
                    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83"/>
                  </svg>
                  Top Insight
                </h3>
                <div className={`insight-box ${insight.type}`}>
                  <span className="insight-icon">{insight.icon}</span>
                  <div className="insight-content">
                    <strong>{insight.title}</strong>
                    <p>{insight.message}</p>
                  </div>
                </div>
              </div>

              <div className="info-section">
                <h3>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <circle cx="12" cy="12" r="10"/>
                    <path d="M12 16v-4M12 8h.01"/>
                  </svg>
                  How to Read the Tea Leaves
                </h3>
                <div className="explainer-box">
                  <p>This analysis scans <strong>{sourceCount}+</strong> live sources from Whales to Anons. <strong>Smart money</strong> gets more weight than <strong>Retail sentiment</strong>. When whales buy while apes panic = accumulation zone. When retail FOMOs while whales sell = possible top. Click <strong>Live Sources</strong> to verify - trust, but verify anon.</p>
                </div>
              </div>
            </section>
          )}

          {/* SOURCES TAB */}
          {activeTab === 'sources' && (
            <section className="tab-panel active" role="tabpanel">
              <div className="info-section">
                <div className="section-header">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <circle cx="12" cy="12" r="10"/>
                      <path d="M2 12h20"/>
                    </svg>
                    Live Data Sources
                  </h3>
                  <p className="section-desc">Sources are rendered directly from the pipeline inventory (via /api/sentiment/sources).</p>
                </div>

                <div className="tier-legend">
                  <div className="legend-item tier-1">
                    <span className="legend-dot"></span>
                    <span className="legend-label">Tier 1: Institutional</span>
                    <span className="legend-weight">0.85 weight</span>
                  </div>
                  <div className="legend-item tier-2">
                    <span className="legend-dot"></span>
                    <span className="legend-label">Tier 2: Professional</span>
                    <span className="legend-weight">0.70 weight</span>
                  </div>
                  <div className="legend-item tier-3">
                    <span className="legend-dot"></span>
                    <span className="legend-label">Tier 3: Retail/Social</span>
                    <span className="legend-weight">0.50 weight</span>
                  </div>
                </div>
              </div>

              <div className="sources-list">
                {sortedSources.length > 0 ? (
                  sortedSources.map((source) => {
                    const tierKey = source.tier || 'tier3';
                    const tierClass = tierKey === 'fringe' ? 'tier-fringe' : tierKey.replace(/tier(\d)/i, 'tier-$1');
                    const badgeLabel = getTierBadgeLabel(tierKey);
                    const statusLabel = source.status ? `${source.status.charAt(0).toUpperCase()}${source.status.slice(1)}` : 'Unknown';
                    const weightLabel = typeof source.trust_weight === 'number'
                      ? source.trust_weight.toFixed(2)
                      : '--';
                    const scoreLabel = getSourceScoreLabel(source.sentiment_score);

                    return (
                      <div key={source.name} className={`source-card ${tierClass}`}>
                        <div className="source-info">
                          <div className="source-header">
                            <span className="source-icon" aria-hidden="true">{TIER_ICONS[tierKey] || 'SRC'}</span>
                            <div>
                              <div className="source-name">{source.name}</div>
                              <span className="source-status">{statusLabel}</span>
                            </div>
                          </div>
                          <div className="source-desc">
                            {TIER_LABELS[tierKey] || 'Live pipeline source'}
                          </div>
                          <div className="source-meta">
                            <span>Weight: {weightLabel}</span>
                            <span>Status: {statusLabel}</span>
                            <span>Updated: {formatTimestamp(source.last_updated)}</span>
                          </div>
                        </div>
                        <div className="source-metrics">
                          <span className={`tier-badge ${tierClass}`}>{badgeLabel}</span>
                          <span className="source-score">Score {scoreLabel}</span>
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <div className="sources-empty">
                    <p>
                      {pipelineHealth.checked && !pipelineHealth.running
                        ? 'Sentiment pipeline offline. Start the collector to reveal live sources.'
                        : 'Loading pipeline sources...'}
                    </p>
                  </div>
                )}
              </div>
            </section>
          )}

          {/* CHARTS TAB */}
          {activeTab === 'charts' && (
            <section className="tab-panel active" role="tabpanel">
              <div className="info-section">
                <div className="section-header">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M3 3v18h18"/>
                      <path d="M7 16l4-4 4 4 6-6"/>
                    </svg>
                    Sentiment Trend (24h)
                  </h3>
                  <p className="section-desc">Track how market sentiment has evolved</p>
                </div>
                <div className="chart-container">
                  <canvas ref={trendChartRef} role="img" aria-label="Sentiment trend chart"></canvas>
                </div>
              </div>

              <div className="charts-row">
                <div className="info-section half">
                  <div className="section-header">
                    <h3>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <circle cx="12" cy="12" r="10"/>
                      </svg>
                      Source Breakdown
                    </h3>
                  </div>
                  <div className="chart-container donut">
                    <canvas ref={pieChartRef} role="img" aria-label="Source breakdown"></canvas>
                  </div>
                </div>

                <div className="info-section half">
                  <div className="section-header">
                    <h3>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M18 20V10M12 20V4M6 20v-6"/>
                      </svg>
                      Tier Comparison
                    </h3>
                  </div>
                  <div className="chart-container donut">
                    <canvas ref={tierChartRef} role="img" aria-label="Tier comparison"></canvas>
                  </div>
                </div>
              </div>

              <div className="info-section">
                <div className="section-header">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
                    </svg>
                    Sentiment vs Price Correlation
                  </h3>
                  <p className="section-desc">How sentiment aligns with BTC price movement</p>
                </div>
                <div className="chart-container">
                  <canvas ref={correlationChartRef} role="img" aria-label="Correlation chart"></canvas>
                </div>
              </div>
            </section>
          )}

          {/* INSIGHTS TAB */}
          {activeTab === 'insights' && (
            <section className="tab-panel active" role="tabpanel">
              <div className="info-section">
                <div className="section-header">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <circle cx="12" cy="12" r="4"/>
                      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83"/>
                    </svg>
                    Market Insights
                  </h3>
                  <p className="section-desc">AI-generated analysis based on multi-source data</p>
                </div>

                <div className="insights-list">
                  <div className={`insight-box ${insight.type}`}>
                    <span className="insight-icon">{insight.icon}</span>
                    <div className="insight-content">
                      <strong>{insight.title}</strong>
                      <p>{insight.message}</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="info-section">
                <div className="disclaimer-box">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                    <path d="M12 9v4M12 17h.01"/>
                  </svg>
                  <p><strong>Disclaimer:</strong> This is sentiment analysis, not financial advice. Always do your own research and consider your risk tolerance before making investment decisions.</p>
                </div>
              </div>
            </section>
          )}
        </main>

        {/* Footer */}
        <footer className="popup-footer">
          <div className="footer-left">
            <span className="data-source">Powered by real-time data from <span>{sourceCount}+</span> sources</span>
          </div>
          <div className="footer-right">
            <button
              className={`refresh-btn ${isRefreshing ? 'refreshing' : ''}`}
              onClick={handleRefresh}
              aria-label="Refresh sentiment data"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M23 4v6h-6M1 20v-6h6"/>
                <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
              </svg>
              Refresh Now
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
};

export default SentimentPopupAdvanced;
