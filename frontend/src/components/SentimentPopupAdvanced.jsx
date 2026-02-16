import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { useMarketHeat } from '../hooks/useMarketHeat';
import { useData } from '../context/DataContext';
import { API_ENDPOINTS, fetchData } from '../api';
import AlertsTab from './AlertsTab';
import MarketSignalCard from './MarketSignalCard';
import '../styles/sentiment-popup-advanced.css';

const REFRESH_MS = 15000;
const COIN_REFRESH_MS = 30000;
const INTEL_REFRESH_MS = 60000;
const COIN_ALERT_REFRESH_MS = 60000;

const normalizeTab = (value) => {
  const raw = String(value || '').trim().toLowerCase();
  if (raw === 'alerts' || raw === 'feed' || raw === 'global') return 'alerts';
  if (raw === 'pulse' || raw === 'market') return 'pulse';
  if (raw === 'intel' || raw === 'sources') return 'intel';
  return 'coin';
};

const normalizeSymbol = (value) => {
  const raw = String(value || '').trim().toUpperCase();
  if (!raw) return null;
  if (raw.includes('-')) return raw.split('-', 1)[0] || null;
  if (raw.endsWith('USD') && raw.length > 3) return raw.slice(0, -3) || null;
  return raw;
};

const resolveTvSymbol = (sym, exchange = 'auto') => {
  const s = String(sym || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  const coinbase = s ? `COINBASE:${s}USD` : 'COINBASE:BTCUSD';
  const binance = s ? `BINANCE:${s}USDT` : 'BINANCE:BTCUSDT';

  if (exchange === 'coinbase') return { symbol: coinbase, source: 'coinbase' };
  if (exchange === 'binance') return { symbol: binance, source: 'binance' };

  if (!s) return { symbol: coinbase, source: 'coinbase' };
  if (s === 'BTC' || s === 'ETH') return { symbol: coinbase, source: 'coinbase' };
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

const toNumber = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const formatPercent = (value) => {
  const n = toNumber(value);
  if (n === null) return '--';
  const abs = Math.abs(n);
  const digits = abs >= 10 ? 1 : abs >= 1 ? 2 : 3;
  return `${n >= 0 ? '+' : ''}${n.toFixed(digits)}%`;
};

const trendScore = (change1m, change3m, change1h) => {
  let score = 0;
  if (change1m !== null) score += change1m > 0 ? 1 : change1m < 0 ? -1 : 0;
  if (change3m !== null) score += change3m > 0 ? 2 : change3m < 0 ? -2 : 0;
  if (change1h !== null) score += change1h > 0 ? 3 : change1h < 0 ? -3 : 0;
  return score;
};

const trendLabel = (score) => {
  if (score >= 4) return 'Bullish';
  if (score >= 2) return 'Leaning Bullish';
  if (score <= -4) return 'Bearish';
  if (score <= -2) return 'Leaning Bearish';
  return 'Neutral';
};

const toneClass = (value) => {
  const n = toNumber(value);
  if (n === null) return 'neutral';
  if (n > 0) return 'positive';
  if (n < 0) return 'negative';
  return 'neutral';
};

const gaugePosition = (indexValue) => {
  const score = Math.max(0, Math.min(100, Number(indexValue) || 0));
  const angle = 180 - ((score / 100) * 180);
  const radians = (angle * Math.PI) / 180;
  const cx = 100 + 80 * Math.cos(radians);
  const cy = 100 - 80 * Math.sin(radians);
  const offset = 251.2 - (251.2 * score / 100);
  return { cx, cy, offset };
};

const pressureLabel = (indexValue) => {
  const score = Math.max(0, Math.min(100, Number(indexValue) || 0));
  if (score <= 20) return 'Fear';
  if (score <= 40) return 'Cautious';
  if (score <= 60) return 'Neutral';
  if (score <= 80) return 'Risk-On';
  return 'Euphoria';
};

const normalizeTsMs = (value) => {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value < 1e12 ? value * 1000 : value;
  }
  const n = Number(value);
  if (Number.isFinite(n)) return n < 1e12 ? n * 1000 : n;
  const parsed = Date.parse(String(value));
  return Number.isFinite(parsed) ? parsed : null;
};

const parseCoinInsights = (payload) => {
  const root = payload?.data && typeof payload.data === 'object' ? payload.data : (payload || {});
  return {
    symbol: normalizeSymbol(root.symbol) || null,
    change1m: toNumber(root.change_1m ?? root.change1m ?? root.metrics?.change_1m ?? root.metrics?.change1m),
    change3m: toNumber(root.change_3m ?? root.change3m ?? root.metrics?.change_3m ?? root.metrics?.change3m),
    change1h: toNumber(root.change_1h ?? root.change1h ?? root.d1h ?? root.metrics?.change_1h ?? root.metrics?.change1h),
    volumeChange1h: toNumber(root.volume_change_1h ?? root.volumeChange1h ?? root.metrics?.volume_change_1h ?? root.metrics?.volumeChange1h),
    updatedAt: root.updated_at ?? root.updatedAt ?? root.timestamp ?? null,
  };
};

const clamp = (value, min, max) => {
  const n = Number(value);
  if (!Number.isFinite(n)) return min;
  if (n < min) return min;
  if (n > max) return max;
  return n;
};

const coinScoreLabel = (score) => {
  if (score === null) return 'Awaiting tape';
  if (score <= 35) return 'Cautious';
  if (score <= 65) return 'Neutral';
  return 'Aggressive';
};

const humanTime = (value) => {
  const tsMs = normalizeTsMs(value);
  if (!Number.isFinite(tsMs)) return '--';
  return new Date(tsMs).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

const formatCompactNumber = (value) => {
  const n = toNumber(value);
  if (n === null) return '--';
  const abs = Math.abs(n);
  if (abs >= 1000) {
    return new Intl.NumberFormat(undefined, {
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(n);
  }
  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 0,
  }).format(Math.round(n));
};

const sentimentLabelFromScore = (score) => {
  const n = toNumber(score);
  if (n === null) return null;
  if (n >= 0.2) return 'Bullish';
  if (n <= -0.2) return 'Bearish';
  return 'Mixed';
};

const sentimentClassFromLabel = (label) => {
  const raw = String(label || '').trim().toLowerCase();
  if (raw.includes('bull')) return 'positive';
  if (raw.includes('bear')) return 'negative';
  return 'neutral';
};

const isProxySocialSource = (source) => {
  const raw = String(source || '').trim().toLowerCase();
  return raw === 'coingecko';
};

const parseSentimentPayload = (value) => {
  if (!value && value !== 0) return null;

  if (typeof value === 'object') {
    const labelRaw = String(value.label || value.sentiment || '').trim();
    const netScore = toNumber(value.net_score ?? value.netScore ?? value.score ?? value.value);
    const bullishPct = toNumber(value.bullish_pct ?? value.bullishPct ?? value.bullish);
    const bearishPct = toNumber(value.bearish_pct ?? value.bearishPct ?? value.bearish);
    const label = labelRaw || sentimentLabelFromScore(netScore) || (bullishPct !== null || bearishPct !== null ? 'Mixed' : null);
    if (!label && netScore === null && bullishPct === null && bearishPct === null) return null;
    return {
      label: label || 'Mixed',
      netScore,
      bullishPct,
      bearishPct,
    };
  }

  const numeric = toNumber(value);
  if (numeric !== null) {
    const normalized = Math.abs(numeric) <= 1
      ? numeric
      : numeric >= 0 && numeric <= 100
        ? ((numeric - 50) / 50)
        : Math.max(-1, Math.min(1, numeric / 100));
    return {
      label: sentimentLabelFromScore(normalized) || 'Mixed',
      netScore: normalized,
      bullishPct: Math.max(0, Math.min(100, Math.round((normalized + 1) * 50))),
      bearishPct: Math.max(0, Math.min(100, Math.round((1 - normalized) * 50))),
    };
  }

  const text = String(value || '').trim();
  if (!text) return null;
  return {
    label: text,
    netScore: null,
    bullishPct: null,
    bearishPct: null,
  };
};

const parseSocialMetrics = (value) => {
  const root = value && typeof value === 'object' ? value : {};
  return {
    socialVolume24h: toNumber(root.social_volume_24h ?? root.socialVolume24h),
    socialEngagement24h: toNumber(root.social_engagement_24h ?? root.socialEngagement24h),
    socialDominance24h: toNumber(root.social_dominance_24h ?? root.socialDominance24h),
    sentiment24h: parseSentimentPayload(root.sentiment_24h ?? root.sentiment24h),
    socialRank: toNumber(root.social_rank ?? root.socialRank),
    socialHeat: toNumber(root.social_heat ?? root.socialHeat),
    socialHeatTrend: String((root.social_heat_trend ?? root.socialHeatTrend) || '').trim().toLowerCase() || null,
    posts60m: toNumber(root.posts_60m ?? root.posts60m),
    posts24h: toNumber(root.posts_24h ?? root.posts24h),
    uniqueAuthors24h: toNumber(root.unique_authors_24h ?? root.uniqueAuthors24h),
    source: String(root.source || '').trim().toLowerCase() || null,
    updatedAt: root.updated_at ?? root.updatedAt ?? null,
  };
};

const parseIntel = (payload) => {
  const root = payload && typeof payload === 'object' ? payload : {};
  const eventsRaw = root.events && typeof root.events === 'object' ? root.events : null;
  const newsRaw = root.news && typeof root.news === 'object' ? root.news : null;
  const events = eventsRaw || newsRaw || { status: 'offline', items: [] };
  const news = newsRaw || eventsRaw || { status: 'offline', items: [] };
  const social = root.social && typeof root.social === 'object' ? root.social : { status: 'offline', items: [], metrics: null };
  return {
    symbol: normalizeSymbol(root.symbol) || null,
    status: String(root.status || events.status || social.status || 'offline'),
    coinId: root.coin_id || null,
    events: {
      status: String(events.status || 'offline'),
      items: Array.isArray(events.items) ? events.items : [],
    },
    news: {
      status: String(news.status || 'offline'),
      items: Array.isArray(news.items) ? news.items : [],
    },
    social: {
      status: String(social.status || 'offline'),
      items: Array.isArray(social.items) ? social.items : [],
      metrics: parseSocialMetrics(social.metrics),
    },
    ts: root.ts || null,
  };
};

const parseCoinAlertsPayload = (payload) => {
  const root = payload && typeof payload === 'object' ? payload : {};
  const recentRaw = Array.isArray(root.recent)
    ? root.recent
    : Array.isArray(root.items)
      ? root.items
      : [];
  const activeRaw = Array.isArray(root.active) ? root.active : [];
  const sourcesRaw = Array.isArray(root.sources_used)
    ? root.sources_used
    : Array.isArray(root.sourcesUsed)
      ? root.sourcesUsed
      : [];
  return {
    status: String(root.status || 'offline'),
    active: activeRaw.filter((row) => row && typeof row === 'object'),
    recent: recentRaw.filter((row) => row && typeof row === 'object'),
    sourcesUsed: sourcesRaw
      .map((src) => String(src || '').trim().toLowerCase())
      .filter(Boolean),
    meta: root.meta && typeof root.meta === 'object' ? root.meta : {},
  };
};

const symbolFromAlert = (alert) => {
  const raw = String(alert?.symbol || alert?.product_id || '').toUpperCase();
  if (!raw) return null;
  if (raw.includes('-')) return raw.split('-', 1)[0] || null;
  return raw;
};

const alertTsMs = (alert) => {
  return (
    (Number.isFinite(alert?.event_ts_ms) && alert.event_ts_ms) ||
    (Number.isFinite(alert?.ts_ms) && alert.ts_ms) ||
    normalizeTsMs(alert?.event_ts) ||
    normalizeTsMs(alert?.ts) ||
    0
  );
};

const alertIdentity = (alert) => {
  if (alert?.id != null) return String(alert.id);
  if (alert?.alert_id != null) return String(alert.alert_id);
  const symbol = symbolFromAlert(alert) || '';
  const type = String(alert?.type_key || alert?.type || '').toLowerCase();
  return `${symbol}:${type}:${alertTsMs(alert)}`;
};

const SentimentPopupAdvanced = ({ isOpen, onClose, symbol, defaultTab = 'coin' }) => {
  const {
    error,
    refresh,
    pipelineStatus,
  } = useMarketHeat();
  const { activeAlerts = [], alertsRecent = [] } = useData() || {};

  const [activeTab, setActiveTab] = useState(normalizeTab(defaultTab));
  const [chartExchange, setChartExchange] = useState('auto');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const [coinInsights, setCoinInsights] = useState(null);
  const [coinInsightsLoading, setCoinInsightsLoading] = useState(false);
  const [coinInsightsError, setCoinInsightsError] = useState(null);

  const [coinIntel, setCoinIntel] = useState(null);
  const [coinIntelLoading, setCoinIntelLoading] = useState(false);
  const [coinIntelError, setCoinIntelError] = useState(null);

  const [coinAlertsPayload, setCoinAlertsPayload] = useState(() => ({
    status: 'offline',
    active: [],
    recent: [],
    sourcesUsed: [],
    meta: {},
  }));
  const [coinAlertsLoading, setCoinAlertsLoading] = useState(false);
  const [coinAlertsError, setCoinAlertsError] = useState(null);
  const [coinAlertsHydrated, setCoinAlertsHydrated] = useState(false);

  const coinSymbol = useMemo(() => normalizeSymbol(symbol), [symbol]);

  useEffect(() => {
    if (isOpen) setActiveTab(normalizeTab(defaultTab));
  }, [isOpen, defaultTab]);

  useEffect(() => {
    const onEsc = (evt) => {
      if (evt.key === 'Escape' && isOpen) onClose();
    };
    if (isOpen) {
      document.addEventListener('keydown', onEsc);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', onEsc);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  const loadCoinInsights = useCallback(async ({ silent = false } = {}) => {
    if (!coinSymbol || !isOpen) {
      setCoinInsights(null);
      setCoinInsightsError(null);
      return null;
    }
    if (!silent) setCoinInsightsLoading(true);
    try {
      const endpoint = API_ENDPOINTS.insights
        ? API_ENDPOINTS.insights(coinSymbol)
        : `/api/insights/${encodeURIComponent(coinSymbol)}`;
      const payload = await fetchData(endpoint);
      const parsed = parseCoinInsights(payload);
      setCoinInsights(parsed);
      setCoinInsightsError(null);
      return parsed;
    } catch (err) {
      setCoinInsightsError(String(err?.message || err || 'Failed to load coin pressure'));
      return null;
    } finally {
      if (!silent) setCoinInsightsLoading(false);
    }
  }, [coinSymbol, isOpen]);

  const loadCoinIntel = useCallback(async ({ silent = false } = {}) => {
    if (!coinSymbol || !isOpen) {
      setCoinIntel(null);
      setCoinIntelError(null);
      return null;
    }
    if (!silent) setCoinIntelLoading(true);
    try {
      const endpoint = API_ENDPOINTS.coinIntel
        ? API_ENDPOINTS.coinIntel(coinSymbol)
        : `/api/coin-intel?symbol=${encodeURIComponent(coinSymbol)}`;
      const payload = await fetchData(endpoint);
      const parsed = parseIntel(payload);
      setCoinIntel(parsed);
      setCoinIntelError(null);
      return parsed;
    } catch (err) {
      setCoinIntelError(String(err?.message || err || 'Failed to load coin intel'));
      return null;
    } finally {
      if (!silent) setCoinIntelLoading(false);
    }
  }, [coinSymbol, isOpen]);

  const loadCoinAlerts = useCallback(async ({ silent = false } = {}) => {
    if (!coinSymbol || !isOpen) {
      setCoinAlertsPayload({
        status: 'offline',
        active: [],
        recent: [],
        sourcesUsed: [],
        meta: {},
      });
      setCoinAlertsError(null);
      setCoinAlertsHydrated(false);
      return null;
    }
    if (!silent) setCoinAlertsLoading(true);
    try {
      const endpoint = API_ENDPOINTS.coinAlerts
        ? API_ENDPOINTS.coinAlerts(coinSymbol)
        : `/api/coin-alerts?symbol=${encodeURIComponent(coinSymbol)}`;
      const payload = await fetchData(endpoint);
      const parsed = parseCoinAlertsPayload(payload);
      setCoinAlertsPayload(parsed);
      setCoinAlertsError(null);
      setCoinAlertsHydrated(true);
      return parsed;
    } catch (err) {
      setCoinAlertsError(String(err?.message || err || 'Failed to load coin alerts'));
      return null;
    } finally {
      if (!silent) setCoinAlertsLoading(false);
    }
  }, [coinSymbol, isOpen]);

  useEffect(() => {
    if (!isOpen || !coinSymbol) {
      setCoinInsights(null);
      setCoinInsightsError(null);
      setCoinInsightsLoading(false);
      return;
    }

    let cancelled = false;
    const run = async (silent = false) => {
      if (cancelled) return;
      await loadCoinInsights({ silent });
    };

    run(false);
    const id = setInterval(() => run(true), COIN_REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [isOpen, coinSymbol, loadCoinInsights]);

  useEffect(() => {
    if (!isOpen || !coinSymbol) {
      if (!coinSymbol) {
        setCoinIntel(null);
        setCoinIntelError(null);
        setCoinIntelLoading(false);
      }
      return;
    }

    let cancelled = false;
    const run = async (silent = false) => {
      if (cancelled) return;
      await loadCoinIntel({ silent });
    };

    run(activeTab !== 'intel');
    const id = setInterval(() => run(true), INTEL_REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [isOpen, coinSymbol, loadCoinIntel, activeTab]);

  useEffect(() => {
    if (!isOpen || !coinSymbol) {
      if (!coinSymbol) {
        setCoinAlertsPayload({
          status: 'offline',
          active: [],
          recent: [],
          sourcesUsed: [],
          meta: {},
        });
        setCoinAlertsError(null);
        setCoinAlertsLoading(false);
        setCoinAlertsHydrated(false);
      }
      return;
    }

    let cancelled = false;
    const run = async (silent = false) => {
      if (cancelled) return;
      await loadCoinAlerts({ silent });
    };

    run(false);
    const id = setInterval(() => run(true), COIN_ALERT_REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [isOpen, coinSymbol, loadCoinAlerts]);

  const fallbackAllAlerts = useMemo(() => {
    const merged = [
      ...(Array.isArray(activeAlerts) ? activeAlerts : []),
      ...(Array.isArray(alertsRecent) ? alertsRecent : []),
    ];
    const seen = new Set();
    const out = [];
    for (const row of merged) {
      if (!row || typeof row !== 'object') continue;
      const key = alertIdentity(row);
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(row);
    }
    return out;
  }, [activeAlerts, alertsRecent]);

  const fallbackCoinAlerts = useMemo(() => {
    if (!coinSymbol) return [];
    const filtered = fallbackAllAlerts.filter((a) => symbolFromAlert(a) === coinSymbol);
    return [...filtered].sort((a, b) => alertTsMs(b) - alertTsMs(a));
  }, [fallbackAllAlerts, coinSymbol]);

  const coinAlerts = useMemo(() => {
    if (!coinSymbol) return [];
    if (coinAlertsHydrated) {
      const recent = Array.isArray(coinAlertsPayload.recent) ? coinAlertsPayload.recent : [];
      return [...recent].sort((a, b) => alertTsMs(b) - alertTsMs(a));
    }
    return fallbackCoinAlerts;
  }, [coinSymbol, coinAlertsHydrated, coinAlertsPayload.recent, fallbackCoinAlerts]);

  const breakoutState = useMemo(() => {
    const top = coinAlerts[0];
    if (!top) return 'No breakout';
    const type = String(top.type_key || top.type || '').toLowerCase();
    if (type.includes('moonshot') || type.includes('breakout')) return 'Breakout Up';
    if (type.includes('crater') || type.includes('dump')) return 'Breakout Down';
    return 'No breakout';
  }, [coinAlerts]);

  const change1m = toNumber(coinInsights?.change1m);
  const change3m = toNumber(coinInsights?.change3m);
  const change1h = toNumber(coinInsights?.change1h);
  const volumeChange1h = toNumber(coinInsights?.volumeChange1h);
  const alignmentScore = trendScore(change1m, change3m, change1h);
  const hasCoinTape = (change1m !== null || change3m !== null || change1h !== null || volumeChange1h !== null || coinAlerts.length > 0);

  const volumeConfirms = useMemo(() => {
    if (change3m === null || volumeChange1h === null) return false;
    if (Math.abs(volumeChange1h) < 10) return false;
    const priceSign = change3m > 0 ? 1 : change3m < 0 ? -1 : 0;
    const volSign = volumeChange1h > 0 ? 1 : volumeChange1h < 0 ? -1 : 0;
    return priceSign !== 0 && priceSign === volSign;
  }, [change3m, volumeChange1h]);

  const confidencePct = useMemo(() => {
    if (!hasCoinTape) return null;
    const alignment = Math.min(1, Math.abs(alignmentScore) / 6);
    let streakRaw = 0;
    for (const alert of coinAlerts) {
      const streak = toNumber(alert?.evidence?.streak ?? alert?.extra?.streak);
      if (streak !== null && streak > 0) {
        streakRaw = Math.max(streakRaw, streak);
      }
    }
    const streak = Math.min(1, Math.max(0, streakRaw) / 4);
    const volumeConfirm = volumeConfirms ? 1 : 0;
    return Math.round(((0.45 * alignment) + (0.35 * volumeConfirm) + (0.2 * streak)) * 100);
  }, [hasCoinTape, alignmentScore, coinAlerts, volumeConfirms]);

  const signalFlags = useMemo(() => {
    const recentTypes = coinAlerts.slice(0, 8).map((a) => String(a?.type_key || a?.type || '').toLowerCase());
    return {
      hasReversal: recentTypes.some((t) => t.includes('reversal') || t.includes('trend_break')),
      hasFakeout: recentTypes.some((t) => t.includes('fakeout')),
      hasSqueeze: recentTypes.some((t) => t.includes('squeeze') || t.includes('volatility_expansion')),
      hasExhaustion: recentTypes.some((t) => t.includes('exhaustion')),
      hasMomentum: recentTypes.some((t) => t.includes('moonshot') || t.includes('breakout') || t.includes('coin_fomo')),
    };
  }, [coinAlerts]);

  const persistenceStreak = useMemo(() => {
    for (const alert of coinAlerts) {
      const streak = toNumber(alert?.evidence?.streak ?? alert?.extra?.streak);
      if (streak !== null && streak > 0) return Math.round(streak);
      const type = String(alert?.type_key || alert?.type || '').toLowerCase();
      if (type.includes('persistent')) return 1;
    }
    return null;
  }, [coinAlerts]);

  const coinScore = useMemo(() => {
    if (!hasCoinTape) return null;
    let score = 50;
    if (change1m !== null) score += clamp(change1m * 2.5, -14, 14);
    if (change3m !== null) score += clamp(change3m * 4.0, -20, 20);
    if (change1h !== null) score += clamp(change1h * 2.5, -20, 20);
    if (volumeChange1h !== null) score += clamp(volumeChange1h / 10, -14, 14);
    score += alignmentScore * 3;
    if (volumeConfirms) score += 8;
    if (signalFlags.hasMomentum) score += 6;
    if (signalFlags.hasFakeout) score -= 10;
    if (signalFlags.hasReversal) score -= 6;
    if (signalFlags.hasExhaustion) score -= 8;
    return Math.round(clamp(score, 0, 100));
  }, [
    hasCoinTape,
    change1m,
    change3m,
    change1h,
    volumeChange1h,
    alignmentScore,
    volumeConfirms,
    signalFlags,
  ]);

  const primaryAction = useMemo(() => {
    const topType = String(coinAlerts[0]?.type_key || coinAlerts[0]?.type || '').toLowerCase();
    if (topType.includes('fakeout')) return 'Fakeout risk: avoid chasing and wait for reclaim confirmation.';
    if (topType.includes('reversal') || topType.includes('trend_break')) return 'Reversal signal active: wait for retest confirmation before entry.';
    if (topType.includes('squeeze') || topType.includes('volatility_expansion')) return 'Compression just broke: watch continuation on the next close.';
    if (topType.includes('exhaustion')) return 'Exhaustion flagged: tighten risk and avoid late momentum entries.';
    if (topType.includes('whale') || topType.includes('stealth')) return 'Participation is leading price: watch for directional confirmation.';
    if (breakoutState === 'Breakout Up') return 'Momentum is expanding: watch continuation above the recent high.';
    if (breakoutState === 'Breakout Down') return 'Breakdown pressure is active: avoid countertrend entries until reclaim.';
    if (alignmentScore >= 3 && volumeConfirms) return 'Trend and volume align: favor pullback entries over chasing.';
    if (alignmentScore <= -3 && volumeConfirms) return 'Downtrend and volume align: protect longs and wait for base formation.';
    return 'No high-conviction setup yet: wait for alignment plus volume confirmation.';
  }, [coinAlerts, breakoutState, alignmentScore, volumeConfirms]);

  const socialMetrics = coinIntel?.social?.metrics || null;
  const socialHeat = toNumber(socialMetrics?.socialHeat);
  const socialVolume24h = toNumber(socialMetrics?.socialVolume24h ?? socialMetrics?.posts24h);
  const socialEngagement24h = toNumber(socialMetrics?.socialEngagement24h);
  const socialDominance24h = toNumber(socialMetrics?.socialDominance24h);
  const socialRank = toNumber(socialMetrics?.socialRank);
  const socialPosts60m = toNumber(socialMetrics?.posts60m);
  const socialPosts24h = toNumber(socialMetrics?.posts24h);
  const socialUniqueAuthors24h = toNumber(socialMetrics?.uniqueAuthors24h);
  const socialSentiment = socialMetrics?.sentiment24h || null;
  const socialSentimentLabel = String(socialSentiment?.label || '').trim() || null;
  const socialSentimentNet = toNumber(socialSentiment?.netScore);
  const socialSentimentDisplay = socialSentimentLabel || sentimentLabelFromScore(socialSentimentNet);
  const socialUpdatedAt = socialMetrics?.updatedAt || null;
  const socialSource = String(socialMetrics?.source || '').trim().toLowerCase() || null;
  const socialIsProxy = isProxySocialSource(socialSource);

  const socialSourceLabel = useMemo(() => {
    if (!socialSource) return null;
    if (socialSource === 'coinpaprika') return 'CoinPaprika';
    if (socialSource === 'lunarcrush') return 'LunarCrush';
    if (socialSource === 'mixed') return 'Mixed';
    return socialSource;
  }, [socialSource]);

  const socialHeatTrend = useMemo(() => {
    if (socialIsProxy) return null;
    const raw = String(socialMetrics?.socialHeatTrend || '').trim().toLowerCase();
    if (raw.includes('rise') || raw.includes('spike') || raw.includes('up')) return 'rising';
    if (raw.includes('collapse') || raw.includes('fall') || raw.includes('down')) return 'collapsing';
    if (raw.includes('flat') || raw.includes('neutral') || raw.includes('stable')) return 'flat';
    if (socialPosts60m !== null && socialPosts24h !== null && socialPosts24h > 0) {
      const expectedHourly = Math.max(1, socialPosts24h / 24);
      const ratio = socialPosts60m / expectedHourly;
      if (ratio >= 1.5) return 'rising';
      if (ratio <= 0.6) return 'collapsing';
      return 'flat';
    }
    return null;
  }, [socialMetrics, socialPosts60m, socialPosts24h, socialIsProxy]);

  const socialHeatTone = socialHeat === null ? 'neutral' : socialHeat >= 66 ? 'positive' : socialHeat <= 35 ? 'negative' : 'neutral';
  const socialSentimentTone = sentimentClassFromLabel(socialSentimentDisplay);

  const hasMeaningfulSocialMetrics = useMemo(() => (
    socialHeat !== null ||
    (socialVolume24h !== null && socialVolume24h > 0) ||
    (socialEngagement24h !== null && socialEngagement24h > 0) ||
    (socialDominance24h !== null && socialDominance24h > 0) ||
    (socialRank !== null && socialRank > 0) ||
    (socialPosts60m !== null && socialPosts60m > 0) ||
    (socialUniqueAuthors24h !== null && socialUniqueAuthors24h > 0) ||
    Boolean(socialSentimentDisplay) ||
    Boolean(socialUpdatedAt)
  ), [
    socialHeat,
    socialVolume24h,
    socialEngagement24h,
    socialDominance24h,
    socialRank,
    socialPosts60m,
    socialUniqueAuthors24h,
    socialSentimentDisplay,
    socialUpdatedAt,
  ]);

  const socialActionLine = useMemo(() => {
    if (socialIsProxy) return null;
    if (change3m === null) return null;
    if (socialHeat === null && !socialHeatTrend) return null;

    const rising = socialHeatTrend === 'rising';
    const collapsing = socialHeatTrend === 'collapsing';
    const heatSpike = rising || (socialHeat !== null && socialHeat >= 70);
    const heatCollapse = collapsing || (socialHeat !== null && socialHeat <= 35);

    if (change3m > 0 && rising) {
      return 'Momentum is supported by attention: favor pullbacks and avoid chasing extension.';
    }
    if (change3m > 0 && heatCollapse) {
      return 'Price is up but attention is fading: treat this as thin and watch for fakeout risk.';
    }
    if (change3m < 0 && heatSpike) {
      return 'Capitulation chatter is spiking: wait for reclaim confirmation before countertrend entries.';
    }
    if (Math.abs(change3m) < 0.05 && heatSpike) {
      return 'Attention is leading price: set breakout and breakdown alerts before the next impulse.';
    }
    return null;
  }, [change3m, socialHeat, socialHeatTrend, socialIsProxy]);

  const coinAlertsSourcesLabel = useMemo(() => {
    const list = Array.isArray(coinAlertsPayload?.sourcesUsed) ? coinAlertsPayload.sourcesUsed : [];
    if (!list.length) return null;
    return list.join(' · ');
  }, [coinAlertsPayload]);

  const coinAlertsScopeNote = useMemo(() => {
    if (!coinSymbol) return null;
    if (coinAlertsError && !coinAlertsHydrated) {
      return 'Unified coin alerts unavailable. Using tape-only fallback.';
    }
    if (coinAlertsHydrated && coinAlertsSourcesLabel) {
      return `Unified alerts sources: ${coinAlertsSourcesLabel}`;
    }
    if (coinAlertsLoading && !coinAlertsHydrated) {
      return 'Loading unified coin alerts...';
    }
    return null;
  }, [coinSymbol, coinAlertsError, coinAlertsHydrated, coinAlertsSourcesLabel, coinAlertsLoading]);

  const structureState = useMemo(() => {
    if (signalFlags.hasFakeout) return 'Fakeout';
    if (signalFlags.hasReversal) return 'Reversal';
    if (signalFlags.hasExhaustion) return 'Exhaustion';
    if (signalFlags.hasSqueeze) return 'Expansion';
    if (signalFlags.hasMomentum) return 'Momentum';
    return 'Calm';
  }, [signalFlags]);

  const tvResolved = resolveTvSymbol(coinSymbol, chartExchange);
  const tvUrl = buildTradingViewEmbedUrl(tvResolved.symbol);

  const handleOverlayClick = (event) => {
    if (event.target.classList.contains('sentiment-overlay')) onClose();
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await Promise.all([
      refresh({ freshLatest: true }),
      loadCoinInsights({ silent: false }),
      loadCoinIntel({ silent: false }),
      loadCoinAlerts({ silent: false }),
    ]);
    setTimeout(() => setIsRefreshing(false), 700);
  };

  if (!isOpen) return null;

  return (
    <div
      className={`sentiment-overlay ${isOpen ? 'active' : ''}`}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="sentimentTitle"
    >
      <div className="sentiment-popup" data-sentiment-symbol={coinSymbol || ''}>
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
              <h1 id="sentimentTitle">Coin Pressure {coinSymbol ? `· ${coinSymbol}` : ''}</h1>
              <p className="subtitle">Tape + alerts for this coin only.</p>
            </div>
          </div>

          <div className="header-right">
            <div className={`live-indicator ${String(pipelineStatus || 'STALE').toLowerCase()}`}>
              <span className={`pulse ${String(pipelineStatus || 'STALE').toLowerCase()}`} aria-hidden="true" />
              <span className="live-text">{pipelineStatus || 'STALE'}</span>
            </div>
            <button className="close-btn" onClick={onClose} aria-label="Close popup">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>
        </header>

        <nav className="tab-nav" role="tablist">
          <button
            className={`tab-btn ${activeTab === 'alerts' ? 'active' : ''}`}
            onClick={() => setActiveTab('alerts')}
            role="tab"
            aria-selected={activeTab === 'alerts'}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M15 17H9" />
              <path d="M18 17V11a6 6 0 10-12 0v6" />
              <path d="M5 17h14" />
              <path d="M10 21a2 2 0 004 0" />
            </svg>
            Alerts
          </button>
          <button
            className={`tab-btn ${activeTab === 'coin' ? 'active' : ''}`}
            onClick={() => setActiveTab('coin')}
            role="tab"
            aria-selected={activeTab === 'coin'}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M4 19h16M7 15l3-3 3 2 4-5" />
            </svg>
            Coin
          </button>
          <button
            className={`tab-btn ${activeTab === 'pulse' ? 'active' : ''}`}
            onClick={() => setActiveTab('pulse')}
            role="tab"
            aria-selected={activeTab === 'pulse'}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="12" r="9"/>
              <path d="M4 12h16M12 3v18"/>
            </svg>
            Pulse
          </button>
          <button
            className={`tab-btn ${activeTab === 'intel' ? 'active' : ''}`}
            onClick={() => setActiveTab('intel')}
            role="tab"
            aria-selected={activeTab === 'intel'}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M10 13a5 5 0 007.07 0l2.12-2.12a5 5 0 00-7.07-7.07L10 6"/>
              <path d="M14 11a5 5 0 01-7.07 0L4.81 8.88a5 5 0 017.07-7.07L14 4"/>
            </svg>
            Intel
          </button>
        </nav>

        <main className="tab-content">
          {error ? (
            <div className="coin-history-note error mw-fetch-note">Pulse feed temporarily unavailable. Showing last known tape snapshot.</div>
          ) : null}

          {activeTab === 'alerts' && (
            <section className="tab-panel active" role="tabpanel">
              {!coinSymbol ? (
                <div className="tab-empty">Choose a coin from the board to load its alerts and events.</div>
              ) : (
                <AlertsTab filterSymbol={coinSymbol} compact={true} />
              )}
            </section>
          )}

          {activeTab === 'coin' && (
            <section className="tab-panel active" role="tabpanel">
              {!coinSymbol ? (
                <div className="tab-empty">Choose a coin from the board to load its score and coin-specific alerts.</div>
              ) : (
                <>
                  <div className="info-section mw-coin-overview">
                    <div className="section-header">
                      <h3>Coin Overview</h3>
                      <p className="section-desc">One-glance score and immediate tape-driven action for {coinSymbol}.</p>
                    </div>
                    <div className="mw-overview-grid">
                      <article className="mw-score-card">
                        <span className="mw-score-label">Coin Score</span>
                        <span className={`mw-score-value ${coinScore === null ? 'neutral' : coinScore >= 66 ? 'positive' : coinScore <= 35 ? 'negative' : 'neutral'}`}>
                          {coinScore === null ? '--' : coinScore}
                        </span>
                        <span className="mw-score-sub">{coinScoreLabel(coinScore)}</span>
                      </article>
                      <article className="mw-action-card">
                        <span className="mw-action-label">Do This Now</span>
                        <p className="mw-action-line">{primaryAction}</p>
                        {socialActionLine ? <p className="mw-action-line mw-action-secondary">{socialActionLine}</p> : null}
                      </article>
                    </div>
                    <div className="mw-score-chips">
                      {/* Only show chips with meaningful data (not 0, not null) */}
                      {change1m !== null && Math.abs(change1m) >= 0.01 && (
                        <div className={`mw-chip ${toneClass(change1m)}`}>
                          <span>1m</span>
                          <strong>{formatPercent(change1m)}</strong>
                        </div>
                      )}
                      {change3m !== null && Math.abs(change3m) >= 0.01 && (
                        <div className={`mw-chip ${toneClass(change3m)}`}>
                          <span>3m</span>
                          <strong>{formatPercent(change3m)}</strong>
                        </div>
                      )}
                      {change1h !== null && Math.abs(change1h) >= 0.01 && (
                        <div className={`mw-chip ${toneClass(change1h)}`}>
                          <span>1h</span>
                          <strong>{formatPercent(change1h)}</strong>
                        </div>
                      )}
                      {volumeChange1h !== null && Math.abs(volumeChange1h) >= 1 && (
                        <div className={`mw-chip ${toneClass(volumeChange1h)}`}>
                          <span>Vol 1h</span>
                          <strong>{formatPercent(volumeChange1h)}</strong>
                        </div>
                      )}
                      {persistenceStreak && (
                        <div className="mw-chip positive">
                          <span>Streak</span>
                          <strong>{persistenceStreak}x</strong>
                        </div>
                      )}
                      <div className={`mw-chip ${structureState === 'Momentum' || structureState === 'Expansion' ? 'positive' : structureState === 'Calm' ? 'neutral' : 'negative'}`}>
                        <span>Structure</span>
                        <strong>{structureState}</strong>
                      </div>
                    </div>
                  </div>

                  <div className="stats-grid">
                    <div className="stat-card primary">
                      <div className="stat-content">
                        <span className="stat-label">Trend Alignment</span>
                        <span className={`stat-value ${alignmentScore > 0 ? 'positive' : alignmentScore < 0 ? 'negative' : 'neutral'}`}>
                          {hasCoinTape ? `${alignmentScore > 0 ? '+' : ''}${alignmentScore}` : '--'}
                        </span>
                        <span className="stat-sublabel">{hasCoinTape ? `${trendLabel(alignmentScore)} (1m/3m/1h)` : 'Awaiting tape'}</span>
                      </div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-content">
                        <span className="stat-label">Breakout State</span>
                        <span className={`stat-value ${breakoutState === 'Breakout Up' ? 'positive' : breakoutState === 'Breakout Down' ? 'negative' : 'neutral'}`}>
                          {hasCoinTape ? breakoutState : '--'}
                        </span>
                        <span className="stat-sublabel">Alerts tracked: {coinAlerts.length}</span>
                      </div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-content">
                        <span className="stat-label">Confidence</span>
                        <span className={`stat-value ${confidencePct !== null && confidencePct >= 65 ? 'positive' : confidencePct !== null && confidencePct <= 35 ? 'negative' : 'neutral'}`}>
                          {confidencePct === null ? '--' : `${confidencePct}%`}
                        </span>
                        <span className="stat-sublabel">{confidencePct === null ? 'Awaiting tape' : 'Alignment + volume + streak'}</span>
                      </div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-content">
                        <span className="stat-label">Last Coin Update</span>
                        <span className="stat-value small">{humanTime(coinInsights?.updatedAt)}</span>
                        <span className="stat-sublabel">Auto-refresh {Math.round(COIN_REFRESH_MS / 1000)}s</span>
                      </div>
                    </div>
                  </div>

                  {coinInsightsLoading && !coinInsights ? (
                    <div className="coin-history-note">Loading coin pressure...</div>
                  ) : null}
                  {coinInsightsError ? (
                    <div className="coin-history-note error mw-fetch-note">Coin insights temporarily unavailable. Showing tape-only signals.</div>
                  ) : null}

                  <div className="info-section">
                    <div className="section-header">
                      <h3>{coinSymbol} Alerts</h3>
                      <p className="section-desc">Signal stream filtered strictly to this coin.</p>
                    </div>
                    {coinAlertsScopeNote ? (
                      <div className={`coin-history-note ${coinAlertsError && !coinAlertsHydrated ? 'error mw-fetch-note' : ''}`}>
                        {coinAlertsScopeNote}
                      </div>
                    ) : null}
                    {!coinAlerts.length ? (
                      <div className="coin-history-note">No coin alerts yet.</div>
                    ) : null}
                    <AlertsTab filterSymbol={coinSymbol} compact />
                  </div>

                  <div className="info-section mw-coin-chart-block">
                    <div className="section-header">
                      <h3>Live Chart · {coinSymbol}</h3>
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
                    <div className="tradingview-widget-container" style={{ height: '360px' }}>
                      <iframe
                        key={`${tvResolved.symbol}-${tvResolved.source}`}
                        src={tvUrl}
                        style={{ width: '100%', height: '100%', border: 'none', borderRadius: '8px' }}
                        title={`${coinSymbol} chart`}
                        sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                        referrerPolicy="no-referrer"
                        loading="lazy"
                      />
                    </div>
                  </div>
                </>
              )}
            </section>
          )}

          {activeTab === 'pulse' && (
            <section className="tab-panel active" role="tabpanel">
              <MarketSignalCard />
            </section>
          )}

          {activeTab === 'intel' && (
            <section className="tab-panel active" role="tabpanel">
              {!coinSymbol ? (
                <div className="tab-empty">Select a coin to load coin-level events and social pulse.</div>
              ) : (
                <>
                  <div className="stats-grid">
                    <div className="stat-card">
                      <div className="stat-content">
                        <span className="stat-label">Intel Status</span>
                        <span className="stat-value neutral">{coinIntel?.status || 'offline'}</span>
                        <span className="stat-sublabel">Updated {humanTime(coinIntel?.ts)}</span>
                      </div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-content">
                        <span className="stat-label">Events Status</span>
                        <span className="stat-value neutral">{coinIntel?.events?.status || 'offline'}</span>
                        <span className="stat-sublabel">{coinIntel?.events?.items?.length || 0} items</span>
                      </div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-content">
                        <span className="stat-label">Social Status</span>
                        <span className="stat-value neutral">{coinIntel?.social?.status || 'offline'}</span>
                        <span className="stat-sublabel">{coinIntel?.social?.items?.length || 0} items</span>
                      </div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-content">
                        <span className="stat-label">CoinPaprika Id</span>
                        <span className="stat-value small">{coinIntel?.coinId || '--'}</span>
                        <span className="stat-sublabel">Cached for {Math.round(INTEL_REFRESH_MS / 1000)}s polling</span>
                      </div>
                    </div>
                  </div>

                  {coinIntelLoading && !coinIntel ? <div className="coin-history-note">Loading coin intel...</div> : null}
                  {coinIntelError ? (
                    <div className="coin-history-note error mw-fetch-note">Intel temporarily unavailable. Showing tape-only signals.</div>
                  ) : null}

                  <div className="info-section">
                    <div className="section-header">
                      <h3>Events</h3>
                      <p className="section-desc">External events feed for {coinSymbol} (best effort, cached).</p>
                    </div>
                    {coinIntel?.events?.items?.length ? (
                      <div className="feed-list">
                        {coinIntel.events.items.slice(0, 5).map((item, idx) => (
                          <div className="news-item" key={`ev-${item.id || idx}`}>
                            <div className="news-item-header">
                              <span className="news-item-source">{humanTime(item.when)}</span>
                              <span className="news-item-time">{item.source_url ? 'Source' : ''}</span>
                            </div>
                            <div className="news-item-title">{item.title || item.name || 'Untitled event'}</div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="tab-empty">No events available right now.</div>
                    )}
                  </div>

                  <div className="info-section">
                    <div className="section-header">
                      <h3>Social Metrics</h3>
                      <p className="section-desc">Coin-level social heat overlay for {coinSymbol}.</p>
                    </div>
                    {hasMeaningfulSocialMetrics ? (
                      <>
                        <div className="mw-score-chips">
                          {!socialIsProxy && socialHeat !== null ? (
                            <div className={`mw-chip ${socialHeatTone}`}>
                              <span>Social Heat</span>
                              <strong>{Math.round(socialHeat)}</strong>
                            </div>
                          ) : null}
                          {socialVolume24h !== null && socialVolume24h > 0 ? (
                            <div className="mw-chip neutral">
                              <span>Audience</span>
                              <strong>{formatCompactNumber(socialVolume24h)}</strong>
                            </div>
                          ) : null}
                          {socialEngagement24h !== null && socialEngagement24h > 0 ? (
                            <div className="mw-chip neutral">
                              <span>24h Engagement</span>
                              <strong>{formatCompactNumber(socialEngagement24h)}</strong>
                            </div>
                          ) : null}
                          {socialPosts60m !== null && socialPosts60m > 0 ? (
                            <div className="mw-chip neutral">
                              <span>Posts 60m</span>
                              <strong>{formatCompactNumber(socialPosts60m)}</strong>
                            </div>
                          ) : null}
                          {socialDominance24h !== null && socialDominance24h > 0 ? (
                            <div className="mw-chip neutral">
                              <span>Dominance</span>
                              <strong>{socialDominance24h.toFixed(2)}%</strong>
                            </div>
                          ) : null}
                          {!socialIsProxy && socialSentimentDisplay ? (
                            <div className={`mw-chip ${socialSentimentTone}`}>
                              <span>Sentiment</span>
                              <strong>{socialSentimentDisplay}</strong>
                            </div>
                          ) : null}
                          {socialRank !== null && socialRank > 0 ? (
                            <div className="mw-chip neutral">
                              <span>Social Rank</span>
                              <strong>#{Math.round(socialRank)}</strong>
                            </div>
                          ) : null}
                          {socialUniqueAuthors24h !== null && socialUniqueAuthors24h > 0 ? (
                            <div className="mw-chip neutral">
                              <span>Authors 24h</span>
                              <strong>{formatCompactNumber(socialUniqueAuthors24h)}</strong>
                            </div>
                          ) : null}
                          {!socialIsProxy && socialHeatTrend ? (
                            <div className={`mw-chip ${socialHeatTrend === 'rising' ? 'positive' : socialHeatTrend === 'collapsing' ? 'negative' : 'neutral'}`}>
                              <span>Heat Trend</span>
                              <strong>{socialHeatTrend === 'rising' ? 'Rising' : socialHeatTrend === 'collapsing' ? 'Collapsing' : 'Flat'}</strong>
                            </div>
                          ) : null}
                          {socialSourceLabel ? (
                            <div className="mw-chip neutral">
                              <span>Source</span>
                              <strong>{socialSourceLabel}</strong>
                            </div>
                          ) : null}
                          {socialUpdatedAt ? (
                            <div className="mw-chip neutral">
                              <span>Updated</span>
                              <strong>{humanTime(socialUpdatedAt)}</strong>
                            </div>
                          ) : null}
                        </div>
                        {socialIsProxy ? (
                          <div className="coin-history-note">Community proxy (not sentiment).</div>
                        ) : null}
                        {socialActionLine ? <div className="coin-history-note mw-intel-action">{socialActionLine}</div> : null}
                      </>
                    ) : (
                      <div className="tab-empty">No social metrics available right now.</div>
                    )}
                  </div>

                  <div className="info-section">
                    <div className="section-header">
                      <h3>Social Pulse</h3>
                      <p className="section-desc">Best-effort social timeline snapshots for {coinSymbol}.</p>
                    </div>
                    {coinIntel?.social?.items?.length ? (
                      <div className="feed-list">
                        {coinIntel.social.items.slice(0, 5).map((item, idx) => (
                          <div className="news-item" key={`so-${item.id || idx}`}>
                            <div className="news-item-header">
                              <span className="news-item-source">{item.author || 'Unknown'}</span>
                              <span className="news-item-time">{humanTime(item.when)}</span>
                            </div>
                            <div className="news-item-title">{item.text || 'No text available'}</div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="tab-empty">No social items available right now.</div>
                    )}
                  </div>
                </>
              )}
            </section>
          )}
        </main>

        <footer className="popup-footer">
          <div className="footer-left">
            <span className="data-source">
              Powered by Coinbase tape data · Coin scope only
            </span>
          </div>
          <div className="footer-right">
            <button
              className={`refresh-btn ${isRefreshing ? 'refreshing' : ''}`}
              onClick={handleRefresh}
              aria-label="Refresh data"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M23 4v6h-6M1 20v-6h6"/>
                <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
              </svg>
              Refresh
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
};

export default SentimentPopupAdvanced;
