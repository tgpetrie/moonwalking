import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { TrendingUp, Activity, AlertTriangle } from 'lucide-react';
import { useMarketHeat } from '../hooks/useMarketHeat';
import { Chart as ChartJS, registerables } from 'chart.js';
import '../styles/sentiment-popup-advanced.css';
import { SkeletonBlock, SkeletonCard, SkeletonText } from './ui/Skeleton';
import AlertsTab from './AlertsTab';
import { API_ENDPOINTS, fetchData } from '../api';

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

const normalizeHistorySymbol = (value) => {
  const raw = String(value || '').trim().toUpperCase();
  if (!raw) return null;
  const base = raw.includes('-')
    ? raw.split('-', 1)[0]
    : raw.endsWith('USD')
      ? raw.slice(0, -3)
      : raw;
  const clean = base.replace(/[^A-Z0-9]/g, '');
  return clean ? `${clean}-USD` : null;
};

const toFiniteNumber = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const formatPercentDelta = (value) => {
  const n = toFiniteNumber(value);
  if (n === null) return '—';
  const abs = Math.abs(n);
  const digits = abs >= 10 ? 1 : abs >= 1 ? 2 : 3;
  return `${n >= 0 ? '+' : ''}${n.toFixed(digits)}%`;
};

const toneClassForNumber = (value) => {
  const n = toFiniteNumber(value);
  if (n === null) return 'neutral';
  if (n > 0) return 'positive';
  if (n < 0) return 'negative';
  return 'neutral';
};

const formatCompact = (value) => {
  const n = toFiniteNumber(value);
  if (n === null) return '—';
  return new Intl.NumberFormat(undefined, {
    notation: 'compact',
    maximumFractionDigits: 2,
  }).format(n);
};

const normalizeTimestampMs = (value) => {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value < 1e12 ? value * 1000 : value;
  }
  const numeric = Number(value);
  if (Number.isFinite(numeric)) {
    return numeric < 1e12 ? numeric * 1000 : numeric;
  }
  const parsed = Date.parse(String(value));
  return Number.isFinite(parsed) ? parsed : null;
};

const toRatio01 = (value) => {
  const n = toFiniteNumber(value);
  if (n === null) return null;
  if (n > 1 && n <= 100) return n / 100;
  return Math.max(0, Math.min(1, n));
};

const formatRatioPercent = (value, digits = 0) => {
  const n = toRatio01(value);
  if (n === null) return '—';
  return `${(n * 100).toFixed(digits)}%`;
};

const formatSignedNumber = (value, digits = 2) => {
  const n = toFiniteNumber(value);
  if (n === null) return '—';
  return `${n > 0 ? '+' : ''}${n.toFixed(digits)}`;
};

const toToneClass = (value) => {
  const n = toFiniteNumber(value);
  if (n === null) return 'neu';
  if (n > 0) return 'pos';
  if (n < 0) return 'neg';
  return 'neu';
};

const normalizeReasonTone = (value) => {
  const tone = String(value || '').trim().toLowerCase();
  if (!tone) return 'neutral';
  if (tone.includes('bull') || tone.includes('pos') || tone.includes('up')) return 'bullish';
  if (tone.includes('bear') || tone.includes('neg') || tone.includes('down')) return 'bearish';
  return 'neutral';
};

const extractTapePulse = (payload) => {
  if (!payload || typeof payload !== 'object') return null;
  const body = payload.data && typeof payload.data === 'object' ? payload.data : payload;
  const metrics = body.metrics && typeof body.metrics === 'object' ? body.metrics : body;
  const change1m = toFiniteNumber(
    metrics.change_1m ?? metrics.change1m ?? body.change_1m ?? body.change1m,
  );
  const change3m = toFiniteNumber(
    metrics.change_3m ?? metrics.change3m ?? body.change_3m ?? body.change3m,
  );
  const volDelta1h = toFiniteNumber(
    metrics.volume_change_1h ?? metrics.volumeChange1h ?? body.volume_change_1h ?? body.volumeChange1h,
  );
  const hasAny = [change1m, change3m, volDelta1h].some((v) => v !== null);
  if (!hasAny) return null;
  return { change1m, change3m, volDelta1h };
};

const SentimentPopupAdvanced = ({ isOpen, onClose, symbol, defaultTab = 'overview' }) => {
  const REFRESH_MS = 15000;
  const COIN_HISTORY_REFRESH_MS = 30000;
  const TAPE_REFRESH_MS = 30000;
  const [activeTab, setActiveTab] = useState(defaultTab || 'overview');
  const [chartExchange, setChartExchange] = useState('auto'); // auto | coinbase | binance
  const {
    data: sentimentData,
    loading,
    error,
    refresh,
    pipelineHealth,
    pipelineStatus: marketPipelineStatus,
    heat: marketHeat,
    regime: marketRegime,
    heatLabel: marketHeatLabel,
    confidence: marketConfidence,
    components: marketComponents,
    reasons: marketReasonsRaw,
    fearGreed: marketFearGreed,
    sentimentHistory: marketHistoryRaw,
    sources: marketSources,
  } = useMarketHeat();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [coinHistory, setCoinHistory] = useState(null);
  const [coinHistoryLoading, setCoinHistoryLoading] = useState(false);
  const [coinHistoryError, setCoinHistoryError] = useState(null);
  const [coinHistoryCb, setCoinHistoryCb] = useState(null);
  const [coinHistoryCbLoading, setCoinHistoryCbLoading] = useState(false);
  const [coinHistoryCbError, setCoinHistoryCbError] = useState(null);
  const [tapePulse, setTapePulse] = useState(null);
  const [tapePulseLoading, setTapePulseLoading] = useState(false);
  const [tapePulseError, setTapePulseError] = useState(null);
  const historySymbol = useMemo(() => normalizeHistorySymbol(symbol), [symbol]);

  // Sync tab when popup opens or defaultTab changes
  useEffect(() => {
    if (isOpen) setActiveTab(defaultTab || 'overview');
  }, [isOpen, defaultTab]);

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
  const correlationChartRef = useRef(null);
  const coinHistoryInFlightRef = useRef(false);
  const coinHistoryQueuedRef = useRef(false);
  const coinHistoryQueuedSilentRef = useRef(true);
  const coinHistoryCbInFlightRef = useRef(false);
  const coinHistoryCbQueuedRef = useRef(false);
  const coinHistoryCbQueuedSilentRef = useRef(true);
  const tapePulseInFlightRef = useRef(false);
  const tapePulseQueuedRef = useRef(false);
  const tapePulseQueuedSilentRef = useRef(true);
  const historySymbolRef = useRef(historySymbol);
  const isOpenRef = useRef(isOpen);

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

  useEffect(() => {
    historySymbolRef.current = historySymbol;
  }, [historySymbol]);

  useEffect(() => {
    isOpenRef.current = isOpen;
  }, [isOpen]);

  const loadCoinHistory = useCallback(async ({ silent = false } = {}) => {
    const requestedSymbol = historySymbolRef.current;
    if (!isOpenRef.current || !requestedSymbol) {
      coinHistoryInFlightRef.current = false;
      coinHistoryQueuedRef.current = false;
      coinHistoryQueuedSilentRef.current = true;
      setCoinHistoryLoading(false);
      if (isOpenRef.current && !requestedSymbol) {
        setCoinHistory(null);
        setCoinHistoryError(null);
      }
      return null;
    }
    if (coinHistoryInFlightRef.current) {
      coinHistoryQueuedRef.current = true;
      coinHistoryQueuedSilentRef.current = coinHistoryQueuedSilentRef.current && silent;
      return null;
    }
    coinHistoryInFlightRef.current = true;

    if (!silent) setCoinHistoryLoading(true);
    try {
      const payload = await fetchData(API_ENDPOINTS.coinHistory(requestedSymbol));
      if (historySymbolRef.current === requestedSymbol) {
        setCoinHistory(payload || null);
        setCoinHistoryError(null);
      }
      return payload || null;
    } catch (err) {
      if (historySymbolRef.current === requestedSymbol) {
        setCoinHistoryError(String(err?.message || err || 'Failed to load coin history'));
      }
      return null;
    } finally {
      coinHistoryInFlightRef.current = false;
      if (!silent) setCoinHistoryLoading(false);

      if (coinHistoryQueuedRef.current) {
        const queuedSilent = coinHistoryQueuedSilentRef.current;
        coinHistoryQueuedRef.current = false;
        coinHistoryQueuedSilentRef.current = true;
        if (isOpenRef.current && historySymbolRef.current) {
          setTimeout(() => {
            loadCoinHistory({ silent: queuedSilent });
          }, 0);
        }
      }
    }
  }, []);

  const loadCoinHistoryCb = useCallback(async ({ silent = false } = {}) => {
    const requestedSymbol = historySymbolRef.current;
    if (!isOpenRef.current || !requestedSymbol) {
      coinHistoryCbInFlightRef.current = false;
      coinHistoryCbQueuedRef.current = false;
      coinHistoryCbQueuedSilentRef.current = true;
      setCoinHistoryCbLoading(false);
      if (isOpenRef.current && !requestedSymbol) {
        setCoinHistoryCb(null);
        setCoinHistoryCbError(null);
      }
      return null;
    }
    if (coinHistoryCbInFlightRef.current) {
      coinHistoryCbQueuedRef.current = true;
      coinHistoryCbQueuedSilentRef.current = coinHistoryCbQueuedSilentRef.current && silent;
      return null;
    }
    coinHistoryCbInFlightRef.current = true;

    if (!silent) setCoinHistoryCbLoading(true);
    try {
      const payload = await fetchData(API_ENDPOINTS.coinHistoryCb(requestedSymbol));
      if (historySymbolRef.current === requestedSymbol) {
        setCoinHistoryCb(payload || null);
        setCoinHistoryCbError(null);
      }
      return payload || null;
    } catch (err) {
      if (historySymbolRef.current === requestedSymbol) {
        setCoinHistoryCbError(String(err?.message || err || 'Failed to load Coinbase backfill'));
      }
      return null;
    } finally {
      coinHistoryCbInFlightRef.current = false;
      if (!silent) setCoinHistoryCbLoading(false);

      if (coinHistoryCbQueuedRef.current) {
        const queuedSilent = coinHistoryCbQueuedSilentRef.current;
        coinHistoryCbQueuedRef.current = false;
        coinHistoryCbQueuedSilentRef.current = true;
        if (isOpenRef.current && historySymbolRef.current) {
          setTimeout(() => {
            loadCoinHistoryCb({ silent: queuedSilent });
          }, 0);
        }
      }
    }
  }, []);

  const loadTapePulse = useCallback(async ({ silent = false } = {}) => {
    const requestedSymbol = historySymbolRef.current;
    if (!isOpenRef.current || !requestedSymbol) {
      tapePulseInFlightRef.current = false;
      tapePulseQueuedRef.current = false;
      tapePulseQueuedSilentRef.current = true;
      setTapePulseLoading(false);
      if (isOpenRef.current && !requestedSymbol) {
        setTapePulse(null);
        setTapePulseError(null);
      }
      return null;
    }

    if (tapePulseInFlightRef.current) {
      tapePulseQueuedRef.current = true;
      tapePulseQueuedSilentRef.current = tapePulseQueuedSilentRef.current && silent;
      return null;
    }

    tapePulseInFlightRef.current = true;
    if (!silent) setTapePulseLoading(true);

    try {
      let parsed = null;
      let finalPayload = null;
      try {
        const payload = await fetchData(API_ENDPOINTS.intelligenceReport(requestedSymbol));
        parsed = extractTapePulse(payload);
        finalPayload = payload;
      } catch (_) {
        // fallback below
      }

      if (!parsed) {
        const payload = await fetchData(API_ENDPOINTS.insights(requestedSymbol));
        parsed = extractTapePulse(payload);
        finalPayload = payload;
      }

      if (historySymbolRef.current === requestedSymbol) {
        setTapePulse(parsed);
        setTapePulseError(null);
      }
      return finalPayload;
    } catch (err) {
      if (historySymbolRef.current === requestedSymbol) {
        setTapePulseError(String(err?.message || err || 'Failed to load tape pulse'));
      }
      return null;
    } finally {
      tapePulseInFlightRef.current = false;
      if (!silent) setTapePulseLoading(false);

      if (tapePulseQueuedRef.current) {
        const queuedSilent = tapePulseQueuedSilentRef.current;
        tapePulseQueuedRef.current = false;
        tapePulseQueuedSilentRef.current = true;
        if (isOpenRef.current && historySymbolRef.current) {
          setTimeout(() => {
            loadTapePulse({ silent: queuedSilent });
          }, 0);
        }
      }
    }
  }, []);

  useEffect(() => {
    if (!isOpen || !historySymbol) {
      setCoinHistory(null);
      setCoinHistoryError(null);
      setCoinHistoryLoading(false);
      setCoinHistoryCb(null);
      setCoinHistoryCbError(null);
      setCoinHistoryCbLoading(false);
      coinHistoryCbInFlightRef.current = false;
      coinHistoryCbQueuedRef.current = false;
      coinHistoryCbQueuedSilentRef.current = true;
      return;
    }

    let disposed = false;
    const run = async (silent = false) => {
      if (disposed) return;
      await loadCoinHistory({ silent });
    };

    run(false);
    const intervalId = setInterval(() => {
      run(true);
    }, COIN_HISTORY_REFRESH_MS);

    return () => {
      disposed = true;
      clearInterval(intervalId);
    };
  }, [isOpen, historySymbol, loadCoinHistory]);

  useEffect(() => {
    if (!isOpen || !historySymbol) return;

    const localCoverage = toFiniteNumber(coinHistory?.historyCoverage?.minutesAvailable);
    const localDeltas = coinHistory?.deltas || {};
    const localD1h = toFiniteNumber(coinHistory?.d1h ?? localDeltas?.['1h']);
    const needsCbBackfill = localCoverage === null || localCoverage < 60 || localD1h === null;

    if (!needsCbBackfill) return;
    if (coinHistoryCbLoading || coinHistoryCbInFlightRef.current) return;
    if (coinHistoryCb && !coinHistoryCbError) return;

    loadCoinHistoryCb({ silent: false });
  }, [isOpen, historySymbol, coinHistory, coinHistoryCb, coinHistoryCbError, coinHistoryCbLoading, loadCoinHistoryCb]);

  useEffect(() => {
    if (!isOpen || !historySymbol) {
      setTapePulse(null);
      setTapePulseError(null);
      setTapePulseLoading(false);
      return;
    }

    let disposed = false;
    const run = async (silent = false) => {
      if (disposed) return;
      await loadTapePulse({ silent });
    };

    run(false);
    const intervalId = setInterval(() => {
      run(true);
    }, TAPE_REFRESH_MS);

    return () => {
      disposed = true;
      clearInterval(intervalId);
    };
  }, [isOpen, historySymbol, loadTapePulse]);

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
    if (!isOpen) return;

    let timeoutId = null;
    if (activeTab === 'charts' && sentimentData) {
      timeoutId = window.setTimeout(() => initCharts(), 100);
    }

    return () => {
      if (timeoutId) window.clearTimeout(timeoutId);

      if (activeTab !== 'charts' || !isOpen) {
        Object.values(chartInstancesRef.current).forEach(chart => {
          if (chart) chart.destroy();
        });
        chartInstancesRef.current = {};
      }
    };
  }, [activeTab, sentimentData, isOpen, sentimentHistory.length]);

  const handleRefresh = async () => {
    const localCoverage = toFiniteNumber(coinHistory?.historyCoverage?.minutesAvailable);
    const localDeltas = coinHistory?.deltas || {};
    const localD1h = toFiniteNumber(coinHistory?.d1h ?? localDeltas?.['1h']);
    const needsCbBackfill = Boolean(historySymbol) && (localCoverage === null || localCoverage < 60 || localD1h === null);

    setIsRefreshing(true);
    await Promise.all([
      refresh({ freshLatest: true }),
      historySymbol ? loadCoinHistory() : Promise.resolve(null),
      needsCbBackfill ? loadCoinHistoryCb() : Promise.resolve(null),
      historySymbol ? loadTapePulse() : Promise.resolve(null),
    ]);
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
      initCorrelationChart();
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

  useEffect(() => {
    if (!import.meta.env.DEV || !isOpen || !sentimentData) return;
    if (window.__MW_SENTIMENT_LOGGED__) return;
    window.__MW_SENTIMENT_LOGGED__ = true;
    console.debug("[sentiment] sample payload", {
      pipelineTimestamp: sentimentData.pipelineTimestamp,
      overallSentiment: sentimentData.overallSentiment,
      fearGreedIndex: sentimentData.fearGreedIndex,
      regime: sentimentData.regime,
      heatLabel: sentimentData.heatLabel,
      components: sentimentData.components,
    });
  }, [isOpen, sentimentData]);

  if (!isOpen) return null;

  // null when missing - don't forge 50
  const score = sentimentData?.overallSentiment != null
    ? Math.round(sentimentData.overallSentiment * 100)
    : null;
  const fg = Number.isFinite(sentimentData?.fearGreedIndex) ? Number(sentimentData.fearGreedIndex) : null;
  const hasFG = Number.isFinite(fg);
  const fgStatus = sentimentData?.fearGreedStatus || (hasFG ? "LIVE" : "UNAVAILABLE");
  const fgUpdatedLabel = formatTimestamp(sentimentData?.fearGreedUpdatedAt);
  const insight = generateTopInsight(score, hasFG ? fg : null);
  const gaugePos = updateGaugePosition(score);

  const tvResolved = resolveTvSymbol(symbol, chartExchange);
  const tvUrl = buildTradingViewEmbedUrl(tvResolved.symbol);

  const hasScore = score !== null;
  const regimeRaw = sentimentData?.regime ? sentimentData.regime.toString() : "";
  const regimeDisplay = regimeRaw ? regimeRaw.toUpperCase() : "";
  const confidenceValue = Number.isFinite(sentimentData?.confidence) ? Number(sentimentData.confidence) : null;
  const confidenceDisplay = confidenceValue != null && confidenceValue > 0 ? confidenceValue.toFixed(2) : "";
  const reasonLines = Array.isArray(sentimentData?.reasons)
    ? sentimentData.reasons.slice(0, 2)
    : [];
  const hasMetaLine = (regimeDisplay || confidenceDisplay) && (hasScore || hasFG || reasonLines.length > 0);
  const components = sentimentData?.components || {};
  const hasComponents = Number.isFinite(components.total_symbols)
    ? components.total_symbols > 0
    : [components.breadth_3m, components.breadth_1m, components.momentum_alignment, components.volatility]
        .some((v) => Number.isFinite(v));

  const lastUpdatedMsRaw =
    sentimentData?.pipelineTimestamp ??
    sentimentData?.timestamp ??
    sentimentData?.updatedAt ??
    null;
  const lastUpdatedMs = Number.isFinite(Date.parse(lastUpdatedMsRaw || "")) ? Date.parse(lastUpdatedMsRaw) : null;
  const lastUpdate = Number.isFinite(lastUpdatedMs)
    ? new Date(lastUpdatedMs).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '';
  const status =
    sentimentData?.pipelineStatus ??
    (pipelineHealth?.running ? "LIVE" : "OFFLINE");
  const statusLower = String(status).toLowerCase();
  const staleSeconds =
    sentimentData?.sentimentMeta?.staleSeconds ??
    sentimentData?.sentimentMeta?.stale_seconds ??
    null;
  const statusTitle =
    status === "STALE" && typeof staleSeconds === "number"
      ? `STALE — ${Math.round(staleSeconds)}s stale`
      : status === "OFFLINE"
        ? "OFFLINE — pipeline not reachable"
        : "LIVE";
  const showSentimentLoading = loading && activeTab !== "alerts";
  const showSentimentError = !loading && Boolean(error) && activeTab !== "alerts";
  const localDeltas = coinHistory?.deltas || {};
  const d1hLocal = toFiniteNumber(coinHistory?.d1h ?? localDeltas?.['1h']);
  const cbDeltas = coinHistoryCb?.deltas || {};
  const d1hCb = toFiniteNumber(coinHistoryCb?.d1h ?? cbDeltas?.['1h']);
  const d1h = d1hLocal ?? d1hCb;
  const vol1hNow = toFiniteNumber(coinHistory?.vol1hNow ?? coinHistory?.now?.vol1h);
  const vol1hDelta = toFiniteNumber(coinHistory?.vol1hDelta);
  const historyLastUpdated = coinHistory?.lastUpdated ?? null;
  const cbLastUpdated = coinHistoryCb?.lastUpdated ?? null;
  const windowsLastUpdated = historyLastUpdated ?? cbLastUpdated ?? null;
  const historyCoverage = coinHistory?.historyCoverage || {};
  const minutesAvailable = toFiniteNumber(historyCoverage?.minutesAvailable);
  const needsCbBackfill = minutesAvailable === null || minutesAvailable < 60 || d1hLocal === null;
  const coverageLabel = minutesAvailable !== null
    ? (minutesAvailable >= 60
      ? `${(minutesAvailable / 60).toFixed(minutesAvailable >= 600 ? 0 : 1)}h`
      : `${Math.round(minutesAvailable)}m`)
    : null;
  const window1hSource = d1hLocal !== null ? 'TAPE' : (d1hCb !== null ? 'CB' : null);
  const tapeChange1m = toFiniteNumber(tapePulse?.change1m);
  const tapeChange3m = toFiniteNumber(tapePulse?.change3m);
  const tapeVolDelta1h = toFiniteNumber(tapePulse?.volDelta1h);
  const tapeHas1m = minutesAvailable !== null && minutesAvailable >= 1 && tapeChange1m !== null;
  const tapeHas3m = minutesAvailable !== null && minutesAvailable >= 3 && tapeChange3m !== null;
  const tapeHasVol1h = minutesAvailable !== null && minutesAvailable >= 60 && tapeVolDelta1h !== null;
  const tapeBias = (() => {
    if (!tapeHas1m || !tapeHas3m) return { label: 'Warming', tone: 'neutral' };
    const a = tapeChange1m;
    const b = tapeChange3m;
    if (a === null || b === null) return { label: 'Warming', tone: 'neutral' };
    if (Math.abs(a) < 0.1 && Math.abs(b) < 0.1) return { label: 'Neutral', tone: 'neutral' };
    if (a > 0 && b > 0) return { label: 'Bull', tone: 'positive' };
    if (a < 0 && b < 0) return { label: 'Bear', tone: 'negative' };
    return { label: 'Mixed', tone: 'neutral' };
  })();
  const tapeConfidence = (() => {
    if (!tapeHas1m || !tapeHas3m) return { label: 'Warming', tone: 'neutral' };
    const a = tapeChange1m;
    const b = tapeChange3m;
    if (a === null || b === null) return { label: 'Warming', tone: 'neutral' };
    const agree = (a > 0 && b > 0) || (a < 0 && b < 0);
    if (agree && Math.abs(b) >= 0.6 && (tapeVolDelta1h === null || Math.abs(tapeVolDelta1h) >= 10)) {
      return { label: 'High', tone: 'positive' };
    }
    if (agree) return { label: 'Med', tone: 'neutral' };
    return { label: 'Low', tone: 'negative' };
  })();
  const tapeCoverageText = minutesAvailable === null
    ? 'Warming'
    : `Warming (${Math.round(minutesAvailable)}m of tape)`;
  const globalPipe = pipelineHealth ?? (marketPipelineStatus ? {
    running: marketPipelineStatus === 'LIVE',
    status: marketPipelineStatus,
  } : null);
  const marketStatus = marketPipelineStatus ?? status;
  const marketHeatScoreRaw = toFiniteNumber(marketHeat ?? score);
  const marketHeatScore = marketHeatScoreRaw === null
    ? null
    : (marketHeatScoreRaw <= 1 ? marketHeatScoreRaw * 100 : marketHeatScoreRaw);
  const marketRegimeDisplay = String(marketRegime ?? regimeRaw ?? '').toUpperCase() || '—';
  const marketHeatDisplay = marketHeatLabel || sentimentData?.heatLabel || 'NEUTRAL';
  const marketConfidence01 = toRatio01(marketConfidence ?? confidenceValue);
  const marketConfidenceDisplay = marketConfidence01 === null ? '—' : `${(marketConfidence01 * 100).toFixed(0)}%`;
  const marketComponentsRaw = marketComponents || sentimentData?.components || {};
  const marketBreadth = marketComponentsRaw?.breadth ?? marketComponentsRaw?.marketBreadth ?? marketComponentsRaw?.breadth_3m;
  const marketVolatility = marketComponentsRaw?.volatility ?? marketComponentsRaw?.volRegime;
  const marketMomentum = marketComponentsRaw?.momentum ?? marketComponentsRaw?.marketMomentum ?? marketComponentsRaw?.momentum_alignment;
  const marketImpulse = marketComponentsRaw?.impulse ?? marketComponentsRaw?.flow ?? marketComponentsRaw?.avg_return_1m;
  const fgObject = marketFearGreed || sentimentData?.raw?.fear_greed || {};
  const fgValueRaw = toFiniteNumber(fgObject?.value ?? fgObject?.score ?? fgObject?.index ?? fg);
  const fgValue = fgValueRaw === null ? null : Math.max(0, Math.min(100, fgValueRaw));
  const fgLabel = fgObject?.classification || fgObject?.label || sentimentData?.fearGreedLabel || getFearGreedLabel(fgValue);
  const fgUpdatedRaw = fgObject?.updatedAt ?? fgObject?.updated_at ?? fgObject?.timestamp ?? sentimentData?.fearGreedUpdatedAt ?? null;
  const fgUpdatedMs = normalizeTimestampMs(fgUpdatedRaw);
  const marketReasons = Array.isArray(marketReasonsRaw)
    ? marketReasonsRaw
    : (Array.isArray(sentimentData?.reasons) ? sentimentData.reasons : []);
  const marketReasonCards = marketReasons
    .slice(0, 6)
    .map((reason, index) => {
      if (typeof reason === 'string') {
        return {
          tone: 'neutral',
          title: `Signal ${index + 1}`,
          body: reason,
        };
      }
      const title = reason?.title ?? reason?.label ?? `Signal ${index + 1}`;
      const body = reason?.detail ?? reason?.text ?? reason?.message ?? '';
      if (!body) return null;
      const tone = normalizeReasonTone(reason?.tone ?? reason?.bias ?? reason?.direction ?? reason?.type);
      return { tone, title, body };
    })
    .filter(Boolean);
  const rawHistory = Array.isArray(marketHistoryRaw) && marketHistoryRaw.length ? marketHistoryRaw : sentimentHistory;
  const marketTimeline = rawHistory
    .slice(-8)
    .reverse()
    .map((entry, index) => {
      const ts = normalizeTimestampMs(entry?.ts ?? entry?.time ?? entry?.timestamp ?? entry?.updatedAt ?? null);
      const label = entry?.label ?? entry?.heatLabel ?? entry?.regime ?? marketHeatDisplay;
      const conf = toRatio01(entry?.confidence);
      return {
        id: `${ts ?? 'na'}-${index}`,
        ts,
        label: String(label || 'Market update').toUpperCase(),
        confidence: conf,
      };
    });
  const sourceChips = [
    { label: 'Alternative.me Fear & Greed', href: 'https://alternative.me/crypto/fear-and-greed-index/' },
    { label: 'Coinbase Exchange API', href: 'https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductticker' },
  ];
  if (Array.isArray(marketSources)) {
    marketSources.forEach((src) => {
      if (src && typeof src.url === 'string' && src.url.startsWith('http')) {
        sourceChips.push({
          label: src.name || src.label || 'Source',
          href: src.url,
        });
      }
    });
  }

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
              <p className="subtitle">Market heat from live tape data</p>
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
            symbols: {sentimentData?.components?.total_symbols ?? 0} ·
            regime: {sentimentData?.regime || 'n/a'} ·
            timestamp: {sentimentData?.pipelineTimestamp || 'n/a'}
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
            className={`tab-btn ${activeTab === 'market' ? 'active' : ''}`}
            onClick={() => setActiveTab('market')}
            role="tab"
            aria-selected={activeTab === 'market'}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="12" r="9"/>
              <path d="M4 12 h16M12 3v18"/>
            </svg>
            Market
          </button>
          <button
            className={`tab-btn ${activeTab === 'sources' ? 'active' : ''}`}
            onClick={() => setActiveTab('sources')}
            role="tab"
            aria-selected={activeTab === 'sources'}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M12 2a10 10 0 100 20 10 10 0 000-20z"/>
              <path d="M2 12 h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10"/>
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
          <button
            className={`tab-btn ${activeTab === 'alerts' ? 'active' : ''}`}
            onClick={() => setActiveTab('alerts')}
            role="tab"
            aria-selected={activeTab === 'alerts'}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2z"/>
              <path d="M18 16v-5a6 6 0 10-12 0v5l-2 2h16l-2-2z"/>
            </svg>
            Alerts
          </button>
        </nav>

        {/* Tab Content */}
        <main className="tab-content">
          {/* Loading State */}
          {showSentimentLoading && (
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
                Loading market heat data from Coinbase tape...
              </div>
            </div>
          )}

          {showSentimentError && (
            <div style={{ padding: '1rem', margin: '0 0 1rem 0', background: '#2b1a1a', color: '#ff9b9b', borderRadius: '8px' }}>
              Failed to load sentiment data: {String(error)}
            </div>
          )}

          {/* OVERVIEW TAB */}
          {!loading && activeTab === 'overview' && (
            <section className="tab-panel active" role="tabpanel">
              {!historySymbol && hasMetaLine && (
                <div className="sentiment-meta-line">
                  {regimeDisplay ? `REGIME: ${regimeDisplay}` : null}
                  {regimeDisplay && confidenceDisplay ? " | " : null}
                  {confidenceDisplay ? `CONFIDENCE: ${confidenceDisplay}` : null}
                </div>
              )}
              {!historySymbol && reasonLines.map((r, idx) => (
                <div key={`reason-${idx}`} className="sentiment-reason">{r}</div>
              ))}
              <div className="stats-grid">
                {historySymbol && (
                  <>
                    <div className="stat-card primary">
                      <div className="stat-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M4 19h16M7 15l3-3 3 2 4-5" />
                        </svg>
                      </div>
                      <div className="stat-content">
                        <span className="stat-label">Tape +1m</span>
                        <span className={`stat-value ${toneClassForNumber(tapeHas1m ? tapeChange1m : null)}`}>
                          {tapeHas1m ? formatPercentDelta(tapeChange1m) : '—'}
                        </span>
                        <span className="stat-sublabel">{tapeHas1m ? 'Live tape' : tapeCoverageText}</span>
                      </div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M4 19h16M7 13l4-2 3 1 6-5" />
                        </svg>
                      </div>
                      <div className="stat-content">
                        <span className="stat-label">Tape +3m</span>
                        <span className={`stat-value ${toneClassForNumber(tapeHas3m ? tapeChange3m : null)}`}>
                          {tapeHas3m ? formatPercentDelta(tapeChange3m) : '—'}
                        </span>
                        <span className="stat-sublabel">{tapeHas3m ? 'Live tape' : tapeCoverageText}</span>
                      </div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M12 2v20M5 9l7-7 7 7" />
                        </svg>
                      </div>
                      <div className="stat-content">
                        <span className="stat-label">VOL Δ1h</span>
                        <span className={`stat-value ${toneClassForNumber(tapeHasVol1h ? tapeVolDelta1h : null)}`}>
                          {tapeHasVol1h ? formatPercentDelta(tapeVolDelta1h) : '—'}
                        </span>
                        <span className="stat-sublabel">{tapeHasVol1h ? 'Volume proxy' : 'Needs 60m tape'}</span>
                      </div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M4 12 h16M12 4v16" />
                        </svg>
                      </div>
                      <div className="stat-content">
                        <span className="stat-label">Bias · Confidence</span>
                        <span className={`stat-value ${tapeBias.tone}`}>{tapeBias.label}</span>
                        <span className={`stat-sublabel ${tapeConfidence.tone}`}>Confidence: {tapeConfidence.label}</span>
                      </div>
                    </div>
                  </>
                )}
                {!historySymbol && hasScore && (
                  <div className="stat-card primary">
                    <div className="stat-icon">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/>
                      </svg>
                    </div>
                    <div className="stat-content">
                      <span className="stat-label">Market Sentiment (Global)</span>
                      <span className={`stat-value ${getSentimentClass(score)}`}>{score}</span>
                    </div>
                  </div>
                )}

                {!historySymbol && hasFG && (
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
                      <span className="stat-sublabel">
                        {getFearGreedLabel(fg)}
                        {" · "}
                        {fgStatus}
                        {fgUpdatedLabel ? ` · ${fgUpdatedLabel}` : ""}
                      </span>
                    </div>
                  </div>
                )}

                {!historySymbol && (hasScore || hasComponents) && (
                  <div className="stat-card">
                    <div className="stat-icon">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M13 2L3 14 h9l-1 8 10-12 h-9l1-8z"/>
                      </svg>
                    </div>
                    <div className="stat-content">
                      <span className="stat-label">Market Heat</span>
                      <span className={`stat-value ${hasScore && score >= 55 ? 'positive' : hasScore && score <= 35 ? 'negative' : 'neutral'}`}>
                        {sentimentData?.heatLabel || 'NEUTRAL'}
                      </span>
                      {!symbol && hasComponents && (
                        <span className="stat-sublabel">
                          Breadth {Number.isFinite(components.breadth_3m) ? `${components.breadth_3m.toFixed(0)}%` : '--'}
                          {' · '}Momentum {Number.isFinite(components.momentum_alignment) ? `${(components.momentum_alignment * 100).toFixed(0)}%` : '--'}
                          {' · '}Vol {Number.isFinite(components.volatility) ? `${components.volatility.toFixed(2)}%` : '--'}
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {(lastUpdate || historyLastUpdated) && (
                  <div className="stat-card">
                    <div className="stat-icon">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <circle cx="12" cy="12" r="10"/>
                        <path d="M12 6v6l4 2"/>
                      </svg>
                    </div>
                    <div className="stat-content">
                      <span className="stat-label">Last Updated</span>
                      <span className="stat-value small">
                        {historySymbol ? formatTimestamp(windowsLastUpdated || lastUpdatedMsRaw) : lastUpdate}
                      </span>
                      <span className="stat-sublabel">Auto-refresh: {Math.round(REFRESH_MS / 1000)}s</span>
                    </div>
                  </div>
                )}
              </div>
              {historySymbol && tapePulseError && (
                <div className="coin-history-note error">
                  Tape pulse unavailable: {tapePulseError}
                </div>
              )}
              {historySymbol && tapePulseLoading && !tapePulse && (
                <div className="coin-history-note">Loading tape pulse...</div>
              )}

              {historySymbol && (
                <div className="info-section coin-history-section">
                  <div className="section-header">
                    <h3>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M3 3v18h18" />
                        <path d="M7 16l4-4 4 4 6-6" />
                      </svg>
                      Coin Tape Windows
                    </h3>
                    <p className="section-desc">
                      Windows use local tape first, with Coinbase candle backfill while tape warms ({historySymbol})
                    </p>
                  </div>
                  {coinHistoryError && (
                    <div className="coin-history-note error">
                      Coin history unavailable: {coinHistoryError}
                    </div>
                  )}
                  {coinHistoryLoading && !coinHistory && (
                    <div className="coin-history-note">Loading local history...</div>
                  )}
                  {needsCbBackfill && coinHistoryCbError && (
                    <div className="coin-history-note error">
                      Coinbase backfill unavailable: {coinHistoryCbError}
                    </div>
                  )}
                  {needsCbBackfill && coinHistoryCbLoading && !coinHistoryCb && (
                    <div className="coin-history-note">Loading Coinbase backfill...</div>
                  )}
                  <div className="coin-history-grid">
                    <div className="coin-history-chip">
                      <span className="coin-history-label">Δ 1h {window1hSource ? `(${window1hSource})` : ''}</span>
                      <span className={`coin-history-value ${toneClassForNumber(d1h)}`}>
                        {formatPercentDelta(d1h)}
                      </span>
                    </div>
                    <div className="coin-history-chip">
                      <span className="coin-history-label">Vol Δ 1h</span>
                      <span className={`coin-history-value ${toneClassForNumber(minutesAvailable !== null && minutesAvailable >= 60 ? vol1hDelta : null)}`}>
                        {minutesAvailable !== null && minutesAvailable >= 60 ? formatCompact(vol1hNow) : '—'}
                        {minutesAvailable !== null && minutesAvailable >= 60 && vol1hDelta !== null ? ` (${vol1hDelta >= 0 ? '+' : ''}${formatCompact(vol1hDelta)})` : ''}
                      </span>
                    </div>
                  </div>
                  <div className="coin-history-footer">
                    <span className={`coin-bias-chip ${tapeBias.tone}`}>Bias: {tapeBias.label}</span>
                    <span className="coin-history-meta">
                      Last updated: {formatTimestamp(windowsLastUpdated)}
                      {coverageLabel ? ` · Tape warmup: ${coverageLabel}` : ''}
                      {' · '}Confidence: {tapeConfidence.label}
                    </span>
                  </div>
                  <div className="coin-history-footnote">
                    1h price uses tape when available, otherwise Coinbase candle backfill. 1h volume stays tape-only and needs 60m local coverage.
                  </div>
                </div>
              )}

              {!historySymbol && (
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
              )}

              {/* Market Heat Components - only show in market-wide view, not per-coin */}
              {hasComponents && !symbol && (
                <div className="info-section">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M3 3h7v7H3zM14 3h7v7h-7zM14 14 h7v7h-7zM3 14 h7v7H3z"/>
                    </svg>
                    Market Heat Breakdown
                  </h3>
                  <div className="tier-breakdown-grid">
                    <div className="tier-card tier-1">
                      <div className="tier-header">
                        <span className="tier-icon" aria-hidden="true">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <path d="M4 19h16M7 15l3-4 3 2 4-6"/>
                          </svg>
                        </span>
                        <span className="tier-label">Breadth (3m)</span>
                      </div>
                      <div className="tier-score">
                        {Number.isFinite(components.breadth_3m) ? `${components.breadth_3m.toFixed(0)}%` : '—'}
                      </div>
                      <div className="tier-bar">
                        <div
                          className="tier-bar-fill tier-1-fill"
                          style={{ width: Number.isFinite(components.breadth_3m) ? `${Math.min(100, components.breadth_3m)}%` : '0%' }}
                        />
                      </div>
                      <div className="tier-meta">
                        {components.green_3m ?? 0} green / {components.red_3m ?? 0} red of {components.total_symbols ?? 0}
                      </div>
                    </div>

                    <div className="tier-card tier-2">
                      <div className="tier-header">
                        <span className="tier-icon" aria-hidden="true">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <path d="M13 2L3 14 h7l-1 8 11-14 h-7l1-6z"/>
                          </svg>
                        </span>
                        <span className="tier-label">Breadth (1m)</span>
                      </div>
                      <div className="tier-score">
                        {Number.isFinite(components.breadth_1m) ? `${components.breadth_1m.toFixed(0)}%` : '—'}
                      </div>
                      <div className="tier-bar">
                        <div
                          className="tier-bar-fill tier-2-fill"
                          style={{ width: Number.isFinite(components.breadth_1m) ? `${Math.min(100, components.breadth_1m)}%` : '0%' }}
                        />
                      </div>
                      <div className="tier-meta">
                        {components.green_1m ?? 0} green / {components.red_1m ?? 0} red
                      </div>
                    </div>

                    <div className="tier-card tier-3">
                      <div className="tier-header">
                        <span className="tier-icon" aria-hidden="true">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <path d="M3 12a9 9 0 0115.5-6.36L21 8"/>
                            <path d="M21 12a9 9 0 01-15.5 6.36L3 16"/>
                          </svg>
                        </span>
                        <span className="tier-label">Momentum Alignment</span>
                      </div>
                      <div className="tier-score">
                        {Number.isFinite(components.momentum_alignment) ? `${(components.momentum_alignment * 100).toFixed(0)}%` : '—'}
                      </div>
                      <div className="tier-bar">
                        <div
                          className="tier-bar-fill tier-3-fill"
                          style={{ width: Number.isFinite(components.momentum_alignment) ? `${Math.max(0, Math.min(100, (components.momentum_alignment + 1) * 50))}%` : '0%' }}
                        />
                      </div>
                      <div className="tier-meta">
                        1m vs 3m agreement
                      </div>
                    </div>

                    <div className="tier-card tier-fringe">
                      <div className="tier-header">
                        <span className="tier-icon" aria-hidden="true">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <path d="M4 19h16"/>
                            <path d="M6 14l4-4 3 2 5-6"/>
                          </svg>
                        </span>
                        <span className="tier-label">Volatility</span>
                      </div>
                      <div className="tier-score">
                        {Number.isFinite(components.volatility) ? `${components.volatility.toFixed(2)}%` : '—'}
                      </div>
                      <div className="tier-bar">
                        <div
                          className="tier-bar-fill tier-fringe-fill"
                          style={{ width: Number.isFinite(components.volatility) ? `${Math.min(100, components.volatility * 20)}%` : '0%' }}
                        />
                      </div>
                      <div className="tier-meta">
                        Avg 3m: {Number.isFinite(components.avg_return_3m) ? `${components.avg_return_3m.toFixed(3)}%` : '--'}
                        {' · '}Avg 1m: {Number.isFinite(components.avg_return_1m) ? `${components.avg_return_1m.toFixed(3)}%` : '--'}
                      </div>
                    </div>
                  </div>

                  {/* Pipeline Status */}
                  <div className={`pipeline-status ${pipelineHealth?.running ? 'success' : 'warning'}`}>
                    <span className="status-indicator">{pipelineHealth?.running ? 'OK' : '!'}</span>
                    <span>
                      {pipelineHealth?.running
                        ? `LIVE: Tracking ${sentimentData.components.total_symbols ?? 0} symbols from Coinbase tape`
                        : 'Warming up — collecting price data...'}
                    </span>
                  </div>
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

              {!historySymbol && (
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
              )}

              <div className="info-section">
                <h3>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <circle cx="12" cy="12" r="10"/>
                    <path d="M12 16v-4M12 8h.01"/>
                  </svg>
                  Data Info
                </h3>
                <div className="explainer-box">
                  <p><strong>Refresh:</strong> Pipeline timestamp {lastUpdate}; auto-refresh every {Math.round(REFRESH_MS / 1000)}s.</p>
                  <p className="disclaimer">This is sentiment analysis, not financial advice. Always do your own research.</p>
                </div>
              </div>
            </section>
          )}

          {/* MARKET TAB */}
          {!loading && activeTab === 'market' && (
            <section className="tab-panel active" role="tabpanel">
              <div className="info-section">
                <div className="section-header">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <circle cx="12" cy="12" r="10"/>
                      <path d="M2 12 h20"/>
                    </svg>
                    Global Market Context
                  </h3>
                  <p className="section-desc">Market-wide read from your in-house tape pipeline. No per-coin deltas in this tab.</p>
                </div>
                <div className="stats-grid">
                  <div className="stat-card">
                    <div className="stat-content">
                      <span className="stat-label">Fear &amp; Greed</span>
                      <span className={`stat-value ${getFearGreedClass(fgValue)}`}>{fgValue !== null ? fgValue.toFixed(0) : '—'}</span>
                      <span className="stat-sublabel">
                        {fgLabel || 'Unavailable'}
                        {fgUpdatedMs ? ` · ${formatTimestamp(fgUpdatedMs)}` : ''}
                      </span>
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-content">
                      <span className="stat-label">Heat Label</span>
                      <span className={`stat-value ${toneClassForNumber(marketHeatScore)}`}>{marketHeatDisplay}</span>
                      <span className="stat-sublabel">Score: {marketHeatScore !== null ? marketHeatScore.toFixed(0) : '—'}</span>
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-content">
                      <span className="stat-label">Regime</span>
                      <span className="stat-value neutral">{marketRegimeDisplay}</span>
                      <span className="stat-sublabel">Pipeline: {marketStatus}</span>
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-content">
                      <span className="stat-label">Confidence</span>
                      <span className={`stat-value ${marketConfidence01 !== null && marketConfidence01 >= 0.6 ? 'positive' : marketConfidence01 !== null && marketConfidence01 <= 0.4 ? 'negative' : 'neutral'}`}>{marketConfidenceDisplay}</span>
                      <span className="stat-sublabel">
                        {globalPipe?.running ? 'Pipeline healthy' : 'Pipeline warming'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="info-section">
                <div className="section-header">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M4 19h16M7 15l3-3 3 2 4-5" />
                    </svg>
                    Composite Signals
                  </h3>
                </div>
                <div className="intel-summary-grid">
                  <div className="intel-summary-card">
                    <span className="intel-summary-label">Breadth</span>
                    <span className={`intel-summary-value ${toToneClass(toRatio01(marketBreadth) !== null ? toRatio01(marketBreadth) - 0.5 : null)}`}>{formatRatioPercent(marketBreadth, 0)}</span>
                    <span className="intel-summary-meta">components.breadth / marketBreadth</span>
                  </div>
                  <div className="intel-summary-card">
                    <span className="intel-summary-label">Volatility Regime</span>
                    <span className={`intel-summary-value ${toToneClass(toRatio01(marketVolatility) !== null ? 0.5 - toRatio01(marketVolatility) : null)}`}>{formatRatioPercent(marketVolatility, 1)}</span>
                    <span className="intel-summary-meta">components.volatility / volRegime</span>
                  </div>
                  <div className="intel-summary-card">
                    <span className="intel-summary-label">Momentum</span>
                    <span className={`intel-summary-value ${toToneClass(marketMomentum)}`}>{formatSignedNumber(marketMomentum, 2)}</span>
                    <span className="intel-summary-meta">components.momentum / marketMomentum</span>
                  </div>
                  <div className="intel-summary-card">
                    <span className="intel-summary-label">Impulse</span>
                    <span className={`intel-summary-value ${toToneClass(marketImpulse)}`}>{formatSignedNumber(marketImpulse, 3)}</span>
                    <span className="intel-summary-meta">components.impulse / flow</span>
                  </div>
                </div>
              </div>

              <div className="info-section">
                <div className="section-header">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M12 3l8 4v10l-8 4-8-4V7l8-4z" />
                    </svg>
                    Reason Stack
                  </h3>
                  <p className="section-desc">Best-effort reasons from your current market formula.</p>
                </div>
                {marketReasonCards.length > 0 ? (
                  <div className="insights-list">
                    {marketReasonCards.map((reason, index) => (
                      <div key={`${reason.title}-${index}`} className={`insight-box ${reason.tone}`}>
                        <div className="insight-content">
                          <strong>{reason.title}</strong>
                          <p>{reason.body}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="tab-empty">No reason stack available yet.</div>
                )}
              </div>

              <div className="info-section">
                <div className="section-header">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M3 3v18h18" />
                      <path d="M7 14l3-3 3 2 4-5" />
                    </svg>
                    Recent Heat History
                  </h3>
                  <p className="section-desc">Latest 8 global updates (most recent first).</p>
                </div>
                {marketTimeline.length > 0 ? (
                  <div className="feed-list">
                    {marketTimeline.map((item) => (
                      <div className="news-item" key={item.id}>
                        <div className="news-item-header">
                          <span className="news-item-source">{item.ts ? formatTimestamp(item.ts) : '--:--'}</span>
                          <span className="news-item-time">
                            Confidence {item.confidence !== null ? formatRatioPercent(item.confidence, 0) : '—'}
                          </span>
                        </div>
                        <div className="news-item-title">{item.label}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="tab-empty">No history points yet.</div>
                )}
              </div>

              <div className="info-section">
                <div className="section-header">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M10 13a5 5 0 007.07 0l2.12-2.12a5 5 0 00-7.07-7.07L10 6" />
                      <path d="M14 11a5 5 0 01-7.07 0L4.81 8.88a5 5 0 017.07-7.07L14 4" />
                    </svg>
                    Source Links
                  </h3>
                </div>
                <div className="source-links">
                  {sourceChips.map((sourceLink) => (
                    <a
                      key={`${sourceLink.label}-${sourceLink.href}`}
                      className="source-link-chip"
                      href={sourceLink.href}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {sourceLink.label}
                    </a>
                  ))}
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
                      <path d="M2 12 h20"/>
                    </svg>
                    Data Sources
                  </h3>
                  <p className="section-desc">Market heat is computed from live Coinbase tape data, seasoned with external signals.</p>
                </div>
              </div>

              <div className="sources-list">
                <div className="source-card tier-1">
                  <div className="source-info">
                    <div className="source-header">
                      <span className="source-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <circle cx="12" cy="12" r="2"/>
                          <path d="M5 12a7 7 0 0114 0M2 12a10 10 0 0120 0"/>
                        </svg>
                      </span>
                      <div>
                        <div className="source-name">Coinbase Price Tape</div>
                        <span className="source-status">{status}</span>
                      </div>
                    </div>
                    <div className="source-desc">Real-time price data for {sentimentData?.components?.total_symbols ?? 0} symbols. Breadth, momentum, and volatility computed from 1m &amp; 3m windows.</div>
                    <div className="source-meta">
                      <span>Weight: Primary</span>
                      <span>Refresh: ~8s</span>
                      <span>Updated: {lastUpdate}</span>
                    </div>
                  </div>
                  <div className="source-metrics">
                    <span className="tier-badge tier-1">PRIMARY</span>
                    <span className="source-score">Score {score !== null ? `${score}%` : '--'}</span>
                  </div>
                </div>

                <div className="source-card tier-2">
                  <div className="source-info">
                    <div className="source-header">
                      <span className="source-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M4 19h16M7 15l3-3 3 2 4-5"/>
                        </svg>
                      </span>
                      <div>
                        <div className="source-name">Coinbase Volume (1h Candles)</div>
                        <span className="source-status">{status}</span>
                      </div>
                    </div>
                    <div className="source-desc">Hourly volume from 1-minute candles. Powers whale detection and stealth move alerts.</div>
                    <div className="source-meta">
                      <span>Weight: High</span>
                      <span>Refresh: ~30s</span>
                    </div>
                  </div>
                  <div className="source-metrics">
                    <span className="tier-badge tier-2">VOLUME</span>
                  </div>
                </div>

                <div className={`source-card ${Number.isFinite(fg) ? 'tier-3' : 'tier-fringe'}`}>
                  <div className="source-info">
                    <div className="source-header">
                      <span className="source-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <circle cx="12" cy="12" r="10"/>
                          <path d="M9 10h.01M15 10h.01M8.5 15a5 5 0 017 0"/>
                        </svg>
                      </span>
                      <div>
                        <div className="source-name">Fear &amp; Greed Index</div>
                        <span className="source-status">{Number.isFinite(fg) ? 'LIVE' : 'OFFLINE'}</span>
                      </div>
                    </div>
                    <div className="source-desc">External macro signal from alternative.me. Cached with 5-min TTL.</div>
                    <div className="source-meta">
                      <span>Weight: Seasoning</span>
                      <span>TTL: 5 min</span>
                      {Number.isFinite(fg) && <span>Value: {fg}/100 ({getFearGreedLabel(fg)})</span>}
                    </div>
                  </div>
                  <div className="source-metrics">
                    <span className={`tier-badge ${Number.isFinite(fg) ? 'tier-3' : 'tier-fringe'}`}>
                      {Number.isFinite(fg) ? 'EXTERNAL' : 'N/A'}
                    </span>
                    {Number.isFinite(fg) && <span className="source-score">Score {fg}%</span>}
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
                      <path d="M9 22V12 h6v10"/>
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
                      sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                      referrerPolicy="no-referrer"
                      loading="lazy"
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
                    <div className="sentiment-muted">Warming up — collecting heat history...</div>
                  )}
                </div>
              </div>

              {/* Market-wide breadth and components - hide in per-coin view */}
              {!symbol && (
                <div className="charts-row">
                  <div className="info-section half">
                    <div className="section-header">
                      <h3>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <circle cx="12" cy="12" r="10"/>
                        </svg>
                        Market Breadth
                      </h3>
                    </div>
                  <div className="chart-container donut">
                    {sentimentData?.components ? (
                      <div className="breadth-visual">
                        <div className="breadth-row">
                          <span className="breadth-label">3m Window</span>
                          <div className="breadth-bar-wrap">
                            <div className="breadth-bar green" style={{width: `${sentimentData.components.breadth_3m ?? 0}%`}}></div>
                            <div className="breadth-bar red" style={{width: `${100 - (sentimentData.components.breadth_3m ?? 0)}%`}}></div>
                          </div>
                          <span className="breadth-pct">{sentimentData.components.breadth_3m?.toFixed(0) ?? '--'}%</span>
                        </div>
                        <div className="breadth-row">
                          <span className="breadth-label">1m Window</span>
                          <div className="breadth-bar-wrap">
                            <div className="breadth-bar green" style={{width: `${sentimentData.components.breadth_1m ?? 0}%`}}></div>
                            <div className="breadth-bar red" style={{width: `${100 - (sentimentData.components.breadth_1m ?? 0)}%`}}></div>
                          </div>
                          <span className="breadth-pct">{sentimentData.components.breadth_1m?.toFixed(0) ?? '--'}%</span>
                        </div>
                        <div className="breadth-legend">
                          <span className="legend-dot green"></span> Green
                          <span className="legend-dot red"></span> Red
                        </div>
                      </div>
                    ) : (
                      <div className="sentiment-muted">Warming up...</div>
                    )}
                  </div>
                </div>

                <div className="info-section half">
                  <div className="section-header">
                    <h3>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M18 20V10M12 20V4M6 20v-6"/>
                      </svg>
                      Heat Components
                    </h3>
                  </div>
                  <div className="chart-container donut">
                    {sentimentData?.components ? (
                      <div className="breadth-visual">
                        <div className="breadth-row">
                          <span className="breadth-label">Momentum</span>
                          <div className="breadth-bar-wrap">
                            <div className="breadth-bar" style={{
                              width: `${Math.max(0, Math.min(100, (( sentimentData.components.momentum_alignment ?? 0) + 1) * 50))}%`,
                              background: (sentimentData.components.momentum_alignment ?? 0) > 0 ? '#45ffb3' : '#ae4bf5'
                            }}></div>
                          </div>
                          <span className="breadth-pct">{sentimentData.components.momentum_alignment != null ? `${(sentimentData.components.momentum_alignment * 100).toFixed(0)}%` : '--'}</span>
                        </div>
                        <div className="breadth-row">
                          <span className="breadth-label">Volatility</span>
                          <div className="breadth-bar-wrap">
                            <div className="breadth-bar" style={{
                              width: `${Math.min(100, (sentimentData.components.volatility ?? 0) * 20)}%`,
                              background: '#f1b43a'
                            }}></div>
                          </div>
                          <span className="breadth-pct">{sentimentData.components.volatility?.toFixed(2) ?? '--'}%</span>
                        </div>
                        <div className="breadth-row">
                          <span className="breadth-label">Avg Return</span>
                          <div className="breadth-bar-wrap">
                            <div className="breadth-bar" style={{
                              width: `${Math.min(100, Math.abs(sentimentData.components.avg_return_3m ?? 0) * 50)}%`,
                              background: (sentimentData.components.avg_return_3m ?? 0) >= 0 ? '#45ffb3' : '#ff6b6b'
                            }}></div>
                          </div>
                          <span className="breadth-pct">{sentimentData.components.avg_return_3m?.toFixed(3) ?? '--'}%</span>
                        </div>
                      </div>
                    ) : (
                      <div className="sentiment-muted">Warming up...</div>
                    )}
                  </div>
                </div>
              </div>
              )}

              <div className="info-section">
                <div className="section-header">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M22 12 h-4l-3 9L9 3l-3 9H2"/>
                    </svg>
                    Sentiment vs Price Correlation
                  </h3>
                  <p className="section-desc">How sentiment aligns with price movement</p>
                </div>
                <div className="chart-container">
                  {sentimentHistory.length ? (
                    <canvas ref={correlationChartRef} role="img" aria-label="Correlation chart"></canvas>
                  ) : (
                    <div className="sentiment-muted">Warming up — collecting heat history...</div>
                  )}
                </div>
              </div>

              <div className="info-section">
                <div className="section-header">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M3 12 h18"/>
                      <path d="M3 6h12"/>
                      <path d="M3 18h8"/>
                    </svg>
                    Momentum snapshot
                  </h3>
                  <p className="section-desc">Change across sentiment history (first vs last point)</p>
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
                      </div>
                    );
                  })()}
                </div>
              </div>
            </section>
          )}

          {/* INSIGHTS TAB */}
          {!loading && activeTab === 'insights' && (
            <section className="tab-panel active" role="tabpanel">
              {/* Market Regime Summary */}
              <div className="info-section">
                <div className="section-header">
                  <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M13 2L3 14 h9l-1 8 10-12 h-9l1-8z"/>
                    </svg>
                    Market Regime
                  </h3>
                  <p className="section-desc">Current tape conditions from {sentimentData?.components?.total_symbols ?? 0} symbols</p>
                </div>
                <div className="stats-grid" style={{gridTemplateColumns: 'repeat(3, 1fr)'}}>
                  <div className="stat-card">
                    <div className="stat-content">
                      <span className="stat-label">Regime</span>
                      <span className={`stat-value ${regimeRaw === 'risk_on' ? 'positive' : regimeRaw === 'risk_off' ? 'negative' : 'neutral'}`}>
                        {regimeDisplay}
                      </span>
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-content">
                      <span className="stat-label">Heat</span>
                      <span className={`stat-value ${score !== null && score >= 55 ? 'positive' : score !== null && score <= 35 ? 'negative' : 'neutral'}`}>
                        {sentimentData?.heatLabel || 'NEUTRAL'}
                      </span>
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-content">
                      <span className="stat-label">Confidence</span>
                      <span className="stat-value neutral">{confidenceDisplay}</span>
                    </div>
                  </div>
                </div>
                {reasonLines.length > 0 && (
                  <div style={{marginTop: '0.5rem'}}>
                    {reasonLines.map((r, idx) => (
                      <div key={`insight-reason-${idx}`} className="sentiment-reason">{r}</div>
                    ))}
                  </div>
                )}
              </div>

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
                    <p className="section-desc">1m vs 3m timeframe disagreements detected on tape</p>
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
                  <p className="section-desc">Generated from tape heat and macro signals</p>
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

          {/* ALERTS TAB */}
          {activeTab === 'alerts' && (
            <section className="tab-panel active" role="tabpanel">
              <AlertsTab filterSymbol={symbol || null} />
            </section>
          )}
        </main>

        {/* Footer */}
        <footer className="popup-footer">
          <div className="footer-left">
            <span className="data-source">Powered by Coinbase tape data · <span>{sentimentData?.components?.total_symbols ?? 0}</span> symbols tracked</span>
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
