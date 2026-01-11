import React, { useState, useMemo, useRef, useEffect } from 'react';
import { TrendingUp, Activity, AlertTriangle } from 'lucide-react';
import { useTieredSentiment } from '../hooks/useTieredSentiment';
import { Chart as ChartJS, registerables } from 'chart.js';
import '../styles/sentiment-popup-advanced.css';
import { SkeletonBlock, SkeletonCard, SkeletonText } from './ui/Skeleton';

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
  const { data: sentimentData, loading, error, refresh, pipelineHealth, tieredData, sources: pipelineSources } = useTieredSentiment(symbol, { enabled: isOpen, refreshMs: REFRESH_MS });
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
  const pieChartRef = useRef(null);
  const tierChartRef = useRef(null);
  const correlationChartRef = useRef(null);
  const socialChartRef = useRef(null);

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
  const socialHistory = Array.isArray(sentimentData?.socialHistory)
    ? sentimentData.socialHistory
    : [];
  const socialBreakdown = sentimentData?.socialBreakdown || {};
  const sourceBreakdown = sentimentData?.sourceBreakdown || {};
  const divergenceAlerts = Array.isArray(sentimentData?.divergenceAlerts)
    ? sentimentData.divergenceAlerts
    : [];
  const trendingTopics = Array.isArray(sentimentData?.trendingTopics)
    ? sentimentData.trendingTopics
    : [];
  const tierScores = sentimentData?.tierScores || {};
  const fearGreedIndex = Number.isFinite(sentimentData?.fearGreedIndex)
    ? sentimentData.fearGreedIndex
    : 50;
  const hasTieredData = Boolean(sentimentData?.hasTieredData);

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

  const safeTopics = useMemo(() => {
    return trendingTopics
      .map((t) => {
        const sentiment = (t?.sentiment || 'neutral')?.toString().toLowerCase();
        const tag = t?.tag || t?.topic || 'Topic';
        const volume = t?.volume ?? t?.count ?? '';
        return { sentiment, tag, volume };
      })
      .filter(Boolean);
  }, [trendingTopics]);

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
      if (activeTab !== 'charts') {
        Object.values(chartInstancesRef.current).forEach(chart => {
          if (chart) chart.destroy();
        });
        chartInstancesRef.current = {};
      }
    };
  }, [activeTab, sentimentData, isOpen, sentimentHistory, socialHistory]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refresh({ freshLatest: true });
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
      initSocialHistoryChart();
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

  const initPieChart = () => {
    const canvas = pieChartRef.current;
    if (!canvas) return;

    const breakdown = sourceBreakdown || { tier1: 0, tier2: 0, tier3: 0, fringe: 0 };

    const labels = ['Tier 1', 'Tier 2', 'Tier 3', 'Fringe'];
    const datasets = [{
      data: [breakdown.tier1 || 0, breakdown.tier2 || 0, breakdown.tier3 || 0, breakdown.fringe || 0],
      backgroundColor: ['#45ffb3', '#f1b43a', '#ae4bf5', '#6a7cff'],
      borderColor: '#141414',
      borderWidth: 2
    }];

    const chart = ensureChart('pie', canvas, () => new ChartJS(canvas, {
      type: 'doughnut',
      data: { labels, datasets },
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
    }));

    updateChart(chart, { labels, datasets });
  };

  const initTierChart = () => {
    const canvas = tierChartRef.current;
    if (!canvas) return;

    const redditTwitter = [socialBreakdown.reddit, socialBreakdown.twitter].filter(v => typeof v === 'number');
    const tgChan = [socialBreakdown.telegram, socialBreakdown.chan].filter(v => typeof v === 'number');

    const avg = (arr) => arr.length ? arr.reduce((a,b)=>a+b,0)/arr.length : 0;

    const buckets = [
      { label: 'Macro (F&G)', value: fearGreedIndex },
      { label: 'Reddit/Twitter', value: avg(redditTwitter) * 100 },
      { label: 'Telegram/Chan', value: avg(tgChan) * 100 },
    ];

    const labels = buckets.map(b => b.label);
    const datasets = [{
      label: 'Avg. Sentiment',
      data: buckets.map(b => b.value || 0),
      backgroundColor: ['rgba(69, 255, 179, 0.6)', 'rgba(241, 180, 58, 0.6)', 'rgba(174, 75, 245, 0.6)'],
      borderColor: ['#45ffb3', '#f1b43a', '#ae4bf5'],
      borderWidth: 1,
      borderRadius: 4
    }];

    const chart = ensureChart('tier', canvas, () => new ChartJS(canvas, {
      type: 'bar',
      data: { labels, datasets },
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
    }));

    updateChart(chart, { labels, datasets });
  };

  const initCorrelationChart = () => {
    const canvas = correlationChartRef.current;
    if (!canvas) return;

    const history = sentimentHistory;

    if (!history.length) {
      if (chartInstancesRef.current.correlation) {
        destroyChart('correlation');
      }
      return;
    }

    const labels = history.map(h => {
      const date = new Date(h.timestamp);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    });

    const sentimentScores = history.map(h => (typeof h.sentiment === 'number' ? h.sentiment * 100 : null));
    const priceData = history.map(h => {
      if (typeof h.price === 'number') return h.price;
      if (typeof h.priceNormalized === 'number') return h.priceNormalized;
      return null;
    });

    const datasets = [
      {
        label: 'Price (normalized)',
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
    ];

    const chart = ensureChart('correlation', canvas, () => new ChartJS(canvas, {
      type: 'line',
      data: { labels, datasets },
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
              callback: v => v
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
    }));

    updateChart(chart, { labels, datasets });
  };

  const initSocialHistoryChart = () => {
    const canvas = socialChartRef.current;
    if (!canvas) return;

    if (chartInstancesRef.current.social) {
      // keep instance; will update below
    }

    if (!socialHistory.length) {
      if (chartInstancesRef.current.social) {
        destroyChart('social');
      }
      return;
    }

    const labels = socialHistory.map((h) => {
      const date = new Date(h.timestamp);
      return Number.isNaN(date.getTime())
        ? String(h.timestamp || '')
        : date.toLocaleString([], { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' });
    });

    const series = (label, key, color) => ({
      label,
      data: socialHistory.map((h) => (typeof h[key] === 'number' ? h[key] * 100 : null)),
      tension: 0.35,
      pointRadius: 0,
      pointHoverRadius: 3,
      borderColor: color,
      backgroundColor: 'transparent',
      spanGaps: true,
    });

    const datasets = [
      series('Reddit', 'reddit', '#f1b43a'),
      series('Twitter', 'twitter', '#ae4bf5'),
      series('Telegram', 'telegram', '#45ffb3'),
      series('Chan', 'chan', '#6a7cff'),
    ];

    const chart = ensureChart('social', canvas, () => new ChartJS(canvas, {
      type: 'line',
      data: { labels, datasets },
      options: getChartOptions('Social sentiment (0-100)'),
    }));

    updateChart(chart, { labels, datasets });
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

  const score = sentimentData ? Math.round((sentimentData.overallSentiment ?? 0.5) * 100) : 0;
  const fg = Number.isFinite(sentimentData?.fearGreedIndex) ? sentimentData.fearGreedIndex : 50;
  const insight = generateTopInsight(score, fg);
  const gaugePos = updateGaugePosition(score);

  const tvResolved = resolveTvSymbol(symbol, chartExchange);
  const tvUrl = buildTradingViewEmbedUrl(tvResolved.symbol);

  const fallbackSourceCount = sourceBreakdown
    ? Object.values(sourceBreakdown).filter(v => typeof v === 'number').reduce((a, b) => a + b, 0)
    : 0;
  const sourceCount = pipelineSources?.length || fallbackSourceCount;

  const lastUpdatedMsRaw =
    sentimentData?.pipelineTimestamp ??
    sentimentData?.timestamp ??
    sentimentData?.updatedAt ??
    null;
  const lastUpdatedMs = Number.isFinite(Date.parse(lastUpdatedMsRaw || "")) ? Date.parse(lastUpdatedMsRaw) : Date.now();
  const lastUpdate = Number.isFinite(lastUpdatedMs)
    ? new Date(lastUpdatedMs).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '--:--';

  useEffect(() => {
    if (!import.meta.env.DEV || !isOpen || !sentimentData) return;
    if (window.__MW_SENTIMENT_LOGGED__) return;
    window.__MW_SENTIMENT_LOGGED__ = true;
    console.debug("[sentiment] sample payload", {
      pipelineTimestamp: sentimentData.pipelineTimestamp,
      overallSentiment: sentimentData.overallSentiment,
      fearGreedIndex: sentimentData.fearGreedIndex,
      tierScores: sentimentData.tierScores,
      sourceBreakdown,
      firstSource: sortedSources?.[0] || null,
    });
  }, [isOpen, sentimentData, sourceBreakdown, sortedSources]);

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

        {/* Dev debug strip (visible only in dev to verify data presence) */}
        {import.meta.env.DEV && (
          <div className="dev-strip">
            normalized: {String(Boolean(sentimentData?.normalized))} ·
            hist: {sentimentHistory.length} ·
            social: {socialHistory.length} ·
            sources: {Object.values(sourceBreakdown).filter(v => typeof v === 'number').reduce((a, b) => a + b, 0)} ·
            timestamp: {sentimentData?.pipelineTimestamp || 'n/a'}
            {(!sentimentHistory.length || !socialHistory.length) && ' · No history returned by pipeline yet'}
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
                Fetching from {sourceCount ? `${sourceCount} sources` : 'pipeline sources'}
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
                      T1: {sourceBreakdown?.tier1 || 0} |
                      T2: {sourceBreakdown?.tier2 || 0} |
                      T3: {sourceBreakdown?.tier3 || 0}
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

              {/* Tiered Sentiment Breakdown */}
              {hasTieredData && tierScores && (
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
                        {((tierScores.tier1 ?? 0.5) * 100).toFixed(0)}%
                      </div>
                      <div className="tier-bar">
                        <div
                          className="tier-bar-fill tier-1-fill"
                          style={{ width: `${(tierScores.tier1 ?? 0.5) * 100}%` }}
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
                        {((tierScores.tier2 ?? 0.5) * 100).toFixed(0)}%
                      </div>
                      <div className="tier-bar">
                        <div
                          className="tier-bar-fill tier-2-fill"
                          style={{ width: `${(tierScores.tier2 ?? 0.5) * 100}%` }}
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
                        {((tierScores.tier3 ?? 0.5) * 100).toFixed(0)}%
                      </div>
                      <div className="tier-bar">
                        <div
                          className="tier-bar-fill tier-3-fill"
                          style={{ width: `${(tierScores.tier3 ?? 0.5) * 100}%` }}
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
                        {((tierScores.fringe ?? 0.5) * 100).toFixed(0)}%
                      </div>
                      <div className="tier-bar">
                        <div
                          className="tier-bar-fill tier-fringe-fill"
                          style={{ width: `${(tierScores.fringe ?? 0.5) * 100}%` }}
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
                  <p><strong>Tiers:</strong> T1 (whales/institutions), T2 (pro desks/media), T3 (retail/social), FX (fringe). Tier scores map directly to <code>tierScores</code> from the API.</p>
                  <p><strong>Charts:</strong> The gauge and trend line use <code>overallSentiment</code>; Fear &amp; Greed comes from <code>fearGreedIndex</code>. Flat, tight bands = confirmation; wide swings vs price = noise/volatility.</p>
                  <p><strong>Refresh:</strong> Pipeline timestamp {lastUpdate}; auto-refresh every {Math.round(REFRESH_MS / 1000)}s.</p>
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
                    const sourceUrl = source.url || source.href || source.link;

                    return (
                      <div key={source.name} className={`source-card ${tierClass}`}>
                        <div className="source-info">
                          <div className="source-header">
                            <span className="source-icon" aria-hidden="true">{TIER_ICONS[tierKey] || 'SRC'}</span>
                            <div>
                              {sourceUrl ? (
                                <a
                                  className="source-name"
                                  href={sourceUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                  style={{ color: 'inherit' }}
                                >
                                  {source.name}
                                </a>
                              ) : (
                                <div className="source-name">{source.name}</div>
                              )}
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
                        : 'Pipeline did not return source inventory. Enable /api/sentiment/sources to view live sources.'}
                    </p>
                  </div>
                )}
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
                  <p className="section-desc">How sentiment aligns with price movement</p>
                </div>
                <div className="chart-container">
                  {sentimentHistory.length ? (
                    <canvas ref={correlationChartRef} role="img" aria-label="Correlation chart"></canvas>
                  ) : (
                    <div className="sentiment-muted">No history returned by pipeline.</div>
                  )}
                </div>
              </div>

              <div className="info-section">
                <div className="section-header">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M3 12h18"/>
                      <path d="M3 6h12"/>
                      <path d="M3 18h8"/>
                    </svg>
                    Momentum snapshot
                  </h3>
                  <p className="section-desc">24h change across sentiment and socials (first vs last point)</p>
                </div>
                <div className="momentum-grid">
                  {(() => {
                    const delta = (arr, key) => {
                      if (!Array.isArray(arr) || arr.length < 2) return null;
                      const first = arr[0]?.[key];
                      const last = arr[arr.length - 1]?.[key];
                      if (typeof first !== 'number' || typeof last !== 'number') return null;
                      return ((last - first) * 100).toFixed(1);
                    };
                    const sentimentDelta = delta(sentimentHistory, 'sentiment');
                    const redditDelta = delta(socialHistory, 'reddit');
                    const twitterDelta = delta(socialHistory, 'twitter');
                    const telegramDelta = delta(socialHistory, 'telegram');
                    const chanDelta = delta(socialHistory, 'chan');
                    const card = (label, val) => (
                      <div className="momentum-card" key={label}>
                        <span className="momentum-label">{label}</span>
                        <span className={`momentum-value ${val === null ? 'muted' : val >= 0 ? 'pos' : 'neg'}`}>
                          {val === null ? '—' : `${val > 0 ? '+' : ''}${val}`}
                        </span>
                      </div>
                    );
                    return (
                      <div className="momentum-cards">
                        {card('Sentiment', sentimentDelta)}
                        {card('Reddit', redditDelta)}
                        {card('Twitter', twitterDelta)}
                        {card('Telegram', telegramDelta)}
                        {card('Chan', chanDelta)}
                      </div>
                    );
                  })()}
                </div>
              </div>

              <div className="info-section">
                <div className="section-header">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M3 3v18h18"/>
                    </svg>
                    Social Trend
                  </h3>
                  <p className="section-desc">Reddit, Twitter, Telegram, Chan trend (normalized)</p>
                </div>
                <div className="chart-container">
                  {socialHistory.length ? (
                    <canvas ref={socialChartRef} role="img" aria-label="Social trend chart"></canvas>
                  ) : (
                    <div className="sentiment-muted">No social history returned by pipeline.</div>
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
                    <p className="section-desc">Conflicts between different market tiers</p>
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

              {/* Trending Topics */}
              {safeTopics.length > 0 && (
                <div className="info-section">
                  <div className="section-header">
                    <h3>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                      </svg>
                      Trending Topics
                    </h3>
                    <p className="section-desc">What people are talking about</p>
                  </div>
                  <div className="trending-topics">
                    {safeTopics.slice(0, 5).map((topic, idx) => (
                      <div key={idx} className={`topic-card ${topic.sentiment}`}>
                        <div className="topic-tag">{topic.tag}</div>
                        <div className="topic-meta">
                          <span className={`sentiment-badge ${topic.sentiment}`}>
                            {topic.sentiment ? topic.sentiment.toUpperCase() : 'NEUTRAL'}
                          </span>
                          <span className="volume-badge">{topic.volume}</span>
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
                  <p className="section-desc">Generated from multi-source intelligence</p>
                </div>

                <div className="insights-list">
                  <div className={`insight-box ${insight.type}`}>
                    <span className="insight-icon">{insight.icon}</span>
                    <div className="insight-content">
                      <strong>{insight.title}</strong>
                      <p>{insight.message}</p>
                    </div>
                  </div>

                  {/* Social Sentiment Summary */}
                  {socialBreakdown && (
                    <div className="insight-box info">
                      <span className="insight-icon">SOC</span>
                      <div className="insight-content">
                        <strong>Social Sentiment Breakdown</strong>
                        <p>
                          Reddit: {Math.round((socialBreakdown.reddit || 0) * 100)}% •
                          Twitter: {Math.round((socialBreakdown.twitter || 0) * 100)}% •
                          Telegram: {Math.round((socialBreakdown.telegram || 0) * 100)}%
                          {socialBreakdown.chan && ` • CHAN: ${Math.round(socialBreakdown.chan * 100)}%`}
                        </p>
                      </div>
                    </div>
                  )}
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
