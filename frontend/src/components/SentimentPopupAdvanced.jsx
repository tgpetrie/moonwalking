import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { useMarketHeat } from '../hooks/useMarketHeat';
import { useData } from '../context/DataContext';
import { API_ENDPOINTS, fetchData } from '../api';
import { getCoinEvents } from '../utils/coinHistoryCache';
import { getMarketPressure } from '../utils/marketPressure';
import AlertsTab from './AlertsTab';
import '../styles/sentiment-popup-advanced.css';

const REFRESH_MS = 15000;
const COIN_REFRESH_MS = 30000;
const INTEL_REFRESH_MS = 60000;
const TAPE_MIN = 12;

const normalizeTab = (value) => {
  const raw = String(value || '').trim().toLowerCase();
  if (raw === 'alerts' || raw === 'feed' || raw === 'global') return 'coin';
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
  if (n === null) return 'No data yet';
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
    tape: Array.isArray(root.tape)
      ? root.tape
      : Array.isArray(root.coin_tape)
        ? root.coin_tape
        : Array.isArray(root.metrics?.tape)
          ? root.metrics.tape
          : Array.isArray(root.samples)
            ? root.samples
            : [],
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
  if (score === null) return 'Warming up';
  if (score <= 35) return 'Cautious';
  if (score <= 65) return 'Neutral';
  return 'Aggressive';
};

const humanTime = (value) => {
  const tsMs = normalizeTsMs(value);
  if (!Number.isFinite(tsMs)) return 'No update yet';
  return new Date(tsMs).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
};

const formatCompactNumber = (value) => {
  const n = toNumber(value);
  if (n === null) return 'No data yet';
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

const PRIORITY_HALF_LIFE_MS = 165 * 1000;
const PRIORITY_FRESH_MS = 2 * 60 * 1000;
const PRIORITY_FADING_MS = 3.5 * 60 * 1000;
const PRIORITY_SOFT_EXPIRY_MS = 9 * 60 * 1000;

const rawTypeKey = (alert) => String(alert?.type_key || alert?.type || '').toLowerCase();

const clampNumber = (value, min, max) => Math.min(max, Math.max(min, value));

const priorityBucketForAlert = (alert) => {
  const raw = rawTypeKey(alert);
  const pct = Number(alert?.evidence?.pct_1m ?? alert?.evidence?.pct_3m ?? alert?.pct ?? null);

  if (
    raw.includes('divergence') ||
    raw.includes('fakeout') ||
    raw.includes('exhaustion') ||
    raw.includes('liquidity_shock') ||
    raw.includes('stealth')
  ) {
    return 'divergence';
  }

  if (
    raw.includes('dump') ||
    raw.includes('crater') ||
    raw.includes('fear') ||
    raw.includes('persistent_loser') ||
    raw.includes('trend_break_down') ||
    raw.includes('reversal_down') ||
    raw.includes('breadth_failure')
  ) {
    return 'bearish';
  }

  if (
    raw.includes('moonshot') ||
    raw.includes('breakout') ||
    raw.includes('fomo') ||
    raw.includes('persistent_gainer') ||
    raw.includes('trend_break_up') ||
    raw.includes('breadth_thrust') ||
    raw.includes('reversal_up') ||
    raw.includes('squeeze_break')
  ) {
    return 'bullish';
  }

  if (Number.isFinite(pct)) {
    if (pct > 0) return 'bullish';
    if (pct < 0) return 'bearish';
  }
  return null;
};

const priorityFamilyBonus = (alert, bucket) => {
  const raw = rawTypeKey(alert);
  if (bucket === 'divergence') {
    if (raw.includes('divergence')) return 8;
    if (raw.includes('fakeout') || raw.includes('exhaustion')) return 7;
    if (raw.includes('liquidity_shock') || raw.includes('stealth')) return 6;
    return 4;
  }
  if (bucket === 'bullish') {
    if (raw.includes('moonshot') || raw.includes('breakout')) return 8;
    if (raw.includes('trend_break_up') || raw.includes('breadth_thrust')) return 7;
    if (raw.includes('persistent_gainer') || raw.includes('fomo')) return 6;
    return 4;
  }
  if (bucket === 'bearish') {
    if (raw.includes('crater') || raw.includes('dump')) return 8;
    if (raw.includes('trend_break_down') || raw.includes('breadth_failure')) return 7;
    if (raw.includes('persistent_loser') || raw.includes('fear')) return 6;
    return 4;
  }
  return 0;
};

const toEpochMs = (value) => {
  if (value == null || value === '') return null;
  if (typeof value === 'number' && Number.isFinite(value)) {
    if (Math.abs(value) < 1e11) return Math.round(value * 1000);
    if (Math.abs(value) < 1e14) return Math.round(value);
    return Math.round(value / 1000);
  }
  const raw = String(value).trim();
  if (!raw) return null;
  if (/^-?\d+(?:\.\d+)?$/.test(raw)) return toEpochMs(Number(raw));
  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? parsed : null;
};

const pickTsMs = (alert) => {
  const fields = [
    alert?.event_ts_ms,
    alert?.ts_ms,
    alert?.timestamp_ms,
    alert?.event_ts,
    alert?.ts,
    alert?.timestamp,
    alert?.created_at,
    alert?.createdAt,
    alert?.time,
    alert?.when,
  ];
  for (const value of fields) {
    const ts = toEpochMs(value);
    if (Number.isFinite(ts)) return ts;
  }
  return null;
};

const pickPct = (alert) => {
  const ev = alert?.evidence || {};
  const value = ev.pct_1m ?? ev.pct_3m ?? ev.pct_1h ?? alert?.pct ?? alert?.magnitude ?? null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const pickVolPct = (alert) => {
  const ev = alert?.evidence || {};
  const value = ev.volume_change_1h_pct ?? ev.vol_change_1h_pct ?? ev.vol_pct ?? null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const alertSymbolShort = (alert) =>
  String(alert?.symbol || alert?.product_id || '')
    .toUpperCase()
    .replace(/-USD$|-USDT$|-PERP$/i, '');

const buildRankMaps = (rows = []) => {
  const map = new Map();
  rows.forEach((row, idx) => {
    const symbol = String(row?.symbol || row?.product_id || '').toUpperCase().replace(/-USD$|-USDT$|-PERP$/i, '');
    if (!symbol || map.has(symbol)) return;
    const rank = Number(row?.rank ?? idx + 1);
    map.set(symbol, Number.isFinite(rank) ? rank : idx + 1);
  });
  return map;
};

const computeRankPersistenceScore = (entry) => {
  let score = 0;
  if (Number.isFinite(entry.rank1m)) score += clampNumber(12 - entry.rank1m, 0, 10);
  if (Number.isFinite(entry.rank3m)) score += clampNumber(12 - entry.rank3m, 0, 10);
  if (Number.isFinite(entry.rank1m) && Number.isFinite(entry.rank3m)) {
    score += clampNumber(6 - (Math.abs(entry.rank1m - entry.rank3m) * 2), 0, 6);
  }
  return clampNumber(score, 0, 18);
};

const computeRankTrend = (entry) => {
  if (entry.bucket === 'bullish' && Number.isFinite(entry.rank1m) && Number.isFinite(entry.rank3m)) {
    if (entry.rank1m + 1 < entry.rank3m) return 'rising';
    if (Math.abs(entry.rank1m - entry.rank3m) <= 1) return 'flat-strong';
    return 'slipping';
  }
  if (entry.bucket === 'bearish') {
    if (entry.noConfirmMs >= PRIORITY_FADING_MS) return 'slipping';
    if (Number.isFinite(entry.rank3m) && entry.rank3m <= 3) return 'flat-strong';
    return 'rising';
  }
  return entry.noConfirmMs >= PRIORITY_FADING_MS ? 'slipping' : 'mixed';
};

const buildRankSummary = (entry) => {
  if (Number.isFinite(entry.rank1m) && Number.isFinite(entry.rank3m)) {
    const lo = Math.min(entry.rank1m, entry.rank3m);
    const hi = Math.max(entry.rank1m, entry.rank3m);
    return `rank held ${lo}-${hi}`;
  }
  if (Number.isFinite(entry.rank1m)) return `1m rank ${entry.rank1m}`;
  if (Number.isFinite(entry.rank3m)) return `${entry.bucket === 'bearish' ? '3m loss' : '3m'} rank ${entry.rank3m}`;
  return '';
};

const priorityContributionScore = (alert, nowMs) => {
  const tsMs = pickTsMs(alert);
  if (!Number.isFinite(tsMs)) return null;
  const ageMs = Math.max(0, nowMs - tsMs);
  if (ageMs > PRIORITY_SOFT_EXPIRY_MS) return null;

  const severity = String(alert?.severity || 'info').toLowerCase();
  const severityWeight = ({ critical: 24, high: 18, medium: 12, low: 6, info: 3 }[severity] || 3);
  const pct = Math.abs(pickPct(alert) ?? 0);
  const volPct = Math.abs(pickVolPct(alert) ?? 0);
  const streak = Math.max(0, Number(alert?.evidence?.streak ?? alert?.extra?.streak ?? 0) || 0);
  const familyBonus = priorityFamilyBonus(alert, priorityBucketForAlert(alert));

  const baseScore =
    severityWeight +
    clampNumber(pct * 5, 0, 18) +
    clampNumber(volPct / 5, 0, 14) +
    clampNumber(streak, 0, 4) * 4 +
    familyBonus;

  const decay = Math.exp(-ageMs / PRIORITY_HALF_LIFE_MS);
  return {
    ageMs,
    tsMs,
    weighted: baseScore * decay,
    isFresh: ageMs <= PRIORITY_FRESH_MS,
    streak,
  };
};

const priorityStateForEntry = (entry) => {
  if (entry.reversalRiskScore >= 14 || entry.bucket === 'divergence') return 'Reversal Risk';
  if (entry.noConfirmMs >= PRIORITY_FADING_MS || entry.score < 40) return 'Fading';
  if (entry.score >= 85 && entry.freshConfirms >= 1 && entry.volumeAligned && !entry.divergenceFlag) return 'Dominant';
  if (entry.score >= 70 && entry.rankPersistenceScore >= 10) return 'Persistent';
  if (entry.score >= 55) return 'Building';
  return 'Fragile';
};

const priorityStateTone = (label, bucket) => {
  if (label === 'Reversal Risk' || label === 'Fading') return 'divergence';
  if (bucket === 'bullish') return 'bullish';
  if (bucket === 'bearish') return 'bearish';
  return 'divergence';
};

const ageLabel = (ms) => {
  if (!Number.isFinite(ms) || ms < 0) return 'n/a';
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  return `${h}h`;
};

const deriveTapeState = (items, marketPressure) => {
  const activeLeaders = items.filter((item) => item.score >= 55).length;
  const weakening = items.filter((item) => ['Fading', 'Reversal Risk'].includes(item.stateLabel)).length;
  const freshConfirms = items.reduce((sum, item) => sum + item.freshConfirms, 0);
  const breadth = Number(marketPressure?.components?.breadth ?? 0);

  let tapeState = 'Choppy';
  if (weakening >= 2 && activeLeaders <= 1) tapeState = 'Reversing';
  else if (activeLeaders >= 3 && freshConfirms >= 3 && breadth >= 0.56) tapeState = 'Expanding';
  else if (activeLeaders <= 2 && items.some((item) => item.score >= 70)) tapeState = 'Concentrated';
  else if (weakening >= 1 && freshConfirms < 2) tapeState = 'Cooling';

  return { tapeState, freshConfirms, activeLeaders, weakening };
};

const priorityReasons = (entry, nowMs) => {
  const reasons = [];
  if (entry.confirms > 1) reasons.push(`${entry.confirms} confirms`);
  if (entry.rankSummary) reasons.push(entry.rankSummary);
  if (entry.volumeAligned) reasons.push('volume aligned');
  if (entry.breadthSupport >= 0.62) reasons.push('breadth aligned');
  else if (entry.rankTrend === 'slipping') reasons.push('rank slipping');
  else if (entry.noConfirmMs >= PRIORITY_FADING_MS) reasons.push(`no reconfirm in ${(entry.noConfirmMs / 60000).toFixed(1)}m`);
  else reasons.push(`fresh ${ageLabel(Math.max(0, nowMs - entry.lastTsMs))} ago`);
  return reasons.slice(0, 3);
};

const buildPriorityItems = ({ alerts = [], gainers1m = [], gainers3m = [], losers3m = [], marketPressure = null, nowMs }) => {
  const boardRanks = {
    oneMin: buildRankMaps(gainers1m),
    gain3m: buildRankMaps(gainers3m),
    loss3m: buildRankMaps(losers3m),
  };

  const grouped = new Map();
  for (const alert of alerts) {
    const symbol = alertSymbolShort(alert);
    const bucket = priorityBucketForAlert(alert);
    if (!symbol || !bucket) continue;

    const contribution = priorityContributionScore(alert, nowMs);
    if (!contribution) continue;

    const key = `${bucket}:${symbol}`;
    const existing = grouped.get(key) || {
      bucket,
      symbol,
      scoreRaw: 0,
      confirms: 0,
      freshConfirms: 0,
      lastTsMs: 0,
      maxStreak: 0,
      topVolPct: 0,
      topVolSign: 1,
      rank1m: null,
      rank3m: null,
      breadthSupport: 0,
      divergenceFlag: bucket === 'divergence',
    };

    existing.scoreRaw += contribution.weighted;
    existing.confirms += 1;
    if (contribution.isFresh) existing.freshConfirms += 1;
    if (contribution.tsMs > existing.lastTsMs) existing.lastTsMs = contribution.tsMs;
    if (contribution.streak > existing.maxStreak) existing.maxStreak = contribution.streak;

    const volSigned = pickVolPct(alert);
    if (Number.isFinite(volSigned) && Math.abs(volSigned) >= existing.topVolPct) {
      existing.topVolPct = Math.abs(volSigned);
      existing.topVolSign = volSigned >= 0 ? 1 : -1;
    }

    const oneMinBoard = boardRanks.oneMin.get(symbol);
    const gain3Board = boardRanks.gain3m.get(symbol);
    const loss3Board = boardRanks.loss3m.get(symbol);
    if (Number.isFinite(oneMinBoard)) existing.rank1m = oneMinBoard;
    if (bucket === 'bearish') {
      if (Number.isFinite(loss3Board)) existing.rank3m = loss3Board;
    } else if (Number.isFinite(gain3Board)) {
      existing.rank3m = gain3Board;
    }

    const ev = alert?.evidence || {};
    const breadthUp = Number(ev.breadth_up ?? marketPressure?.breadth_up ?? marketPressure?.components?.breadth ?? 0) || 0;
    const breadthDown = Number(ev.breadth_down ?? marketPressure?.breadth_down ?? 0) || 0;
    const breadthSupport =
      bucket === 'bullish' ? breadthUp :
      bucket === 'bearish' ? breadthDown :
      Math.max(Math.abs(breadthUp - breadthDown), marketPressure?.components?.breadth ?? 0);
    existing.breadthSupport = Math.max(existing.breadthSupport, clampNumber(breadthSupport, 0, 1));

    grouped.set(key, existing);
  }

  const ranked = Array.from(grouped.values()).map((entry) => {
    const confirmationBonus = Math.min(18, Math.max(0, entry.confirms - 1) * 6);
    const freshBonus = entry.freshConfirms > 0 ? Math.min(10, entry.freshConfirms * 4) : 0;
    entry.noConfirmMs = Math.max(0, nowMs - entry.lastTsMs);
    entry.rankPersistenceScore = computeRankPersistenceScore(entry);
    entry.rankTrend = computeRankTrend(entry);
    entry.rankSummary = buildRankSummary(entry);
    entry.volumeAligned = entry.topVolSign > 0 && entry.topVolPct >= 10;
    entry.reversalRiskScore =
      (entry.bucket === 'divergence' ? 10 : 0) +
      (entry.rankTrend === 'slipping' ? 4 : 0) +
      (entry.noConfirmMs >= PRIORITY_FADING_MS ? 4 : 0);
    const stalePenalty = entry.noConfirmMs > PRIORITY_FADING_MS ? 12 : 0;
    const volumeBonus = entry.volumeAligned ? 10 : 0;
    const breadthBonus = Math.round(entry.breadthSupport * 10);
    const score = clampNumber(
      Math.round(entry.scoreRaw + confirmationBonus + freshBonus + entry.rankPersistenceScore + volumeBonus + breadthBonus - stalePenalty),
      1,
      99
    );
    const stateLabel = priorityStateForEntry({ ...entry, score });
    return { ...entry, score, stateLabel };
  });

  const ordered = ['Dominant', 'Persistent', 'Building', 'Reversal Risk', 'Fading']
    .flatMap((label) =>
      ranked
        .filter((item) => item.stateLabel === label)
        .sort((a, b) => b.score - a.score || b.lastTsMs - a.lastTsMs)
    );

  const deduped = [];
  const seenSymbols = new Set();
  for (const item of ordered) {
    if (seenSymbols.has(item.symbol)) continue;
    seenSymbols.add(item.symbol);
    deduped.push(item);
  }
  return deduped;
};

const horizonTone = (value) => {
  const n = toNumber(value);
  if (n === null) return 'neutral';
  if (n > 0) return 'positive';
  if (n < 0) return 'negative';
  return 'neutral';
};

const horizonWord = (value, label) => {
  const n = toNumber(value);
  if (n === null) return `${label} quiet`;
  if (n > 0) return `${label} up`;
  if (n < 0) return `${label} down`;
  return `${label} flat`;
};

const CoinPressurePriorityStrip = ({ items = [], marketPressure = null, nowMs, activeSymbol = null }) => {
  const summary = deriveTapeState(items, marketPressure);

  return (
    <section className="cp-strip" aria-label="Strongest right now">
      <div className="cp-strip__hero">
        <div>
          <div className="cp-strip__eyebrow">Strongest Right Now</div>
          <h2 className="cp-strip__title">
            {items.length ? `${summary.tapeState} tape` : 'No dominant live setup'}
          </h2>
          <p className="cp-strip__sub">
            {items.length
              ? `7m horizon. Fresh within 2m, fading after 3.5m silence, soft expiry at 9m.`
              : 'Tape is live, but conviction is still forming inside the 7m window.'}
          </p>
        </div>
        <div className="cp-strip__model">7m decayed model</div>
      </div>

      <div className="cp-strip__rail">
        <span className="cp-strip__rail-chip">Tape State: {summary.tapeState}</span>
        <span className="cp-strip__rail-chip">Fresh: {summary.freshConfirms}</span>
        <span className="cp-strip__rail-chip">Leaders: {summary.activeLeaders}</span>
        <span className="cp-strip__rail-chip">Weakening: {summary.weakening}</span>
      </div>

      {items.length ? (
        <div className="cp-strip__rows">
          {items.slice(0, 3).map((item) => (
            <button
              key={`${item.bucket}:${item.symbol}`}
              type="button"
              className={`cp-strip__row ${activeSymbol === item.symbol ? 'is-active' : ''}`}
              data-tone={priorityStateTone(item.stateLabel, item.bucket)}
              onClick={() => {
                if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
                  window.dispatchEvent(new CustomEvent('openInfo', { detail: item.symbol }));
                }
              }}
            >
              <div className="cp-strip__row-top">
                <div className="cp-strip__row-title">
                  <span>{item.symbol}</span>
                  <span className="cp-strip__row-sep">·</span>
                  <span>{item.stateLabel}</span>
                </div>
                <div className="cp-strip__row-score">{item.score}</div>
              </div>
              <div className="cp-strip__row-body">{priorityReasons(item, nowMs).join(' · ')}</div>
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
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
  const {
    activeAlerts = [],
    alertsRecent = [],
    connectionStatus = 'STALE',
    staleSeconds = null,
    lastFetchTs = null,
    market_pressure = null,
    gainers_1m = [],
    gainers_3m = [],
    losers_3m = [],
  } = useData() || {};

  const [activeTab, setActiveTab] = useState(normalizeTab(defaultTab));
  const [chartExchange, setChartExchange] = useState('auto');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const [coinInsights, setCoinInsights] = useState(null);
  const [coinInsightsLoading, setCoinInsightsLoading] = useState(false);
  const [coinInsightsError, setCoinInsightsError] = useState(null);

  const [coinIntel, setCoinIntel] = useState(null);
  const [coinIntelLoading, setCoinIntelLoading] = useState(false);
  const [coinIntelError, setCoinIntelError] = useState(null);

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

  const cachedCoinHistory = useMemo(() => {
    if (!coinSymbol) return [];
    const cached = getCoinEvents(coinSymbol);
    return [...cached].sort((a, b) => alertTsMs(b) - alertTsMs(a));
  }, [coinSymbol, activeAlerts, alertsRecent]);

  const coinAlerts = useMemo(() => {
    if (!coinSymbol) return [];
    if (fallbackCoinAlerts.length) return fallbackCoinAlerts;
    return cachedCoinHistory;
  }, [coinSymbol, fallbackCoinAlerts, cachedCoinHistory]);

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
  const tape = Array.isArray(coinInsights?.tape) ? coinInsights.tape : [];
  const tapeCount = Math.max(
    tape.length,
    coinAlerts.length,
    [change1m, change3m, change1h, volumeChange1h].filter((v) => v !== null).length * 3
  );
  const lastCoinUpdateTs = coinInsights?.updatedAt || coinAlerts[0]?.event_ts_ms || coinAlerts[0]?.ts_ms || coinAlerts[0]?.event_ts || coinAlerts[0]?.ts || null;
  const hasLastCoinUpdate = Number.isFinite(normalizeTsMs(lastCoinUpdateTs));
  const metricsReady = tapeCount >= TAPE_MIN && Number.isFinite(normalizeTsMs(lastCoinUpdateTs));
  const alignmentScore = trendScore(change1m, change3m, change1h);
  const hasCoinTape = metricsReady;

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
    if (socialSource === 'coingecko') return 'CoinGecko';
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

  const dataStaleAgeSeconds = useMemo(() => {
    if (Number.isFinite(staleSeconds)) return Math.max(0, Number(staleSeconds));
    if (staleSeconds && typeof staleSeconds === 'object') {
      const nums = Object.values(staleSeconds)
        .map((v) => Number(v))
        .filter((v) => Number.isFinite(v));
      if (nums.length) return Math.max(...nums);
    }
    if (Number.isFinite(lastFetchTs)) {
      return Math.max(0, Math.round((Date.now() - Number(lastFetchTs)) / 1000));
    }
    return null;
  }, [staleSeconds, lastFetchTs]);

  const dataLinkState = useMemo(() => {
    const status = String(connectionStatus || '').toUpperCase();
    if (status === 'LIVE') {
      return { tone: 'live', text: 'DATA: CONNECTED' };
    }
    if (status === 'DOWN') {
      return { tone: 'offline', text: 'DATA: DOWN' };
    }
    if (Number.isFinite(dataStaleAgeSeconds)) {
      return { tone: 'stale', text: `DATA: STALE (${Math.round(dataStaleAgeSeconds)}s)` };
    }
    return { tone: 'stale', text: 'DATA: STALE' };
  }, [connectionStatus, dataStaleAgeSeconds]);

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
  const coinPanelNeedsWarmup = activeTab === 'coin' && coinSymbol && !metricsReady;
  const liveLabelRaw = coinPanelNeedsWarmup ? (coinInsightsLoading ? 'BOOTING' : 'WARMING') : String(pipelineStatus || 'STALE').toUpperCase();
  const liveClass = liveLabelRaw === 'LIVE' ? 'live' : liveLabelRaw === 'OFFLINE' ? 'offline' : 'stale';
  const nowMs = Date.now();
  const marketPressureSummary = useMemo(
    () => getMarketPressure({ market_pressure }),
    [market_pressure]
  );

  const priorityEntries = useMemo(
    () =>
      buildPriorityItems({
        alerts: fallbackAllAlerts,
        gainers1m: gainers_1m,
        gainers3m: gainers_3m,
        losers3m: losers_3m,
        marketPressure: marketPressureSummary,
        nowMs,
      }),
    [fallbackAllAlerts, gainers_1m, gainers_3m, losers_3m, marketPressureSummary, nowMs]
  );

  const coinPriorityEntry = useMemo(
    () => priorityEntries.find((entry) => entry.symbol === coinSymbol) || null,
    [priorityEntries, coinSymbol]
  );
  const coinEvidenceEmptyCopy = useMemo(() => {
    if (!coinSymbol) return 'No live coin signal right now.';
    if (!fallbackCoinAlerts.length && cachedCoinHistory.length) {
      return `No live coin signal right now. Showing cached ${coinSymbol} history while live tape rebuilds.`;
    }
    if (coinPriorityEntry?.rankSummary) {
      return `No live coin signal right now. ${coinSymbol} is still holding ${coinPriorityEntry.rankSummary}.`;
    }
    const last = hasLastCoinUpdate ? ` Last tape ${humanTime(lastCoinUpdateTs)}.` : '';
    return `No live coin signal right now for ${coinSymbol}.${last}`;
  }, [
    coinSymbol,
    fallbackCoinAlerts.length,
    cachedCoinHistory.length,
    coinPriorityEntry,
    hasLastCoinUpdate,
    lastCoinUpdateTs,
  ]);

  const alignmentLabel = useMemo(() => {
    if (change1m === null && change3m === null && change1h === null) return 'Warming';
    const parts = [change1m, change3m, change1h].filter((v) => v !== null);
    const allUp = parts.length > 0 && parts.every((v) => v > 0);
    const allDown = parts.length > 0 && parts.every((v) => v < 0);
    if (allUp) return 'Aligned Up';
    if (allDown) return 'Aligned Down';
    return 'Mixed';
  }, [change1m, change3m, change1h]);

  const alignmentDetail = useMemo(
    () => [horizonWord(change1m, '1m'), horizonWord(change3m, '3m'), horizonWord(change1h, '1h')].join(' · '),
    [change1m, change3m, change1h]
  );

  const setupQuality = useMemo(() => {
    if (confidencePct === null) return { label: 'Forming', detail: 'Need more tape to score setup quality.', tone: 'neutral' };
    if (confidencePct >= 75) return { label: 'Strong', detail: 'Driven by confirmation, persistence, and volume support.', tone: 'positive' };
    if (confidencePct >= 55) return { label: 'Mixed', detail: 'Some confirmation is present, but conviction is not clean yet.', tone: 'neutral' };
    return { label: 'Fragile', detail: 'Mixed alignment or weak confirmation reduces trust.', tone: 'negative' };
  }, [confidencePct]);

  const freshAgeMs = useMemo(() => {
    const ts = coinPriorityEntry?.lastTsMs ?? normalizeTsMs(lastCoinUpdateTs);
    return Number.isFinite(ts) ? Math.max(0, nowMs - ts) : null;
  }, [coinPriorityEntry, lastCoinUpdateTs, nowMs]);

  const coinHero = useMemo(() => {
    if (!coinSymbol) {
      return {
        eyebrow: 'Coin State',
        state: 'No coin selected',
        sub: 'Pick a coin from the board to load local state.',
        tone: 'neutral',
      };
    }
    if (!metricsReady) {
      return {
        eyebrow: `${coinSymbol} Right Now`,
        state: 'Warming',
        sub: 'Advanced insights warming up. Waiting for enough tape to trust the local read.',
        tone: 'neutral',
      };
    }
    if (coinPriorityEntry?.stateLabel === 'Dominant' || (breakoutState === 'Breakout Up' && alignmentScore >= 3 && volumeConfirms)) {
      return {
        eyebrow: `${coinSymbol} Right Now`,
        state: 'Dominant',
        sub: freshAgeMs !== null && freshAgeMs <= PRIORITY_FRESH_MS
          ? `Fresh 3m confirmation ${ageLabel(freshAgeMs)} ago. Alignment and participation are supporting the move.`
          : 'Strength is still holding, but the next reconfirm matters.',
        tone: 'positive',
      };
    }
    if (coinPriorityEntry?.stateLabel === 'Building' || signalFlags.hasMomentum || (change3m !== null && change3m > 0)) {
      return {
        eyebrow: `${coinSymbol} Right Now`,
        state: 'Building',
        sub: volumeConfirms
          ? 'Early upside pressure is present and volume is confirming it, but the setup is not fully settled yet.'
          : 'Early upside pressure is present, but confirmation and participation are still uneven.',
        tone: 'positive',
      };
    }
    if (coinPriorityEntry?.stateLabel === 'Reversal Risk' || signalFlags.hasFakeout || signalFlags.hasReversal || signalFlags.hasExhaustion) {
      return {
        eyebrow: `${coinSymbol} Right Now`,
        state: 'Fragile',
        sub: 'Structure is unstable. Recent strength looks vulnerable until the coin reclaims and reconfirms.',
        tone: 'negative',
      };
    }
    if (coinPriorityEntry?.stateLabel === 'Fading' || breakoutState === 'Breakout Down' || (change3m !== null && change3m < 0 && alignmentScore <= -2)) {
      return {
        eyebrow: `${coinSymbol} Right Now`,
        state: 'Fading',
        sub: freshAgeMs !== null && freshAgeMs > PRIORITY_FADING_MS
          ? `No reconfirm in ${(freshAgeMs / 60000).toFixed(1)}m. Support is thinning and follow-through is fading.`
          : 'Pressure is slipping and follow-through is weakening.',
        tone: 'negative',
      };
    }
    if (!signalFlags.hasFakeout && !signalFlags.hasMomentum && !signalFlags.hasReversal && metricsReady) {
      return {
        eyebrow: `${coinSymbol} Right Now`,
        state: 'Range-hold',
        sub: 'The coin is rotating inside range. Direction is mixed and there is no clean breakout edge yet.',
        tone: 'neutral',
      };
    }
    return {
      eyebrow: `${coinSymbol} Right Now`,
      state: 'Mixed',
      sub: 'Tape is active, but direction and conviction are still mixed. No clean edge yet.',
      tone: 'neutral',
    };
  }, [coinSymbol, metricsReady, coinPriorityEntry, breakoutState, alignmentScore, volumeConfirms, freshAgeMs, signalFlags, change3m]);

  const actionBias = useMemo(() => {
    if (!metricsReady) return { label: 'Wait', detail: 'Need more tape before trusting a local read.', tone: 'neutral' };
    if (coinHero.state === 'Dominant') return { label: 'Press strength', detail: 'Momentum is confirmed. Favor pullbacks over chasing extension.', tone: 'positive' };
    if (coinHero.state === 'Building') return { label: 'Only act on reconfirm', detail: 'Setup is constructive, but you want another fresh push inside the 7m window.', tone: 'neutral' };
    if (coinHero.state === 'Fragile') return { label: 'Stand aside', detail: 'This setup can break either way. Wait for reclaim or cleaner failure.', tone: 'negative' };
    if (coinHero.state === 'Fading') return { label: 'Watch for reclaim', detail: 'Do not press weakness blindly. Require a reclaim before re-engaging.', tone: 'negative' };
    if (coinHero.state === 'Range-hold' || coinHero.state === 'Mixed') return { label: 'Stand aside', detail: 'Tape is mixed. Wait for a reclaim, breakdown, or fresh reconfirm.', tone: 'neutral' };
    return { label: 'Wait', detail: 'Nothing here deserves urgency yet.', tone: 'neutral' };
  }, [metricsReady, coinHero]);

  const coinBadges = useMemo(() => {
    const badges = [];
    if (breakoutState === 'Breakout Up') badges.push({ label: 'BREAKOUT ACTIVE', tone: 'positive' });
    if (signalFlags.hasFakeout) badges.push({ label: 'FAILED BREAKOUT', tone: 'negative' });
    if (!signalFlags.hasFakeout && !signalFlags.hasMomentum && !signalFlags.hasReversal && metricsReady) badges.push({ label: 'RANGE-HOLD', tone: 'neutral' });
    if (volumeConfirms) badges.push({ label: 'VOLUME CONFIRMED', tone: 'positive' });
    if ((marketPressureSummary?.breadth_up ?? 0) < 0.45) badges.push({ label: 'BREADTH WEAK', tone: 'negative' });
    if (coinPriorityEntry?.stateLabel === 'Reversal Risk' || signalFlags.hasReversal || signalFlags.hasExhaustion) badges.push({ label: 'REVERSAL RISK', tone: 'negative' });
    return badges;
  }, [breakoutState, signalFlags, metricsReady, volumeConfirms, marketPressureSummary, coinPriorityEntry]);

  const pulseWhy = useMemo(() => {
    const reasons = [];
    if (coinPriorityEntry?.freshConfirms) reasons.push(`${coinPriorityEntry.freshConfirms} fresh confirms inside 2m`);
    if (volumeConfirms) reasons.push('volume is confirming the move');
    if (alignmentLabel !== 'Warming') reasons.push(`alignment is ${alignmentLabel.toLowerCase()}`);
    if (coinPriorityEntry?.rankSummary) reasons.push(coinPriorityEntry.rankSummary);
    if (!reasons.length) reasons.push('local tape is still building a reliable read');
    return reasons.slice(0, 4);
  }, [coinPriorityEntry, volumeConfirms, alignmentLabel]);

  const pulseRisks = useMemo(() => {
    const risks = [];
    if (freshAgeMs !== null && freshAgeMs > PRIORITY_FADING_MS) risks.push(`fading after ${(freshAgeMs / 60000).toFixed(1)}m without reconfirm`);
    if (!volumeConfirms && metricsReady) risks.push('volume support is missing');
    if (alignmentLabel === 'Mixed') risks.push('timeframes are mixed');
    if ((marketPressureSummary?.breadth_up ?? 0) < 0.45) risks.push('broad tape support is weak');
    if (signalFlags.hasFakeout) risks.push('recent fakeout risk is still active');
    if (!risks.length) risks.push('invalidates if the next push fails to hold top cohort rank');
    return risks.slice(0, 4);
  }, [freshAgeMs, volumeConfirms, metricsReady, alignmentLabel, marketPressureSummary, signalFlags]);

  const intelHero = useMemo(() => {
    const hasEvents = Boolean(coinIntel?.events?.items?.length);
    const hasSocial = hasMeaningfulSocialMetrics || Boolean(coinIntel?.social?.items?.length);
    if (coinIntelError) {
      return { label: 'Mixed context', detail: 'External feeds are degraded, so this read is tape-led for now.', tone: 'neutral' };
    }
    if (hasEvents && hasSocial) {
      return { label: 'Catalyst present', detail: 'External context and attention are both active around this coin.', tone: 'positive' };
    }
    if (hasEvents) {
      return { label: 'Catalyst present', detail: 'There is event context beyond the tape. Check whether the move is confirming it.', tone: 'positive' };
    }
    if (socialActionLine || (socialHeatTrend === 'rising' && !socialIsProxy)) {
      return { label: 'Social attention rising', detail: 'Attention is building, but the tape still decides whether it matters.', tone: 'neutral' };
    }
    if (hasSocial) {
      return { label: 'Mixed context', detail: 'External attention exists, but the driver is still unclear.', tone: 'neutral' };
    }
    return { label: 'Tape-led', detail: 'No meaningful external driver detected. Treat this as a tape-first move.', tone: 'neutral' };
  }, [coinIntel, hasMeaningfulSocialMetrics, coinIntelError, socialActionLine, socialHeatTrend, socialIsProxy]);

  const intelSupport = useMemo(() => ([
    { label: 'Attention', value: socialHeatTrend ? (socialHeatTrend === 'rising' ? 'Rising' : socialHeatTrend === 'collapsing' ? 'Fading' : 'Flat') : 'Quiet', tone: socialHeatTrend === 'rising' ? 'positive' : socialHeatTrend === 'collapsing' ? 'negative' : 'neutral' },
    { label: 'Source mix', value: socialSourceLabel || (coinIntel?.events?.items?.length ? 'Events only' : 'Tape only'), tone: 'neutral' },
    { label: 'Trust level', value: coinIntelError ? 'Low' : coinIntel?.status === 'live' ? 'High' : 'Medium', tone: coinIntelError ? 'negative' : coinIntel?.status === 'live' ? 'positive' : 'neutral' },
    { label: 'Last external update', value: humanTime(socialUpdatedAt || coinIntel?.ts), tone: 'neutral' },
  ]), [socialHeatTrend, socialSourceLabel, coinIntel, coinIntelError, socialUpdatedAt]);

  const handleOverlayClick = (event) => {
    if (event.target.classList.contains('sentiment-overlay')) onClose();
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await Promise.all([
      refresh({ freshLatest: true }),
      loadCoinInsights({ silent: false }),
      loadCoinIntel({ silent: false }),
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
              <p className="subtitle">Coin-scoped state, tape, and context.</p>
            </div>
          </div>

          <div className="header-right">
            <div className={`live-indicator ${liveClass}`}>
              <span className={`pulse ${liveClass}`} aria-hidden="true" />
              <span className="live-text">{liveLabelRaw}</span>
            </div>
            <div className={`data-link-state ${dataLinkState.tone}`}>{dataLinkState.text}</div>
            <button className="close-btn" onClick={onClose} aria-label="Close popup">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>
        </header>

        <nav className="tab-nav" role="tablist">
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

          {activeTab === 'coin' && (
            <section className="tab-panel active" role="tabpanel">
              {!coinSymbol ? (
                <div className="tab-empty">Choose a coin from the board to load its local state.</div>
              ) : (
                <>
                  <section className="cp-section cp-section--hero">
                    <div className={`cp-hero cp-hero--coin cp-hero--${coinHero.tone}`}>
                      <div className="cp-hero__eyebrow">{coinHero.eyebrow}</div>
                      <div className="cp-hero__title">{coinHero.state}</div>
                      <div className="cp-hero__sub">{coinHero.sub}</div>
                    </div>
                  </section>

                  {!metricsReady ? (
                    <div className="bh-coin-warmup">
                      <div className="bh-coin-warmup__title">Warming up</div>
                      <div className="bh-coin-warmup__sub">Collecting enough tape to trust the local state.</div>
                      <div className="bh-coin-warmup__meta">
                        Tape samples: {tapeCount}/{TAPE_MIN}{hasLastCoinUpdate ? ` · Last update ${humanTime(lastCoinUpdateTs)}` : ''}
                      </div>
                    </div>
                  ) : null}

                  <section className="cp-section">
                    <div className="cp-support-grid">
                      <article className="cp-support-card">
                        <span className="cp-support-card__label">Alignment</span>
                        <strong className={`cp-support-card__value ${alignmentLabel === 'Aligned Up' ? 'positive' : alignmentLabel === 'Aligned Down' ? 'negative' : 'neutral'}`}>{alignmentLabel}</strong>
                        <span className="cp-support-card__sub">{alignmentDetail}</span>
                      </article>
                      <article className="cp-support-card">
                        <span className="cp-support-card__label">Setup Quality</span>
                        <strong className={`cp-support-card__value ${setupQuality.tone}`}>{setupQuality.label}</strong>
                        <span className="cp-support-card__sub">{setupQuality.detail}</span>
                      </article>
                      <article className="cp-support-card">
                        <span className="cp-support-card__label">Persistence</span>
                        <strong className="cp-support-card__value neutral">{persistenceStreak ? `${persistenceStreak}x` : 'Quiet'}</strong>
                        <span className="cp-support-card__sub">{coinPriorityEntry?.rankSummary || 'Rank hold not established yet.'}</span>
                      </article>
                      <article className="cp-support-card">
                        <span className="cp-support-card__label">Last update</span>
                        <strong className="cp-support-card__value neutral">{humanTime(lastCoinUpdateTs)}</strong>
                        <span className="cp-support-card__sub">{freshAgeMs !== null ? `fresh within ${ageLabel(freshAgeMs)}` : 'waiting for next tape sample'}</span>
                      </article>
                    </div>
                  </section>

                  {coinBadges.length ? (
                    <section className="cp-section">
                      <div className="cp-badge-rail">
                        {coinBadges.map((badge) => (
                          <span key={badge.label} className={`cp-badge cp-badge--${badge.tone}`}>{badge.label}</span>
                        ))}
                      </div>
                    </section>
                  ) : null}

                  {coinInsightsLoading && !coinInsights ? (
                    <div className="coin-history-note">Advanced insights warming up. Tape-only signals will fill in first.</div>
                  ) : null}
                  {coinInsightsError ? (
                    <div className="coin-history-note error mw-fetch-note">Advanced insights are still building. Showing live tape signals and chart in the meantime.</div>
                  ) : null}

                  <section className="cp-section">
                    <div className="section-header">
                      <h3>Tape Signals</h3>
                      <p className="section-desc">Coin-specific signals only. Market-wide leaders stay in the global alerts panel.</p>
                    </div>
                    <AlertsTab
                      filterSymbol={coinSymbol}
                      compact
                      hideHeader
                      hideFoot
                      emptyCopy={coinEvidenceEmptyCopy}
                    />
                  </section>

                  <div className="info-section mw-coin-chart-block">
                    <div className="section-header">
                      <h3>Chart</h3>
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

                  <div className="cp-meta-footer">
                    <span>Feed {liveLabelRaw}</span>
                    <span>Last update {humanTime(lastCoinUpdateTs)}</span>
                    <span>Scope coin-only</span>
                    <span>Chart {tvResolved.source}</span>
                  </div>
                </>
              )}
            </section>
          )}

          {activeTab === 'pulse' && (
            <section className="tab-panel active" role="tabpanel">
              {!coinSymbol ? (
                <div className="tab-empty">Choose a coin from the board to load its tactical read.</div>
              ) : (
                <>
                  <section className="cp-section cp-section--hero">
                    <div className={`cp-hero cp-hero--${actionBias.tone}`}>
                      <div className="cp-hero__eyebrow">Action Bias</div>
                      <div className="cp-hero__title">{actionBias.label}</div>
                      <div className="cp-hero__sub">{actionBias.detail}</div>
                    </div>
                  </section>

                  <section className="cp-section">
                    <div className="cp-support-grid">
                      <article className="cp-support-card">
                        <span className="cp-support-card__label">Setup quality</span>
                        <strong className={`cp-support-card__value ${setupQuality.tone}`}>{setupQuality.label}</strong>
                        <span className="cp-support-card__sub">{setupQuality.detail}</span>
                      </article>
                      <article className="cp-support-card">
                        <span className="cp-support-card__label">Persistence</span>
                        <strong className="cp-support-card__value neutral">{coinPriorityEntry?.stateLabel || 'Forming'}</strong>
                        <span className="cp-support-card__sub">{coinPriorityEntry?.rankSummary || 'No stable rank hold yet.'}</span>
                      </article>
                      <article className="cp-support-card">
                        <span className="cp-support-card__label">Market breadth</span>
                        <strong className={`cp-support-card__value ${((marketPressureSummary?.breadth_up ?? 0) >= 0.56) ? 'positive' : ((marketPressureSummary?.breadth_up ?? 0) <= 0.44) ? 'negative' : 'neutral'}`}>
                          {((marketPressureSummary?.breadth_up ?? 0) >= 0.56) ? 'Supportive' : ((marketPressureSummary?.breadth_up ?? 0) <= 0.44) ? 'Hostile' : 'Mixed'}
                        </strong>
                        <span className="cp-support-card__sub">Secondary market-wide context. {marketPressureSummary?.label || 'No broad tape label yet.'}</span>
                      </article>
                      <article className="cp-support-card">
                        <span className="cp-support-card__label">Reconfirm timer</span>
                        <strong className="cp-support-card__value neutral">
                          {freshAgeMs === null ? 'n/a' : freshAgeMs <= PRIORITY_FRESH_MS ? `fresh ${ageLabel(freshAgeMs)}` : `no reconfirm ${ageLabel(freshAgeMs)}`}
                        </strong>
                        <span className="cp-support-card__sub">Fresh within 2m. Fade threshold 3.5m.</span>
                      </article>
                    </div>
                  </section>

                  <section className="cp-section">
                    <div className="cp-evidence-grid">
                      <article className="cp-note-card">
                        <div className="cp-note-card__title">Why</div>
                        <ul className="cp-list">
                          {pulseWhy.map((item) => <li key={item}>{item}</li>)}
                        </ul>
                      </article>
                      <article className="cp-note-card cp-note-card--risk">
                        <div className="cp-note-card__title">Risk</div>
                        <ul className="cp-list">
                          {pulseRisks.map((item) => <li key={item}>{item}</li>)}
                        </ul>
                      </article>
                    </div>
                  </section>

                  <section className="cp-section">
                    <div className="section-header">
                      <h3>Tape Signals</h3>
                      <p className="section-desc">Recent coin-specific rows driving the tactical call.</p>
                    </div>
                    <AlertsTab filterSymbol={coinSymbol} compact hideHeader hideFoot />
                  </section>
                </>
              )}
            </section>
          )}

          {activeTab === 'intel' && (
            <section className="tab-panel active" role="tabpanel">
              {!coinSymbol ? (
                <div className="tab-empty">Select a coin to load external context.</div>
              ) : (
                <>
                  <section className="cp-section cp-section--hero">
                    <div className={`cp-hero cp-hero--${intelHero.tone}`}>
                      <div className="cp-hero__eyebrow">External Driver</div>
                      <div className="cp-hero__title">{intelHero.label}</div>
                      <div className="cp-hero__sub">{intelHero.detail}</div>
                    </div>
                  </section>

                  <section className="cp-section">
                    <div className="cp-support-grid">
                      {intelSupport.map((item) => (
                        <article key={item.label} className="cp-support-card">
                          <span className="cp-support-card__label">{item.label}</span>
                          <strong className={`cp-support-card__value ${item.tone}`}>{item.value}</strong>
                          <span className="cp-support-card__sub">
                            {item.label === 'Trust level'
                              ? 'Plumbing is secondary. Use this only to calibrate trust.'
                              : item.label === 'Source mix'
                                ? 'What kind of context is actually feeding this read.'
                                : item.label === 'Attention'
                                  ? 'Whether the move has external eyes on it.'
                                  : 'Last external refresh.'}
                          </span>
                        </article>
                      ))}
                    </div>
                  </section>

                  {coinIntelLoading && !coinIntel ? <div className="coin-history-note">Loading coin intel...</div> : null}
                  {coinIntelError ? (
                    <div className="coin-history-note error mw-fetch-note">External context is degraded. The read below is tape-led until outside sources reconnect.</div>
                  ) : null}

                  <div className="info-section">
                    <div className="section-header">
                      <h3>Events</h3>
                      <p className="section-desc">External catalyst evidence. If this is empty, the move is probably tape-led.</p>
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
                      <div className="tab-empty">No meaningful external driver detected. Move appears tape-led.</div>
                    )}
                  </div>

                  <div className="info-section">
                    <div className="section-header">
                      <h3>Context</h3>
                      <p className="section-desc">Attention, trust, and source mix. Social is context, not a hero KPI.</p>
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
                      <div className="tab-empty">No meaningful external context detected. Treat this as tape-first until something confirms.</div>
                    )}
                  </div>

                  <div className="info-section">
                    <div className="section-header">
                      <h3>Social Pulse</h3>
                      <p className="section-desc">Recent external items, shown only as supporting evidence.</p>
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

                  <div className="cp-meta-footer">
                    <span>Feed {coinIntel?.status || 'offline'}</span>
                    <span>Cached {Math.round(INTEL_REFRESH_MS / 1000)}s</span>
                    <span>Provider {socialSourceLabel || 'mixed'}</span>
                    <span>ID {coinIntel?.coinId || 'unlinked'}</span>
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
