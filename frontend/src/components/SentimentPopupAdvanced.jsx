import React, { useState, useMemo, useRef, useEffect } from 'react';
import { TrendingUp, Activity, AlertTriangle } from 'lucide-react';
import { useMarketHeat } from '../hooks/useMarketHeat';
import { Chart as ChartJS, registerables } from 'chart.js';
import '../styles/sentiment-popup-advanced.css';
import { SkeletonBlock, SkeletonCard, SkeletonText } from './ui/Skeleton';

// Register Chart.js components
ChartJS.register(...registerables);


/**
 * Advanced Sentiment Analysis Popup
 * Multi-tab interface with live data, charts, and insights
 */
const resolveTvSymbol = (sym, exchange = 'auto') => {
  const s = String(sym || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  const coinbase = s ? `COINBASE:${s}USD` : 'COINBASE:BTCUSD';
  const binance = s ? `BINANCE:${s}USDT` : 'BINANCE:BTCUSDT';

  if (exchange === 'coinbase') return { symbol: coinbase, source: 'coinbase' };
  if (exchange === 'binance') return { symbol: binance, source: 'binance' };

  // auto: prefer Coinbase for well-known majors, fallback to Binance for long/odd tickers
  if (!s) return { symbol: coinbase, source: 'coinbase' };
  if (s === 'BTC') return { symbol: 'COINBASE:BTCUSD', source: 'coinbase' };
  if (s === 'ETH') return { symbol: 'COINBASE:ETHUSD', source: 'coinbase' };
  if (s.length > 6) return { symbol: binance, source: 'binance' };
  return { symbol: coinbase, source: 'coinbase' };
};

const buildTradingViewEmbedUrl = (tvSymbol) => {
  const params = new URLSearchParams({
    symbol: tvSymbol,
    interval: '15',
    theme: 'dark',
    style: '1',
    timezone: 'Etc/UTC',
    withdateranges: '1',
    hide_side_toolbar: '0',
    allow_symbol_change: '1',
  });
  return `https://s.tradingview.com/widgetembed/?${params.toString()}`;
};

const SentimentPopupAdvanced = ({ isOpen, onClose, symbol = 'BTC' }) => {
  const REFRESH_MS = 15000;
  const [activeTab, setActiveTab] = useState('overview');
  const [chartExchange, setChartExchange] = useState('auto'); // auto | coinbase | binance
  const { data: sentimentData, loading, error, refresh, pipelineHealth } = useMarketHeat();
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Optional debug: Log symbol on open for debugging
  useEffect(() => {
    if (isOpen && symbol) {
      try {
        if (localStorage.getItem("mw_debug_sentiment") === "1") {
          console.log("[SentimentPopup] Opened with symbol:", symbol);
        }
      } catch {}
    }
  }, [isOpen, symbol]);

  // Chart references
  const trendChartRef = useRef(null);

  const chartInstancesRef = useRef({});

  const destroyChart = (key) => {
    const chart = chartInstancesRef.current[key];
    if (chart) {
      chart.destroy();
      delete chartInstancesRef.current[key];
    }
  };

  const ensureChart = (key, canvas, factoryFn) => {
    if (!canvas) return null;
    if (!chartInstancesRef.current[key]) {
      chartInstancesRef.current[key] = factoryFn();
    }
    return chartInstancesRef.current[key];
  };

  const updateChart = (chart, { labels, datasets }) => {
    if (!chart) return;
    chart.data.labels = labels;
    chart.data.datasets = datasets;
    chart.update('none');
  };

  const sentimentHistory = Array.isArray(sentimentData?.sentimentHistory)
    ? sentimentData.sentimentHistory
    : [];
  const divergenceAlerts = Array.isArray(sentimentData?.divergenceAlerts)
    ? sentimentData.divergenceAlerts
    : [];
  const tapeHeat = sentimentData?.tapeHeat || sentimentData?.raw?.tape_heat || sentimentData?.raw?.tapeHeat || {};
  const tapeComponents = sentimentData?.components || sentimentData?.raw?.components || {};

  const breadthPct = Number.isFinite(tapeHeat?.breadth) ? tapeHeat.breadth * 100 : null;
  const alignment = Number.isFinite(tapeHeat?.momentum_alignment) ? tapeHeat.momentum_alignment : null;
  const volatility = Number.isFinite(tapeHeat?.volatility) ? tapeHeat.volatility : null;
  const avg1m = Number.isFinite(tapeComponents?.avg_return_1m) ? tapeComponents.avg_return_1m : null;
  const avg3m = Number.isFinite(tapeComponents?.avg_return_3m) ? tapeComponents.avg_return_3m : null;
  const greenCount = Number.isFinite(tapeComponents?.green_count) ? tapeComponents.green_count : null;
  const totalSymbols = Number.isFinite(tapeComponents?.total_symbols) ? tapeComponents.total_symbols : null;

  // Don't forge 50 when missing - keep null
  const fearGreedIndex = Number.isFinite(sentimentData?.fearGreedIndex)
    ? sentimentData.fearGreedIndex
    : null;

  const safeAlerts = useMemo(() => {
    return divergenceAlerts
      .map((a) => {
        const message = typeof a?.message === 'string' ? a.message : String(a?.message ?? '').trim();
        const type = typeof a?.type === 'string' ? a.type : 'info';
        if (!message) return null;
        return { type, message };
      })
      .filter(Boolean);
  }, [divergenceAlerts]);


  const formatTimestamp = (value) => {
    if (!value) return '--:--';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
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
      if (activeTab !== 'charts') {
        Object.values(chartInstancesRef.current).forEach(chart => {
          if (chart) chart.destroy();
        });
        chartInstancesRef.current = {};
      }
    };
  }, [activeTab, sentimentData, isOpen, sentimentHistory]);

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

  const formatNumberShort = (num) => {
    if (!Number.isFinite(num)) return 'N/A';
    const abs = Math.abs(num);
    if (abs >= 1e12) return `${(num / 1e12).toFixed(2)}T`;
    if (abs >= 1e9) return `${(num / 1e9).toFixed(2)}B`;
    if (abs >= 1e6) return `${(num / 1e6).toFixed(2)}M`;
    if (abs >= 1e3) return `${(num / 1e3).toFixed(1)}K`;
    return num.toFixed(2);
  };

  const getFearGreedLabel = (fg) => {
    if (!Number.isFinite(fg)) return 'Missing';
    if (fg >= 90) return 'Extreme Greed';
    if (fg >= 75) return 'Greed';
    if (fg >= 55) return 'Mild Greed';
    if (fg >= 45) return 'Neutral';
    if (fg >= 25) return 'Fear';
    return 'Extreme Fear';
  };

  const getFearGreedClass = (fg) => {
    if (!Number.isFinite(fg)) return 'neutral';
    if (fg >= 55) return 'positive';
    if (fg <= 45) return 'negative';
    return 'neutral';
  };

  const generateTopInsight = (score, fg) => {
    // Handle missing data
    if (score === null && !Number.isFinite(fg)) {
      return {
        type: 'neutral',
        icon: <Activity size={16} />,
        title: 'Sentiment Unavailable',
        message: 'Pipeline warming up or offline. No sentiment data to analyze yet.'
      };
    }

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

    if (score !== null && score > 75) {
      return {
        type: 'bullish',
        icon: <TrendingUp size={16} />,
        title: 'Strong Bullish Sentiment',
        message: `Overall sentiment at ${score}/100 shows broad market optimism. Momentum favors buyers, but watch for overbought conditions.`
      };
    }

    if (score !== null && score < 35) {
      return {
        type: 'bearish',
        icon: <Activity size={16} />,
        title: 'Bearish Sentiment Prevailing',
        message: `Sentiment at ${score}/100 indicates widespread pessimism. This could mean continued downside or a contrarian buying opportunity.`
      };
    }

    const scoreText = score !== null ? `${score}/100` : 'unavailable';
    const fgText = Number.isFinite(fg) ? `F&G at ${fg}` : 'F&G unavailable';
    return {
      type: 'neutral',
      icon: <Activity size={16} />,
      title: 'Market in Equilibrium',
      message: `Sentiment ${scoreText} with ${fgText} shows balanced market conditions. Good time to research and build positions gradually.`
    };
  };

  const updateGaugePosition = (score) => {
    // If score is null, hide needle at center with full offset (empty gauge)
    const s = score ?? 50; // visual fallback only
    const angle = 180 - (s / 100 * 180);
    const radians = angle * Math.PI / 180;
    const cx = 100 + 80 * Math.cos(radians);
    const cy = 100 - 80 * Math.sin(radians);

    // If null, show empty gauge (full offset)
    const offset = score === null ? 251.2 : 251.2 - (251.2 * score / 100);

    return { cx, cy, offset, isNull: score === null };
  };

  const initCharts = () => {
    if (!sentimentData) return;

    try {
      initTrendChart();
    } catch (error) {
      console.error('Error initializing charts:', error);
    }
  };

  const initTrendChart = () => {
    const canvas = trendChartRef.current;
    if (!canvas) return;

    const history = sentimentHistory;

    if (!history.length) {
      if (chartInstancesRef.current.trend) {
        destroyChart('trend');
      }
      return;
    }

    const labels = history.map(h => {
      const date = new Date(h.timestamp);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    });

    const sentimentScores = history.map(h => (typeof h.sentiment === 'number' ? h.sentiment * 100 : null));

    const datasets = [
      {
        label: 'Overall Sentiment',
        data: sentimentScores,
        borderColor: '#ae4bf5',
        backgroundColor: 'rgba(174, 75, 245, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 4
      }
    ];

    const chart = ensureChart('trend', canvas, () => new ChartJS(canvas, {
      type: 'line',
      data: { labels, datasets },
      options: getChartOptions('Sentiment (0-100)')
    }));

    updateChart(chart, { labels, datasets });
  };

  // Removed tier/source/correlation/social charts for local tape heat

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

  // null when missing - don't forge 50
  const score = sentimentData?.overallSentiment != null
    ? Math.round(sentimentData.overallSentiment * 100)
    : null;
  const fg = Number.isFinite(sentimentData?.fearGreedIndex) ? Number(sentimentData.fearGreedIndex) : null;
  const fgStatus = sentimentData?.fearGreedStatus || (Number.isFinite(fg) ? "LIVE" : "UNAVAILABLE");
  const fgUpdatedLabel = formatTimestamp(sentimentData?.fearGreedUpdatedAt);
  const insight = generateTopInsight(score, Number.isFinite(fg) ? fg : score);
  const gaugePos = updateGaugePosition(score);

  const tvResolved = resolveTvSymbol(symbol, chartExchange);
  const tvUrl = buildTradingViewEmbedUrl(tvResolved.symbol);

  const sourceCount = Number.isFinite(fg) ? 2 : 1;
  const regimeRaw = (sentimentData?.regime || "unknown").toString();
  const regimeDisplay = regimeRaw.toUpperCase();
  const confidenceDisplay = Number.isFinite(sentimentData?.confidence)
    ? Number(sentimentData.confidence).toFixed(2)
    : "--";
  const reasonLines = Array.isArray(sentimentData?.reasons)
    ? sentimentData.reasons.slice(0, 2)
    : [];

  const lastUpdatedMsRaw =
    sentimentData?.pipelineTimestamp ??
    sentimentData?.timestamp ??
    sentimentData?.updatedAt ??
    null;
  const lastUpdatedMs = Number.isFinite(Date.parse(lastUpdatedMsRaw || "")) ? Date.parse(lastUpdatedMsRaw) : Date.now();
  const lastUpdate = Number.isFinite(lastUpdatedMs)
    ? new Date(lastUpdatedMs).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '--:--';
  const status =
    sentimentData?.pipelineStatus ??
    (pipelineHealth?.pipelineRunning ? "LIVE" : "OFFLINE");
  const statusLower = String(status).toLowerCase();
  const staleSeconds =
    sentimentData?.sentimentMeta?.staleSeconds ??
    sentimentData?.sentimentMeta?.stale_seconds ??
    null;
  const statusTitle =
    status === "STALE" && typeof staleSeconds === "number"
      ? `STALE — ${Math.round(staleSeconds)}s stale`

      ++++























































































































































































      ------------------++++++++++------------------+++++++++++++++++++++++++++++++++++++      : status === "OFFLINE"
        ? "OFFLINE — tape engine not ready"
        : "LIVE";

  useEffect(() => {
    if (!import.meta.env.DEV || !isOpen || !sentimentData) return;
    if (window.__MW_SENTIMENT_LOGGED__) return;
    window.__MW_SENTIMENT_LOGGED__ = true;
    console.debug("[sentiment] sample payload", {
      overallSentiment: sentimentData.overallSentiment,
      fearGreedIndex: sentimentData.fearGreedIndex,
      tapeHeat,
      components: tapeComponents,
    });
  }, [isOpen, sentimentData, tapeHeat, tapeComponents]);

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
              <h1 id="sentimentTitle">Sentiment Analysis {symbol ? `· ${symbol}` : ''}</h1>
              <p className="subtitle">Tape + Fear &amp; Greed intelligence</p>
            </div>
          </div>
          <div className="header-right">
            <div
              className={`live-indicator ${statusLower}`}
              title={statusTitle}
              role="status"
              aria-live="polite"
            >
              <span className={`pulse ${statusLower}`} aria-hidden="true"></span>
              <span className="live-text">{status}</span>
            </div>
            <button className="close-btn" onClick={onClose} aria-label="Close sentiment analysis">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>
        </header>

        {/* Dev debug strip (visible only in dev to verify data presence) */}
        {import.meta.env.DEV && (
          <div className="dev-strip">
            normalized: {String(Boolean(sentimentData?.normalized))} ·
            hist: {sentimentHistory.length} ·
            breadth: {breadthPct != null ? `${Math.round(breadthPct)}%` : "n/a"} ·
            vol: {volatility != null ? `${volatility.toFixed(2)}%` : "n/a"} ·
            sources: {sourceCount} ·
            timestamp: {sentimentData?.pipelineTimestamp || 'n/a'}
            {!sentimentHistory.length && ' · No history returned yet'}
          </div>
        )}

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
          {/* Loading State */}
          {loading && (
            <div className="loading-skeleton">
              <div className="skeleton-header">
                <SkeletonBlock w="220px" h={24} radius={8} />
                <SkeletonBlock w="160px" h={14} radius={6} />
              </div>
              <div className="skeleton-grid">
                {[...Array(4)].map((_, idx) => (
                  <SkeletonCard key={idx} className="skeleton-stat-card">
                    <SkeletonBlock w="36px" h="36px" radius={12} />
                    <SkeletonText lines={2} lineH={12} widths={['70%', '50%']} />
                  </SkeletonCard>
                ))}
              </div>
              <SkeletonBlock h={180} radius={20} className="loading-gauge" />
              <SkeletonBlock h={260} radius={16} className="loading-chart" />
              <div className="loading-footer-text">
                Fetching from {sourceCount ? `${sourceCount} sources` : 'tape sources'}
              </div>
            </div>
          )}

          {!loading && error && (
            <div style={{ padding: '1rem', margin: '0 0 1rem 0', background: '#2b1a1a', color: '#ff9b9b', borderRadius: '8px' }}>
              Failed to load sentiment data: {String(error)}
            </div>
          )}

          {/* OVERVIEW TAB */}
          {!loading && activeTab === 'overview' && (
            <section className="tab-panel active" role="tabpanel">
              <div className="sentiment-meta-line">
                REGIME: {regimeDisplay} | CONFIDENCE: {confidenceDisplay}
              </div>
              {reasonLines.map((r, idx) => (
                <div key={`reason-${idx}`} className="sentiment-reason">{r}</div>
              ))}
              <div className="stats-grid">
                <div className="stat-card primary">
                  <div className="stat-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/>
                    </svg>
                  </div>
                  <div className="stat-content">
                    <span className="stat-label">Overall Sentiment</span>
                    <span className={`stat-value ${score !== null ? getSentimentClass(score) : 'muted'}`}>{score !== null ? score : '—'}</span>
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
                    <span className={`stat-value ${getFearGreedClass(fg)}`}>{Number.isFinite(fg) ? fg : "N/A"}</span>
                    <span className="stat-sublabel">
                      {getFearGreedLabel(fg)}
                      {" · "}
                      {fgStatus}
                      {fgUpdatedLabel ? ` · ${fgUpdatedLabel}` : ""}
                    </span>
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
                    <span className="stat-label">Tape Breadth</span>
                    <span className="stat-value">{breadthPct != null ? `${Math.round(breadthPct)}%` : "N/A"}</span>
                    <span className="stat-sublabel">
                      {greenCount != null && totalSymbols != null
                        ? `${greenCount}/${totalSymbols} green · Avg 1m ${avg1m != null ? `${avg1m.toFixed(2)}%` : "—"}`
                        : "Coverage warming"}
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
                  <span className="stat-sublabel">Auto-refresh: {Math.round(REFRESH_MS / 1000)}s</span>
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

              {/* Tape Heat Breakdown */}
              <div className="info-section">
                <h3>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z"/>
                  </svg>
                  Tape Heat Breakdown
                </h3>
                <div className="tier-breakdown-grid">
                  <div className="tier-card tier-1">
                    <div className="tier-header">
                      <span className="tier-icon">BR</span>
                      <span className="tier-label">Breadth (3m)</span>
                    </div>
                    <div className="tier-score">
                      {breadthPct != null ? `${Math.round(breadthPct)}%` : '—'}
                    </div>
                    <div className="tier-bar">
                      <div
                        className="tier-bar-fill tier-1-fill"
                        style={{ width: breadthPct != null ? `${Math.min(100, Math.max(0, breadthPct))}%` : '0%' }}
                      />
                    </div>
                    <div className="tier-meta">
                      {greenCount != null && totalSymbols != null ? `${greenCount}/${totalSymbols} green` : 'Coverage warming'}
                    </div>
                  </div>

                  <div className="tier-card tier-2">
                    <div className="tier-header">
                      <span className="tier-icon">MO</span>
                      <span className="tier-label">Momentum Align</span>
                    </div>
                    <div className="tier-score">
                      {alignment != null ? alignment.toFixed(2) : '—'}
                    </div>
                    <div className="tier-bar">
                      <div
                        className="tier-bar-fill tier-2-fill"
                        style={{ width: alignment != null ? `${Math.min(100, Math.max(0, (alignment + 1) * 50))}%` : '0%' }}
                      />
                    </div>
                    <div className="tier-meta">
                      1m avg {avg1m != null ? `${avg1m.toFixed(2)}%` : '—'} · 3m avg {avg3m != null ? `${avg3m.toFixed(2)}%` : '—'}
                    </div>
                  </div>

                  <div className="tier-card tier-3">
                    <div className="tier-header">
                      <span className="tier-icon">VO</span>
                      <span className="tier-label">Volatility</span>
                    </div>
                    <div className="tier-score">
                      {volatility != null ? `${volatility.toFixed(2)}%` : '—'}
                    </div>
                    <div className="tier-bar">
                      <div
                        className="tier-bar-fill tier-3-fill"
                        style={{ width: volatility != null ? `${Math.min(100, Math.max(0, volatility * 10))}%` : '0%' }}
                      />
                    </div>
                    <div className="tier-meta">3m return dispersion (stdev)</div>
                  </div>
                </div>
              </div>

              {/* Divergence Alerts */}
              {safeAlerts.length > 0 && (
                <div className="info-section">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                      <path d="M12 9v4M12 17h.01"/>
                    </svg>
                    Divergence Alerts
                  </h3>
                  <div className="divergence-alerts">
                    {safeAlerts.map((alert, idx) => (
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
                  <p><strong>Tape Heat:</strong> Breadth = % green (3m), Momentum = 1m vs 3m alignment, Volatility = 3m dispersion. These feed the overall score.</p>
                  <p><strong>Charts:</strong> The gauge and trend line use <code>overallSentiment</code> from tape heat; Fear &amp; Greed is the only external bolt-on.</p>
                  <p><strong>Refresh:</strong> Last update {lastUpdate}; auto-refresh every {Math.round(REFRESH_MS / 1000)}s.</p>
                  <p className="disclaimer">If I were giving financial advice, I would say to treat this as context only, size small, and verify the linked sources before moving any capital.</p>
                </div>
              </div>
            </section>
          )}

          {/* SOURCES TAB */}
          {!loading && activeTab === 'sources' && (
            <section className="tab-panel active" role="tabpanel">
              <div className="info-section">
                <div className="section-header">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <circle cx="12" cy="12" r="10"/>
                      <path d="M2 12h20"/>
                    </svg>
                    Data Sources
                  </h3>
                  <p className="section-desc">Local tape engine + external Fear &amp; Greed.</p>
                </div>
                <div className="sources-list">
                  <div className="source-card tier-1">
                    <div className="source-info">
                      <div className="source-header">
                        <span className="source-icon" aria-hidden="true">CB</span>
                        <div>
                          <div className="source-name">Coinbase Tape Data</div>
                          <span className="source-status">Live</span>
                        </div>
                      </div>
                      <div className="source-desc">Local price history (1m/3m) computed on-box.</div>
                      <div className="source-meta">
                        <span>Scope: Market-wide</span>
                        <span>Status: {status}</span>
                      </div>
                    </div>
                    <div className="source-metrics">
                      <span className="tier-badge tier-1">TAPE</span>
                      <span className="source-score">Score {getSourceScoreLabel(score != null ? score / 100 : null)}</span>
                    </div>
                  </div>
                  <div className="source-card tier-2">
                    <div className="source-info">
                      <div className="source-header">
                        <span className="source-icon" aria-hidden="true">FG</span>
                        <div>
                          <div className="source-name">Fear &amp; Greed Index</div>
                          <span className="source-status">{fgStatus}</span>
                        </div>
                      </div>
                      <div className="source-desc">Alternative.me index (cached, 5m TTL).</div>
                      <div className="source-meta">
                        <span>Value: {Number.isFinite(fg) ? fg : "N/A"}</span>
                        <span>Updated: {fgUpdatedLabel || "—"}</span>
                      </div>
                    </div>
                    <div className="source-metrics">
                      <span className="tier-badge tier-2">FGI</span>
                      <span className="source-score">Score {getSourceScoreLabel(Number.isFinite(fg) ? fg / 100 : null)}</span>
                    </div>
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* CHARTS TAB */}
          {!loading && activeTab === 'charts' && (
            <section className="tab-panel active" role="tabpanel">
              {/* TradingView Chart */}
              <div className="info-section">
                <div className="section-header">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
                      <path d="M9 22V12h6v10"/>
                    </svg>
                    Live Price Chart - {symbol}
                  </h3>
                  <p className="section-desc">TradingView real-time data (source selectable)</p>
                  <div className="mini-toggle">
                    {['auto', 'coinbase', 'binance'].map((opt) => (
                      <button
                        key={opt}
                        className={`mini-toggle-btn ${chartExchange === opt ? 'active' : ''}`}
                        onClick={() => setChartExchange(opt)}
                      >
                        {opt === 'auto' ? 'Auto' : opt === 'coinbase' ? 'Coinbase' : 'Binance'}
                      </button>
                    ))}
                    <span className="mini-toggle-label">Source: {tvResolved.source}</span>
                  </div>
                </div>
                <div className="tradingview-widget-container" style={{height: '420px', marginBottom: '1rem'}}>
                  <div style={{height: '100%', width: '100%'}}>
                    <iframe
                      key={`${tvResolved.symbol}-${tvResolved.source}`}
                      src={tvUrl}
                      style={{width: '100%', height: '100%', border: 'none', borderRadius: '8px'}}
                      title={`${symbol} Price Chart`}
                    />
                  </div>
                </div>
              </div>

              <div className="info-section">
                <div className="section-header">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M3 3v18h18"/>
                      <path d="M7 16l4-4 4 4 6-6"/>
                    </svg>
                    Sentiment Trend (history)
                  </h3>
                  <p className="section-desc">Track how market sentiment has evolved</p>
                </div>
                <div className="chart-container">
                  {sentimentHistory.length ? (
                    <canvas ref={trendChartRef} role="img" aria-label="Sentiment trend chart"></canvas>
                  ) : (
                    <div className="sentiment-muted">No history returned by pipeline.</div>
                  )}
                </div>
              </div>
            </section>
          )}

          {/* INSIGHTS TAB */}
          {!loading && activeTab === 'insights' && (
            <section className="tab-panel active" role="tabpanel">
              {/* Divergence Alerts */}
              {safeAlerts.length > 0 && (
                <div className="info-section">
                  <div className="section-header">
                    <h3>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                        <path d="M12 9v4M12 17h.01"/>
                      </svg>
                      Divergence Alerts
                    </h3>
                    <p className="section-desc">1m vs 3m tape disagreements</p>
                  </div>
                  <div className="divergence-alerts">
                    {safeAlerts.map((alert, idx) => (
                      <div key={idx} className={`alert-box ${alert.type}`}>
                        <span className="alert-icon">
                          {alert.type === 'warning' ? 'WARN' : alert.type === 'success' ? 'OK' : 'INFO'}
                        </span>
                        <div className="alert-content">
                          <p>{alert.message}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* AI Insight */}
              <div className="info-section">
                <div className="section-header">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <circle cx="12" cy="12" r="4"/>
                      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83"/>
                    </svg>
                    AI Market Analysis
                  </h3>
                  <p className="section-desc">Generated from tape heat + F&amp;G</p>
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
            <span className="data-source">Powered by tape + Fear &amp; Greed (<span>{sourceCount}</span> sources)</span>
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
