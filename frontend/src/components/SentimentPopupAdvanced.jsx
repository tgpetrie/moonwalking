import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { useMarketHeat } from '../hooks/useMarketHeat';
import { useData } from '../context/DataContext';
import { API_ENDPOINTS, fetchData } from '../api';
import { getCoinEvents, isCoinEventActive } from '../utils/coinHistoryCache';
import { getMarketPressure } from '../utils/marketPressure';
import {
  PRIORITY_FADING_MS,
  PRIORITY_FRESH_MS,
  buildPriorityEvidence,
  buildPriorityItems,
  priorityBucketForAlert,
} from '../utils/priorityEngine.js';
import CoinPositioning from './CoinPositioning.jsx';
import { coinbaseSpotUrl } from '../utils/coinbaseUrl';
import AlertsTab from './AlertsTab';
import ChartReadPanel from './ChartReadPanel.jsx';
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
    history: root.history && typeof root.history === 'object' ? root.history : null,
    baselineStatus: root.baseline_status && typeof root.baseline_status === 'object' ? root.baseline_status : null,
    sources: root.sources && typeof root.sources === 'object' ? root.sources : {},
    marketSentiment: root.market_sentiment && typeof root.market_sentiment === 'object' ? root.market_sentiment : null,
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
    trendingRank: toNumber(root.trending_rank ?? root.trendingRank),
    trendingSource: String(root.trending_source ?? root.trendingSource ?? '').trim() || null,
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
    providers: Array.isArray(root.providers) ? root.providers : [],
    ts: root.ts || null,
  };
};

const rawTypeKey = (alert) => String(alert?.type_key || alert?.type || '').toLowerCase();

const alertTradeSemantics = (alert) => {
  const raw = rawTypeKey(alert);
  if (!raw) {
    return {
      label: 'NO SIGNAL',
      tone: 'neutral',
      intent: 'No alert family is driving this coin yet.',
      reason: 'Wait for tape, volume, or sentiment context to confirm.',
    };
  }

  if (raw.includes('fakeout')) {
    return {
      label: 'NO CHASE',
      tone: 'negative',
      intent: 'Breakout rejected. Do not buy extension.',
      reason: 'Needs reclaim plus fresh tape confirmation.',
    };
  }
  if (raw.includes('exhaustion_top') || raw.includes('exhaustion')) {
    return {
      label: 'PROTECT',
      tone: 'negative',
      intent: 'Late momentum is losing energy.',
      reason: 'Tighten risk; avoid new late entries until reset.',
    };
  }
  if (raw.includes('crater') || raw.includes('dump') || raw.includes('breadth_failure') || raw.includes('persistent_loser') || raw.includes('trend_break_down') || raw.includes('reversal_down')) {
    return {
      label: 'AVOID LONG',
      tone: 'negative',
      intent: 'Downside pressure is active.',
      reason: 'Wait for reclaim/base formation before buying.',
    };
  }
  if (raw.includes('divergence')) {
    return {
      label: 'TRAP RISK',
      tone: 'negative',
      intent: 'Price, volume, or timeframes disagree.',
      reason: 'Require confirmation before acting on the move.',
    };
  }
  if (raw.includes('liquidity_shock') || raw.includes('stealth') || raw.includes('whale')) {
    return {
      label: 'WATCH',
      tone: 'neutral',
      intent: 'Participation is showing before clean direction.',
      reason: 'Useful early smoke, not a buy by itself.',
    };
  }
  if (raw.includes('breadth_thrust') || raw.includes('trend_break_up')) {
    return {
      label: 'BUY WATCH',
      tone: 'positive',
      intent: 'Upside pressure has broader support.',
      reason: 'Favor pullbacks or clean retests over chasing.',
    };
  }
  if (raw.includes('moonshot') || raw.includes('breakout') || raw.includes('squeeze_break') || raw.includes('persistent_gainer')) {
    return {
      label: 'RECONFIRM',
      tone: 'positive',
      intent: 'Momentum is active, but extension risk is real.',
      reason: 'Buy quality improves after a hold/retest, not at max stretch.',
    };
  }
  if (raw.includes('fomo')) {
    return {
      label: 'HIGH HEAT',
      tone: 'neutral',
      intent: 'Coin is accelerating in hot tape.',
      reason: 'High opportunity and high chase risk; demand a fresh push.',
    };
  }
  if (raw.includes('reversal_up')) {
    return {
      label: 'RECLAIM WATCH',
      tone: 'neutral',
      intent: 'A bullish flip is starting.',
      reason: 'Better after retest holds above the reclaim.',
    };
  }

  const bucket = priorityBucketForAlert(alert);
  if (bucket === 'bullish') {
    return {
      label: 'BUY WATCH',
      tone: 'positive',
      intent: 'Upside tape is present.',
      reason: 'Confirm with volume, breadth, and freshness.',
    };
  }
  if (bucket === 'bearish') {
    return {
      label: 'AVOID LONG',
      tone: 'negative',
      intent: 'Bearish tape is present.',
      reason: 'Wait for a reclaim before buying.',
    };
  }
  return {
    label: 'WATCH',
    tone: 'neutral',
    intent: 'Signal needs context.',
    reason: 'Use this as attention, not as a standalone entry.',
  };
};

const ageLabel = (ms) => {
  if (!Number.isFinite(ms) || ms < 0) return 'n/a';
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  return `${Math.floor(minutes / 60)}h`;
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

const SupportRail = ({ items = [] }) => {
  const visible = Array.isArray(items) ? items.filter((item) => item && item.value) : [];
  if (!visible.length) return null;

  return (
    <div className="cp-support-rail">
      {visible.map((item) => (
        <article key={item.label} className={`cp-support-pill cp-support-pill--${item.tone || "neutral"}`}>
          <span className="cp-support-pill__label">{item.label}</span>
          <strong className="cp-support-pill__value">{item.value}</strong>
          {item.sub ? <span className="cp-support-pill__sub">{item.sub}</span> : null}
        </article>
      ))}
    </div>
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

// Returns true if the alert is still within its active window.
// Prefers backend `expires_at`/`ttl_seconds`; legacy rows use the existing
// backend-aligned five-minute fallback shared with the browser cache.
export const isAlertStillActive = (alert, nowMs) => isCoinEventActive(alert, nowMs);

// Pure, exported for testing. All present-tense signal flags require active
// evidence, including momentum and squeeze families.
export const computeSignalFlags = (coinAlerts, nowMs) => {
  const recent = Array.isArray(coinAlerts) ? coinAlerts.slice(0, 12) : [];
  const activeTypes = recent
    .filter((alert) => isAlertStillActive(alert, nowMs))
    .map((alert) => String(alert?.type_key || alert?.type || '').toLowerCase());
  return {
    hasReversal:   activeTypes.some((t) => t.includes('reversal') || t.includes('trend_break')),
    hasFakeout:    activeTypes.some((t) => t.includes('fakeout')),
    hasSqueeze:    activeTypes.some((t) => t.includes('squeeze') || t.includes('volatility_expansion')),
    hasExhaustion: activeTypes.some((t) => t.includes('exhaustion')),
    hasMomentum:   activeTypes.some((t) => t.includes('moonshot') || t.includes('breakout') || t.includes('coin_fomo')),
  };
};

export const computeBreakoutState = (coinAlerts, nowMs) => {
  const top = Array.isArray(coinAlerts)
    ? coinAlerts.find((alert) => isAlertStillActive(alert, nowMs))
    : null;
  if (!top) return 'No breakout';
  const type = String(top.type_key || top.type || '').toLowerCase();
  if (type.includes('moonshot') || type.includes('breakout')) return 'Breakout Up';
  if (type.includes('crater') || type.includes('dump')) return 'Breakout Down';
  return 'No breakout';
};

// Returns the most specific blocker message for an active risk flag,
// or null if no hard risk is present. `reversalRiskCurrent` is a boolean
// pre-computed by `isReversalRiskCurrent` — do not pass the raw stateLabel.
export const computeRiskBlocker = (signalFlags, reversalRiskCurrent) => {
  if (signalFlags?.hasFakeout)    return 'A recent fakeout warning is still active.';
  if (signalFlags?.hasReversal)   return 'Reversal risk is still active.';
  if (signalFlags?.hasExhaustion) return 'An exhaustion warning is still active.';
  if (reversalRiskCurrent)        return 'Reversal risk pattern is still active.';
  return null;
};

// Returns true only when the Event Evolution Reversal Risk state is still being
// actively confirmed. Uses `noConfirmMs` — the same field and threshold
// (`PRIORITY_FADING_MS`) the system already uses to classify entries as 'Fading'.
// A genuinely current Reversal Risk (noConfirmMs < 3.5 min) remains a hard veto;
// a stale one that persists only due to score-decay does not.
export const isReversalRiskCurrent = (coinPriorityEntry) => {
  if (coinPriorityEntry?.stateLabel !== 'Reversal Risk') return false;
  return (coinPriorityEntry?.noConfirmMs ?? Infinity) < PRIORITY_FADING_MS;
};

// The board badge and this popup read the same live rankings, but the per-coin
// insights that gate `metricsReady` load separately. Without consulting the
// live ranking while warming, an empty supports list renders "Nothing
// meaningful is confirming the setup yet." on a row the board is
// simultaneously badging "Tape confirmed" from the very same data.
export const buildWarmingSupports = (coinLiveRanking) => {
  const score = Number(coinLiveRanking?.live_score);
  if (!Number.isFinite(score) || score < 65) return [];
  return [`Live tape strength is ${score}/100.`];
};

// Headline for the WAIT posture. At score >= 65 the board badges the same coin
// "Tape confirmed", so "no clean setup is active" would read as a flat
// contradiction; name the narrower thing that is actually true instead.
export const resolveWaitHeadline = ({ breakoutUp, score }) => {
  if (breakoutUp) return 'Breakout detected, but confirmation is incomplete.';
  if (Number(score) >= 65)
    return 'Tape strength is notable, but the multi-factor setup is not aligned yet.';
  return 'No clean setup is active right now.';
};

// Pure posture decision table. Returns the label and tone for the current coin
// setup. Callers must handle the `metricsReady` guard separately.
export const computePostureLabel = ({
  score, alignmentLabel, volumeConfirms, persistenceGood, breadthUp,
  historyWeak, hardRisk, breakoutUp, change1m, change3m, canonicalState,
}) => {
  const alignedUp   = alignmentLabel === 'Aligned Up';
  const alignedDown = alignmentLabel === 'Aligned Down';
  const canonicalWeak = canonicalState === 'Fading' || canonicalState === 'Fragile';
  // Both short-term timeframes must be positive for the early gate.
  const shortTermUp = change1m != null && change1m > 0 && change3m != null && change3m > 0;

  if (hardRisk || alignedDown || score < 42)
    return 'STAY CLEAR';
  if (canonicalWeak)
    return 'WAIT';
  if (score >= 70 && alignedUp && volumeConfirms && persistenceGood && breadthUp >= 0.45 && !historyWeak)
    return 'STRONG SETUP';
  if (score >= 60 && volumeConfirms && alignedUp)
    return 'WATCH CLOSE';
  if (score >= 55 && shortTermUp && volumeConfirms && breakoutUp)
    return 'EARLY SETUP';
  return 'WAIT';
};

export const computeBreadthRead = (marketPressure) => {
  const raw = marketPressure?.breadth_up;
  const value = raw === null || raw === undefined || raw === '' ? null : Number(raw);
  if (!Number.isFinite(value)) {
    return {
      available: false,
      value: null,
      status: 'Unavailable',
      tone: 'neutral',
      inline: 'breadth unavailable',
      hero: null,
      badge: null,
      blocker: 'Market breadth is unavailable.',
      risk: 'broad tape support is unavailable',
    };
  }
  if (value >= 0.56) {
    return {
      available: true,
      value,
      status: 'Supportive',
      tone: 'positive',
      inline: 'breadth supports upside',
      hero: 'breadth supportive',
      badge: null,
      blocker: null,
      risk: null,
    };
  }
  if (value <= 0.44) {
    return {
      available: true,
      value,
      status: 'Hostile',
      tone: 'negative',
      inline: 'breadth is hostile',
      hero: 'breadth weak',
      badge: 'BREADTH WEAK',
      blocker: 'Most of the market is not helping it.',
      risk: 'broad tape support is weak',
    };
  }
  return {
    available: true,
    value,
    status: 'Mixed',
    tone: 'neutral',
    inline: 'breadth is mixed',
    hero: null,
    badge: null,
    blocker: null,
    risk: null,
  };
};

// Reports whether the external intel feed answered — nothing more. The previous
// wording ("Trust level: High/Medium/Low") named a data-availability signal as
// if it graded how much the read could be trusted, which is the same defect
// `e684ab52` removed from Market Mood's freshness readout.
export const computeFeedStatus = (coinIntel, coinIntelError) => {
  if (coinIntelError) return { value: 'Degraded', tone: 'negative' };
  if (coinIntel?.status === 'live') return { value: 'Live', tone: 'positive' };
  return { value: 'Cached', tone: 'neutral' };
};

// This rail was labeled "Persistence" while its value was the canonical
// priority state, so it rendered "Persistence: Reversal Risk" — a category
// error, since a risk state is not a measure of how persistent a move is.
// Name the rail for what it actually carries. The genuine rank-hold read was
// already in the sub-line (`rankSummary`) and stays there, joined with the
// hold streak, so no new badge is needed to carry it.
export const buildPriorityRailItem = (coinPriorityEntry, persistenceStreak, fallbackSub) => {
  const stateLabel = coinPriorityEntry?.stateLabel || null;
  const tone =
    stateLabel === 'Dominant' || stateLabel === 'Persistent'
      ? 'positive'
      : stateLabel === 'Reversal Risk'
        ? 'negative'
        : 'neutral';
  const holdNote = persistenceStreak ? `${persistenceStreak}x hold` : null;
  return {
    label: 'Priority',
    // With no priority entry there is no priority state to report. A hold count
    // ("3x hold") or a bare "Low" is not one, so say the coin is unranked.
    value: stateLabel || 'Not ranked',
    tone,
    sub: coinPriorityEntry?.rankSummary || [holdNote, fallbackSub].filter(Boolean).join(' · '),
  };
};

// Canonical priority state -> popup hero state. Exhaustive over every state
// `priorityStateForEntry` can return, so the popup can never silently drop one:
// 'Persistent' and 'Fragile' previously had no branch at all, which sent a
// Persistent coin to the 'Range-hold' fallback ("rotating inside range").
export const PRIORITY_STATE_TO_HERO = Object.freeze({
  Dominant: 'Dominant',
  Persistent: 'Persistent',
  Building: 'Building',
  'Reversal Risk': 'Fragile',
  Fading: 'Fading',
  Fragile: 'Fragile',
});

export const mapPriorityStateToHero = (stateLabel) =>
  PRIORITY_STATE_TO_HERO[stateLabel] || null;

// Presentation for a hero state. Split out so the state decision and its copy
// stay separable, and so both can be asserted without rendering the popup.
export const describeHeroState = (state, { freshAgeMs = null, volumeConfirms = false } = {}) => {
  switch (state) {
    case 'Dominant':
      return {
        state: 'Dominant',
        tone: 'positive',
        sub:
          freshAgeMs !== null && freshAgeMs <= PRIORITY_FRESH_MS
            ? `Fresh 3m confirmation ${ageLabel(freshAgeMs)} ago. Alignment and participation are supporting the move.`
            : 'Strength is still holding, but the next reconfirm matters.',
      };
    case 'Persistent':
      return {
        state: 'Persistent',
        tone: 'positive',
        sub: 'The move keeps holding its rank across refreshes, even without a fresh push.',
      };
    case 'Building':
      return {
        state: 'Building',
        tone: 'positive',
        sub: volumeConfirms
          ? 'Early upside pressure is present and volume is confirming it, but the setup is not fully settled yet.'
          : 'Early upside pressure is present, but confirmation and participation are still uneven.',
      };
    case 'Fragile':
      return {
        state: 'Fragile',
        tone: 'negative',
        sub: 'Structure is unstable. Recent strength looks vulnerable until the coin reclaims and reconfirms.',
      };
    case 'Fading':
      return {
        state: 'Fading',
        tone: 'negative',
        sub:
          freshAgeMs !== null && freshAgeMs > PRIORITY_FADING_MS
            ? `No reconfirm in ${(freshAgeMs / 60000).toFixed(1)}m. Support is thinning and follow-through is fading.`
            : 'Pressure is slipping and follow-through is weakening.',
      };
    case 'Range-hold':
      return {
        state: 'Range-hold',
        tone: 'neutral',
        sub: 'The coin is rotating inside range. Direction is mixed and there is no clean breakout edge yet.',
      };
    default:
      return {
        state: 'Mixed',
        tone: 'neutral',
        sub: 'Tape is active, but direction and conviction are still mixed. No clean edge yet.',
      };
  }
};

// Hero state for a coin the priority engine has not ranked. These fallbacks are
// the only place local evidence decides the state, and they run only when there
// is no canonical state to contradict. Risk flags are tested before the bullish
// cases so an active fakeout/exhaustion cannot be reported as 'Building'.
export const resolveUnrankedHeroState = ({
  breakoutState, alignmentScore, volumeConfirms, signalFlags, change3m,
}) => {
  const flags = signalFlags || {};
  if (flags.hasFakeout || flags.hasReversal || flags.hasExhaustion) return 'Fragile';
  if (breakoutState === 'Breakout Up' && alignmentScore >= 3 && volumeConfirms) return 'Dominant';
  if (flags.hasMomentum || (change3m !== null && change3m > 0)) return 'Building';
  if (breakoutState === 'Breakout Down' || (change3m !== null && change3m < 0 && alignmentScore <= -2)) {
    return 'Fading';
  }
  if (!flags.hasMomentum) return 'Range-hold';
  return 'Mixed';
};

export const resolveCoinHeroState = ({
  coinPriorityEntry,
  metricsReady,
  breakoutState,
  alignmentScore,
  volumeConfirms,
  signalFlags,
  change3m,
}) => {
  if (coinPriorityEntry) {
    return mapPriorityStateToHero(coinPriorityEntry.stateLabel) || 'Mixed';
  }
  if (!metricsReady) return 'Warming';
  return resolveUnrankedHeroState({
    breakoutState,
    alignmentScore,
    volumeConfirms,
    signalFlags,
    change3m,
  });
};

const parseEventNumber = (value) => {
  if (value === '' || value === null || value === undefined) return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const buildLaunchEventContext = (launchContext) => {
  const raw = launchContext && typeof launchContext === 'object' ? launchContext : null;
  if (!raw) return null;

  const alert = raw.alert && typeof raw.alert === 'object' ? raw.alert : null;
  const direct = raw.event_context && typeof raw.event_context === 'object' ? raw.event_context : null;
  const source = direct || alert || raw;
  if (!source || typeof source !== 'object') return null;

  const evidence = source.evidence && typeof source.evidence === 'object'
    ? source.evidence
    : {};
  const typeKey = String(source.type_key || source.type || '').trim().toUpperCase();
  const window = String(evidence.window || source.window || '').trim();
  const price = parseEventNumber(evidence.price ?? source.price ?? null);
  const pct = parseEventNumber(evidence.pct ?? source.pct ?? null);

  const normalized = {};
  if (typeKey) normalized.type_key = typeKey;

  const normalizedEvidence = {};
  if (window) normalizedEvidence.window = window;
  if (price !== null) normalizedEvidence.price = price;
  if (pct !== null) normalizedEvidence.pct = pct;

  if (Object.keys(normalizedEvidence).length > 0) {
    normalized.evidence = normalizedEvidence;
  }

  return Object.keys(normalized).length > 0 ? normalized : null;
};

const buildAlertBanner = (launchContext) => {
  if (!launchContext || launchContext.source !== 'alerts_center') return null;
  const alert = launchContext.alert;
  if (!alert || typeof alert !== 'object') return null;

  const typeKey = String(alert.type_key || alert.type || '').trim().toUpperCase();
  if (!typeKey) return null;

  const evidence = alert.evidence && typeof alert.evidence === 'object' ? alert.evidence : {};
  const price = parseEventNumber(evidence.price ?? alert.price ?? null);
  const alertWindow = String(evidence.window || alert.window || '').trim();
  const theRead = alert.the_read && typeof alert.the_read === 'object' ? alert.the_read : null;

  const locationParts = [];
  if (alertWindow && price !== null) locationParts.push(`${alertWindow} near $${price}`);
  else if (alertWindow) locationParts.push(`${alertWindow} window`);
  else if (price !== null) locationParts.push(`near $${price}`);

  const headline = locationParts.length
    ? `${typeKey} · ${locationParts[0]}`
    : typeKey;

  const watchLine = theRead?.summary
    || (price !== null ? `Watch whether $${price} holds with continued activity.` : 'Watch for confirmation or rejection of this level.');

  return { headline, watchLine, tone: theRead?.tone || 'neutral' };
};

// ---------------------------------------------------------------------------
// Track Record — per-coin outcome history
// ---------------------------------------------------------------------------

// Readiness is decided by the server, which is the only place that knows
// whether a rate came from controlled measurement. A threshold here could
// promote a category the server had deliberately withheld.
const isTrackMeasured = (status) => status === 'measured';

function CoinOutcomeHistoryCard({ card }) {
  const peerMeasured = isTrackMeasured(card.peer_status);
  const placeboMeasured = isTrackMeasured(card.placebo_status);
  const showRate = peerMeasured && card.win_rate != null;
  const required = card.required_market_periods;
  const dirLabel = card.direction === 'up' ? 'Bullish' : card.direction === 'down' ? 'Bearish' : 'Neutral';

  return (
    <div className="coh-card">
      <div className="coh-card__header">
        <span className="coh-card__label">{card.label}</span>
        <span className={`coh-card__dir coh-card__dir--${card.direction}`}>{dirLabel}</span>
      </div>
      <div className="coh-card__stats">
        <div className="coh-stat">
          <span className="coh-stat__label">Follow-through</span>
          {showRate ? (
            <span className="coh-stat__value">{Math.round(card.win_rate * 100)}%</span>
          ) : (
            <span className="coh-stat__muted">No clear edge detected yet — still collecting</span>
          )}
        </div>
        {/* The two controls fill at different rates, so a single progress
            number would misstate both. */}
        {required != null && (
          <>
            <div className="coh-stat">
              <span className="coh-stat__label">Coin-selection</span>
              <span className="coh-stat__value coh-stat--progress">
                {peerMeasured ? 'Measured' : `${card.peer_market_periods ?? 0} of ${required} market periods`}
              </span>
            </div>
            <div className="coh-stat">
              <span className="coh-stat__label">Timing</span>
              <span className="coh-stat__value coh-stat--progress">
                {placeboMeasured ? 'Measured' : `${card.placebo_market_periods ?? 0} of ${required} market periods`}
              </span>
            </div>
          </>
        )}
        {peerMeasured && card.median_favorable_pct != null && (
          <div className="coh-stat">
            <span className="coh-stat__label">Typical best move</span>
            <span className="coh-stat__value coh-stat--pos">+{card.median_favorable_pct.toFixed(2)}%</span>
          </div>
        )}
        {peerMeasured && card.median_adverse_pct != null && (
          <div className="coh-stat">
            <span className="coh-stat__label">Typical worst dip</span>
            <span className="coh-stat__value coh-stat--neg">{card.median_adverse_pct.toFixed(2)}%</span>
          </div>
        )}
      </div>
    </div>
  );
}

export function CoinOutcomeHistory({ data, loading, error, symbol }) {
  if (loading && !data) {
    return <div className="coh-loading">Loading track record…</div>;
  }
  if (error) {
    return <div className="coh-note coh-note--error">Track record temporarily unavailable.</div>;
  }
  if (!data) return null;

  const { signal_types = [], total_outcomes = 0, target_pct, adverse_pct, measurement_status } = data;
  // Note: `status` on this payload is transport health (live/degraded).
  // Measurement readiness is a separate field precisely so the two can never
  // be confused for one another.
  const measured = measurement_status === 'measured';

  return (
    <section className="coh-section">
      <div className="coh-header">
        <span className="coh-header__title">Track Record</span>
        <span className="coh-header__sub">
          {measured
            ? `${total_outcomes.toLocaleString()} comparable outcomes · graded +${target_pct}% vs −${adverse_pct}%`
            : `Measuring against matched control coins · graded +${target_pct}% vs −${adverse_pct}%`}
        </span>
      </div>
      {signal_types.length === 0 ? (
        <div className="coh-empty">No signal history for {symbol} yet.</div>
      ) : (
        <div className="coh-cards">
          {signal_types.map((card) => (
            <CoinOutcomeHistoryCard
              key={`${card.state}-${card.direction}-${card.label}`}
              card={card}
            />
          ))}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------

const SentimentPopupAdvanced = ({ isOpen, onClose, symbol, defaultTab = 'coin', launchContext = null }) => {
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
    marketPressure: market_pressure = null,
    gainers_1m = [],
    gainers_3m = [],
    losers_3m = [],
    liveRankings = [],
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

  const [coinPositioning, setCoinPositioning] = useState(null);
  const [coinPositioningLoading, setCoinPositioningLoading] = useState(false);

  const [chartRead, setChartRead] = useState(null);
  const [chartReadLoading, setChartReadLoading] = useState(false);
  const [chartReadError, setChartReadError] = useState(null);
  const [chartDrawerOpen, setChartDrawerOpen] = useState(false);

  const [coinHistory, setCoinHistory] = useState(null);
  const [coinHistoryLoading, setCoinHistoryLoading] = useState(false);
  const [coinHistoryError, setCoinHistoryError] = useState(null);

  const coinSymbol = useMemo(() => normalizeSymbol(symbol), [symbol]);
  const coinbaseTradeUrl = useMemo(
    () => coinbaseSpotUrl({ symbol: coinSymbol }),
    [coinSymbol]
  );
  const coinLiveRanking = useMemo(
    () => (Array.isArray(liveRankings)
      ? liveRankings.find((row) => normalizeSymbol(row?.symbol || row?.product_id) === coinSymbol) || null
      : null),
    [liveRankings, coinSymbol]
  );
  const chartEventContext = useMemo(
    () => buildLaunchEventContext(launchContext),
    [launchContext]
  );
  const alertBanner = useMemo(
    () => buildAlertBanner(launchContext),
    [launchContext]
  );

  useEffect(() => {
    if (isOpen) setActiveTab(normalizeTab(defaultTab));
  }, [isOpen, defaultTab]);

  useEffect(() => {
    if (chartEventContext) setChartDrawerOpen(true);
  }, [chartEventContext]);

  useEffect(() => {
    if (!isOpen) setChartDrawerOpen(false);
  }, [isOpen]);

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

  useEffect(() => {
    if (!isOpen || !coinSymbol) {
      setCoinPositioning(null);
      return undefined;
    }
    let cancelled = false;
    setCoinPositioningLoading(true);
    const change = coinLiveRanking?.price_change_percentage_24h;
    const suffix = Number.isFinite(change) ? `?change_24h_pct=${change}` : '';
    fetchData(`/api/positioning/${encodeURIComponent(coinSymbol)}${suffix}`)
      .then((p) => { if (!cancelled) setCoinPositioning(p); })
      .catch(() => { if (!cancelled) setCoinPositioning(null); })
      .finally(() => { if (!cancelled) setCoinPositioningLoading(false); });
    return () => { cancelled = true; };
  }, [isOpen, coinSymbol, coinLiveRanking]);

  useEffect(() => {
    if (!isOpen || !coinSymbol) {
      setChartRead(null);
      setChartReadError(null);
      return undefined;
    }
    let cancelled = false;
    setChartReadLoading(true);
    const endpoint = API_ENDPOINTS.chartRead
      ? API_ENDPOINTS.chartRead(coinSymbol, chartEventContext)
      : `/api/chart-read/${encodeURIComponent(coinSymbol)}`;
    fetchData(endpoint)
      .then((d) => { if (!cancelled) { setChartRead(d); setChartReadError(null); } })
      .catch(() => { if (!cancelled) setChartReadError('unavailable'); })
      .finally(() => { if (!cancelled) setChartReadLoading(false); });
    return () => { cancelled = true; };
  }, [isOpen, coinSymbol, chartEventContext]);

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

  useEffect(() => {
    if (!isOpen || !coinSymbol) {
      setCoinHistory(null);
      setCoinHistoryError(null);
      setCoinHistoryLoading(false);
      return;
    }
    let cancelled = false;
    setCoinHistoryLoading(true);
    fetchData(`/api/coin-history/${encodeURIComponent(coinSymbol)}`)
      .then((payload) => {
        if (cancelled) return;
        if (payload?.status === 'degraded') {
          setCoinHistoryError('degraded');
        } else {
          setCoinHistory(payload ?? null);
          setCoinHistoryError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setCoinHistoryError(String(err?.message || err || 'Failed'));
      })
      .finally(() => {
        if (!cancelled) setCoinHistoryLoading(false);
      });
    return () => { cancelled = true; };
  }, [isOpen, coinSymbol]);

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

  const nowMs = Date.now();

  const activeCoinAlerts = useMemo(
    () => coinAlerts.filter((alert) => isAlertStillActive(alert, nowMs)),
    [coinAlerts, nowMs]
  );

  const breakoutState = useMemo(
    () => computeBreakoutState(coinAlerts, nowMs),
    [coinAlerts, nowMs]
  );

  const change1m = toNumber(coinInsights?.change1m);
  const change3m = toNumber(coinInsights?.change3m);
  const change1h = toNumber(coinInsights?.change1h);
  const volumeChange1h = toNumber(coinInsights?.volumeChange1h);
  const tape = Array.isArray(coinInsights?.tape) ? coinInsights.tape : [];
  const storedTapeSamples = Math.max(0, Number(coinInsights?.history?.samples) || tape.length || 0);
  const tapeIsPersistent = coinInsights?.history?.persistent === true;
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
    for (const alert of activeCoinAlerts) {
      const streak = toNumber(alert?.evidence?.streak ?? alert?.extra?.streak);
      if (streak !== null && streak > 0) {
        streakRaw = Math.max(streakRaw, streak);
      }
    }
    const streak = Math.min(1, Math.max(0, streakRaw) / 4);
    const volumeConfirm = volumeConfirms ? 1 : 0;
    return Math.round(((0.45 * alignment) + (0.35 * volumeConfirm) + (0.2 * streak)) * 100);
  }, [hasCoinTape, alignmentScore, activeCoinAlerts, volumeConfirms]);

  const signalFlags = useMemo(
    () => computeSignalFlags(coinAlerts, nowMs),
    [coinAlerts, nowMs],
  );

  const persistenceStreak = useMemo(() => {
    for (const alert of activeCoinAlerts) {
      const streak = toNumber(alert?.evidence?.streak ?? alert?.extra?.streak);
      if (streak !== null && streak > 0) return Math.round(streak);
      const type = String(alert?.type_key || alert?.type || '').toLowerCase();
      if (type.includes('persistent')) return 1;
    }
    return null;
  }, [activeCoinAlerts]);

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
    const topType = String(activeCoinAlerts[0]?.type_key || activeCoinAlerts[0]?.type || '').toLowerCase();
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
  }, [activeCoinAlerts, breakoutState, alignmentScore, volumeConfirms]);

  const socialMetrics = coinIntel?.social?.metrics || null;
  const socialHeat = toNumber(socialMetrics?.socialHeat);
  const socialVolume24h = toNumber(socialMetrics?.socialVolume24h ?? socialMetrics?.posts24h);
  const socialEngagement24h = toNumber(socialMetrics?.socialEngagement24h);
  const socialDominance24h = toNumber(socialMetrics?.socialDominance24h);
  const socialRank = toNumber(socialMetrics?.socialRank);
  const socialPosts60m = toNumber(socialMetrics?.posts60m);
  const socialPosts24h = toNumber(socialMetrics?.posts24h);
  const socialUniqueAuthors24h = toNumber(socialMetrics?.uniqueAuthors24h);
  const socialTrendingRank = toNumber(socialMetrics?.trendingRank);
  const socialTrendingSource = String(socialMetrics?.trendingSource || '').trim() || null;
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
    (socialTrendingRank !== null && socialTrendingRank > 0) ||
    Boolean(socialSentimentDisplay)
  ), [
    socialHeat,
    socialVolume24h,
    socialEngagement24h,
    socialDominance24h,
    socialRank,
    socialPosts60m,
    socialUniqueAuthors24h,
    socialTrendingRank,
    socialSentimentDisplay,
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
  const marketPressureSummary = useMemo(
    () => getMarketPressure({ market_pressure }),
    [market_pressure]
  );
  const breadthRead = useMemo(
    () => computeBreadthRead(marketPressureSummary),
    [marketPressureSummary]
  );

  const sourceHealth = useMemo(() => {
    const baseline = coinInsights?.baselineStatus || {};
    const socialStatus = String(coinIntel?.social?.status || 'offline').toLowerCase();
    const newsStatus = String(coinIntel?.news?.status || coinIntel?.events?.status || 'offline').toLowerCase();
    const newsCount = Math.max(
      coinIntel?.news?.items?.length || 0,
      coinIntel?.events?.items?.length || 0
    );
    const breadthUniverse = Number(market_pressure?.symbol_count);
    const macroLive = Number.isFinite(Number(coinInsights?.marketSentiment?.value));
    return [
      {
        label: 'Price tape',
        value: metricsReady ? 'Live' : coinInsightsLoading ? 'Warming' : 'Unavailable',
        tone: metricsReady ? 'positive' : 'neutral',
        sub: metricsReady ? 'Coinbase snapshots are current.' : 'Short windows are still filling.',
      },
      {
        label: 'Volume',
        value: baseline.volume_1h ? 'Live' : 'Unavailable',
        tone: baseline.volume_1h ? 'positive' : 'negative',
        sub: baseline.volume_1h ? 'Current and prior 1h windows are present.' : 'No trustworthy 1h comparison yet.',
      },
      {
        label: 'Market breadth',
        value: breadthRead.available ? 'Live' : 'Unavailable',
        tone: breadthRead.available ? 'positive' : 'neutral',
        sub: breadthRead.available
          ? (Number.isFinite(breadthUniverse) && breadthUniverse > 0 ? `${breadthUniverse} Coinbase markets tracked.` : 'Cross-market participation is current.')
          : 'Broad-market participation is missing.',
      },
      {
        label: 'Macro mood',
        value: macroLive ? 'Live' : 'Unavailable',
        tone: macroLive ? 'positive' : 'negative',
        sub: macroLive ? `${coinInsights.marketSentiment.classification || 'Fear & Greed'} · market-wide only.` : 'No market-wide mood source.',
      },
      {
        label: 'Coin social',
        value: hasMeaningfulSocialMetrics ? 'Live' : socialStatus === 'stale' ? 'Stale / empty' : 'Unavailable',
        tone: hasMeaningfulSocialMetrics ? 'positive' : 'negative',
        sub: hasMeaningfulSocialMetrics ? `${socialSourceLabel || 'External'} coin context is present.` : 'Not included in the trading read.',
      },
      {
        label: 'News / events',
        value: newsStatus === 'live' ? (newsCount ? `Live · ${newsCount}` : 'Live · no items') : 'Unavailable',
        tone: newsStatus === 'live' ? (newsCount ? 'positive' : 'neutral') : 'negative',
        sub: newsCount ? 'Coin-specific catalyst items are present.' : 'No catalyst is being assumed.',
      },
    ];
  }, [
    coinInsights,
    coinInsightsLoading,
    coinIntel,
    market_pressure,
    marketPressureSummary,
    breadthRead,
    metricsReady,
    hasMeaningfulSocialMetrics,
    socialSourceLabel,
  ]);

  const priorityEvidence = useMemo(
    () => buildPriorityEvidence({ activeAlerts, recentAlerts: alertsRecent, nowMs }),
    [activeAlerts, alertsRecent, nowMs]
  );

  const priorityEntries = useMemo(
    () =>
      buildPriorityItems({
        alerts: priorityEvidence,
        gainers1m: gainers_1m,
        gainers3m: gainers_3m,
        losers3m: losers_3m,
        marketPressure: marketPressureSummary,
        nowMs,
      }),
    [priorityEvidence, gainers_1m, gainers_3m, losers_3m, marketPressureSummary, nowMs]
  );

  const coinPriorityEntry = useMemo(
    () => priorityEntries.find((entry) => entry.symbol === coinSymbol) || null,
    [priorityEntries, coinSymbol]
  );
  const hasCanonicalNegativeState = ['Reversal Risk', 'Fragile', 'Fading'].includes(coinPriorityEntry?.stateLabel);
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
    if (hasCanonicalNegativeState) {
      return {
        label: 'Fragile',
        detail: 'Positive confirmation cannot override the canonical risk state.',
        tone: 'negative',
      };
    }
    if (confidencePct >= 75) return { label: 'Strong', detail: 'Driven by confirmation, persistence, and volume support.', tone: 'positive' };
    if (confidencePct >= 55) return { label: 'Mixed', detail: 'Some confirmation is present, but conviction is not clean yet.', tone: 'neutral' };
    return { label: 'Fragile', detail: 'Mixed alignment or weak confirmation reduces trust.', tone: 'negative' };
  }, [confidencePct, hasCanonicalNegativeState]);

  const freshAgeMs = useMemo(() => {
    const ts = coinPriorityEntry?.lastTsMs ?? normalizeTsMs(lastCoinUpdateTs);
    return Number.isFinite(ts) ? Math.max(0, nowMs - ts) : null;
  }, [coinPriorityEntry, lastCoinUpdateTs, nowMs]);

  // Canonical priority is the sole authority on this coin's state.
  //
  // This block used to reach 'Dominant'/'Building' from its own fallback
  // evidence (breakoutState, signalFlags, a bare `change3m > 0`) *even when the
  // priority engine said otherwise*, and because the Building test ran before
  // the Reversal Risk test, a coin the engine classed 'Reversal Risk' with a
  // positive 3m surfaced here as 'Building'. The Coin tab reads posture
  // straight from the priority entry, so one popup could show STAY CLEAR on
  // Coin and BUY WATCH on Pulse at the same instant — the same contradiction
  // 2ea35e71 removed between the board and this popup, and a second semantic
  // authority after 927a5d6c centralized priority.
  //
  // The local fallbacks still run, but only for a coin the engine has not
  // ranked, where there is no canonical state for them to contradict.
  const coinHero = useMemo(() => {
    if (!coinSymbol) {
      return {
        eyebrow: 'Coin State',
        state: 'No coin selected',
        sub: 'Pick a coin from the board to load local state.',
        tone: 'neutral',
      };
    }
    const eyebrow = `${coinSymbol} Right Now`;
    const state = resolveCoinHeroState({
      coinPriorityEntry,
      metricsReady,
      breakoutState,
      alignmentScore,
      volumeConfirms,
      signalFlags,
      change3m,
    });
    if (state === 'Warming') {
      return {
        eyebrow,
        state: 'Warming',
        sub: 'Advanced insights warming up. Waiting for enough tape to trust the local read.',
        tone: 'neutral',
      };
    }

    return { eyebrow, ...describeHeroState(state, { freshAgeMs, volumeConfirms }) };
  }, [coinSymbol, metricsReady, coinPriorityEntry, breakoutState, alignmentScore, volumeConfirms, freshAgeMs, signalFlags, change3m]);

  const actionBias = useMemo(() => {
    if (!metricsReady) return { label: 'Wait', detail: 'Need more tape before trusting a local read.', tone: 'neutral' };
    if (coinHero.state === 'Dominant' || coinHero.state === 'Persistent') return { label: 'Press strength', detail: 'Momentum is confirmed. Favor pullbacks over chasing extension.', tone: 'positive' };
    if (coinHero.state === 'Building') return { label: 'Only act on reconfirm', detail: 'Setup is constructive, but you want another fresh push inside the 7m window.', tone: 'neutral' };
    if (coinHero.state === 'Fragile') return { label: 'Stand aside', detail: 'This setup can break either way. Wait for reclaim or cleaner failure.', tone: 'negative' };
    if (coinHero.state === 'Fading') return { label: 'Watch for reclaim', detail: 'Do not press weakness blindly. Require a reclaim before re-engaging.', tone: 'negative' };
    if (coinHero.state === 'Range-hold' || coinHero.state === 'Mixed') return { label: 'Stand aside', detail: 'Tape is mixed. Wait for a reclaim, breakdown, or fresh reconfirm.', tone: 'neutral' };
    return { label: 'Wait', detail: 'Nothing here deserves urgency yet.', tone: 'neutral' };
  }, [metricsReady, coinHero]);

  const quickBuyRead = useMemo(() => {
    if (!metricsReady) {
      return {
        label: 'WAIT',
        tone: 'neutral',
        intent: 'Tape is still warming.',
        reason: 'Do not use the coin read until the 1m/3m windows and baselines are populated.',
        sentiment: 'No reliable sentiment context yet.',
        confirmation: 'Need live tape first.',
      };
    }

    const topAlert = activeCoinAlerts[0] || null;
    const semantic = alertTradeSemantics(topAlert);
    const hasFreshConfirm = freshAgeMs !== null && freshAgeMs <= PRIORITY_FRESH_MS;
    const breadthUp = breadthRead.value;
    const breadthDown = Number(marketPressureSummary?.breadth_down ?? 0) || 0;
    const breadthText = breadthRead.available || breadthDown < 0.56
      ? breadthRead.inline
      : 'breadth supports downside';
    const attentionParts = [];
    if (socialTrendingRank !== null && socialTrendingRank > 0) {
      attentionParts.push(`trending #${socialTrendingRank}${socialTrendingSource ? ` via ${socialTrendingSource}` : ''}`);
    }
    if (socialVolume24h !== null && socialVolume24h > 0) {
      attentionParts.push(`${formatCompactNumber(socialVolume24h)} 24h social mentions`);
    }
    if (socialActionLine) {
      attentionParts.push(socialActionLine);
    } else if (socialIsProxy && hasMeaningfulSocialMetrics) {
      attentionParts.push('attention proxy only; no true social sentiment score');
    } else if (!hasMeaningfulSocialMetrics) {
      attentionParts.push('no meaningful external sentiment driver');
    }

    let label = semantic.label;
    let tone = semantic.tone;
    let intent = semantic.intent;
    let reason = semantic.reason;
    let confirmation = `${volumeConfirms ? 'volume confirms' : 'volume missing'} · ${breadthText}`;

    if (semantic.tone === 'positive') {
      if (!volumeConfirms || !hasFreshConfirm || breadthUp === null || breadthUp < 0.45 || signalFlags.hasFakeout || signalFlags.hasExhaustion) {
        label = 'RECONFIRM';
        tone = 'neutral';
        intent = 'Upside exists, but it is not clean enough for a blind quick buy.';
        confirmation = `${hasFreshConfirm ? 'fresh' : 'needs fresh push'} · ${confirmation}`;
      } else if (coinHero.state === 'Dominant' || coinHero.state === 'Persistent' || coinHero.state === 'Building') {
        label = 'BUY WATCH';
        tone = 'positive';
        intent = 'Fast tape, participation, and context are aligned enough to watch for an entry.';
      }
    }

    if (semantic.tone === 'negative') {
      label = semantic.label === 'NO SIGNAL' ? 'WAIT' : semantic.label;
      tone = 'negative';
      intent = semantic.intent;
    } else if (coinHero.state === 'Fragile' || coinHero.state === 'Fading') {
      label = 'WAIT';
      tone = 'negative';
      intent = actionBias.detail;
      reason = coinPriorityEntry?.stateLabel === 'Reversal Risk'
        ? 'Wait for the active risk warning to clear before treating this as a clean setup.'
        : 'Nothing here deserves urgency yet.';
    }

    return {
      label,
      tone,
      intent,
      reason,
      sentiment: attentionParts.filter(Boolean).slice(0, 2).join(' · '),
      confirmation,
    };
  }, [
    metricsReady,
    activeCoinAlerts,
    freshAgeMs,
    marketPressureSummary,
    breadthRead,
    socialTrendingRank,
    socialTrendingSource,
    socialVolume24h,
    socialActionLine,
    socialIsProxy,
    hasMeaningfulSocialMetrics,
    volumeConfirms,
    signalFlags,
    coinHero,
    actionBias,
    coinPriorityEntry,
  ]);

  const pulseTrigger = useMemo(() => {
    if (!metricsReady) return 'Need more tape';
    if (freshAgeMs !== null && freshAgeMs <= PRIORITY_FRESH_MS) return `Fresh ${ageLabel(freshAgeMs)}`;
    if (signalFlags.hasFakeout) return 'Reclaim needed';
    if (volumeConfirms && alignmentLabel !== 'Mixed') return 'Hold top cohort';
    return 'Reconfirm inside 2m';
  }, [metricsReady, freshAgeMs, signalFlags, volumeConfirms, alignmentLabel]);

  const coinBadges = useMemo(() => {
    const badges = [];
    if (breakoutState === 'Breakout Up') badges.push({ label: 'BREAKOUT ACTIVE', tone: 'positive' });
    if (signalFlags.hasFakeout) badges.push({ label: 'FAILED BREAKOUT', tone: 'negative' });
    if (!signalFlags.hasFakeout && !signalFlags.hasMomentum && !signalFlags.hasReversal && metricsReady) badges.push({ label: 'RANGE-HOLD', tone: 'neutral' });
    if (volumeConfirms) badges.push({ label: 'VOLUME CONFIRMED', tone: 'positive' });
    if (breadthRead.badge) badges.push({ label: breadthRead.badge, tone: breadthRead.tone });
    if (coinPriorityEntry?.stateLabel === 'Reversal Risk' || signalFlags.hasReversal || signalFlags.hasExhaustion) badges.push({ label: 'REVERSAL RISK', tone: 'negative' });
    return badges;
  }, [breakoutState, signalFlags, metricsReady, volumeConfirms, breadthRead, coinPriorityEntry]);

  const earlyRead = useMemo(() => {
    // Fast, deliberately-unconfirmed directional lean from 1m+3m momentum plus
    // funding bias. This commits sooner than the confirmed verdict below (it
    // accepts noise for immediacy) so the panel always shows a direction.
    const m1 = Number.isFinite(change1m) ? change1m : null;
    const m3 = Number.isFinite(change3m) ? change3m : null;
    if (m1 === null && m3 === null) {
      return { label: 'NEUTRAL', tone: 'neutral', note: 'No fast momentum yet.' };
    }
    const mom = (m3 ?? 0) * 0.6 + (m1 ?? 0) * 0.4; // weight 3m over noisier 1m
    const THRESH = 0.15; // percent — below this is baseline alt wiggle
    const bias = coinPositioning?.available ? coinPositioning.funding_bias : null;
    if (mom >= THRESH) {
      if (hasCanonicalNegativeState) {
        return {
          label: 'TAPE UP',
          tone: 'caution',
          note: 'Short-term tape is pushing up, but the risk warning overrides entry quality.',
        };
      }
      if (bias === 'crowded_long') return { label: 'TAPE UP', tone: 'caution', note: 'Up, but longs are crowded — squeeze risk.' };
      if (bias === 'short' || bias === 'crowded_short') return { label: 'TAPE UP', tone: 'positive', note: 'Up with shorts paying — clean push.' };
      return { label: 'TAPE UP', tone: 'positive', note: 'Short-term tape is pushing up.' };
    }
    if (mom <= -THRESH) {
      if (bias === 'crowded_short') return { label: 'TAPE DOWN', tone: 'caution', note: 'Down, but shorts are crowded — bounce risk.' };
      if (bias === 'long' || bias === 'crowded_long') return { label: 'TAPE DOWN', tone: 'negative', note: 'Down with longs still paying — heavy.' };
      return { label: 'TAPE DOWN', tone: 'negative', note: 'Short-term tape is pushing down.' };
    }
    return { label: 'NEUTRAL', tone: 'neutral', note: 'No clear fast lean right now.' };
  }, [change1m, change3m, coinPositioning, hasCanonicalNegativeState]);

  const simpleCoinRead = useMemo(() => {
    if (!metricsReady) {
      return {
        label: 'WAIT',
        tone: 'neutral',
        headline: 'Not enough live tape yet.',
        supports: buildWarmingSupports(coinLiveRanking),
        blockers: ['The short-term windows are still filling.'],
        upgrade: 'Check again after the next few live updates.',
        invalidation: 'No setup is valid until the data is ready.',
        history: null,
      };
    }

    const score = Number(coinLiveRanking?.live_score ?? 50);
    const evidence = Number(coinLiveRanking?.data_quality ?? 0);
    const observedInputs = Number(coinLiveRanking?.observed_inputs ?? Math.round(evidence * 6 / 100));
    const expectedInputs = Number(coinLiveRanking?.expected_inputs || 6);
    const breadthUp = breadthRead.value;
    const alignedUp = alignmentLabel === 'Aligned Up';
    const alignedDown = alignmentLabel === 'Aligned Down';
    const persistenceGood = ['Dominant', 'Persistent'].includes(coinPriorityEntry?.stateLabel) || persistenceStreak >= 3;
    const persistenceWeak = ['Fading', 'Fragile'].includes(coinPriorityEntry?.stateLabel) || !persistenceGood;
    const breakoutUp = breakoutState === 'Breakout Up' || signalFlags.hasMomentum;
    const reversalRiskCurrent = isReversalRiskCurrent(coinPriorityEntry);
    const hardRisk = signalFlags.hasFakeout || signalFlags.hasReversal || reversalRiskCurrent;
    const historyLabel = coinAlerts.find((alert) => alert?.the_read?.history?.label)?.the_read?.history?.label || null;
    const historyPctMatch = String(historyLabel || '').match(/(\d+(?:\.\d+)?)%/);
    const historyPct = historyPctMatch ? Number(historyPctMatch[1]) : null;
    const historyWeak = Number.isFinite(historyPct) && historyPct < 35;

    const supports = [];
    if (breakoutUp) supports.push('A breakout signal is active.');
    if (volumeConfirms) supports.push('Volume is supporting the move.');
    if (alignedUp) supports.push('The short timeframes agree upward.');
    if (score >= 65) supports.push(`Live strength is ${score}/100.`);
    const liveReasons = Array.isArray(coinLiveRanking?.live_reasons) ? coinLiveRanking.live_reasons : [];
    if (liveReasons.some((reason) => /spot buying/i.test(reason))) supports.push('Real spot buying is present.');
    if (liveReasons.some((reason) => /breaking away/i.test(reason))) supports.push('It is outperforming the wider market.');

    const blockers = [];
    if (alignmentLabel === 'Mixed') blockers.push('The 1m, 3m, and 1h views do not agree.');
    if (alignedDown) blockers.push('Short-term direction is still down.');
    if (persistenceWeak) blockers.push('The move has not held its rank yet.');
    if (!volumeConfirms) blockers.push('Volume has not confirmed the move.');
    if (breadthRead.blocker) blockers.push(breadthRead.blocker);
    if (historyWeak) blockers.push(`Comparable signals only worked ${historyPct}% of the time.`);
    if (evidence > 0 && evidence < 50) blockers.push(`Only ${observedInputs}/${expectedInputs} live inputs are available.`);
    const riskBlocker = computeRiskBlocker(signalFlags, reversalRiskCurrent);
    if (riskBlocker) blockers.push(riskBlocker);

    const shortTermUp = (change1m != null && change1m > 0) && (change3m != null && change3m > 0);
    const label = computePostureLabel({
      score, alignmentLabel, volumeConfirms, persistenceGood, breadthUp,
      historyWeak, hardRisk, breakoutUp, change1m, change3m,
      canonicalState: coinPriorityEntry?.stateLabel,
    });
    const tone = label === 'STAY CLEAR' ? 'negative'
               : label === 'WAIT'       ? 'neutral'
               : 'positive';

    let headline;
    if (label === 'STAY CLEAR') {
      const tapeIsUp = (change3m ?? 0) * 0.6 + (change1m ?? 0) * 0.4 >= 0.15;
      headline = hardRisk && tapeIsUp
        ? 'Short-term tape is moving up, but an active risk warning is overriding the setup.'
        : alignedDown
        ? 'Price is moving down across multiple timeframes.'
        : score < 42
        ? 'Momentum is too weak for a clean setup right now.'
        : 'Risk is stronger than the opportunity right now.';
    } else if (label === 'STRONG SETUP') {
      headline = 'Price, volume, and follow-through are aligned.';
    } else if (label === 'WATCH CLOSE') {
      headline = 'The setup is improving, but still needs a clean hold.';
    } else if (label === 'EARLY SETUP') {
      headline = alignedUp
        ? 'Short-term momentum and breakout evidence are active but still need more confirmation.'
        : 'Short-term momentum, volume, and breakout evidence are aligning before the 1h view has caught up.';
    } else {
      headline = resolveWaitHeadline({ breakoutUp, score });
    }

    let upgrade = 'Wait for the 1m and 3m directions to agree and for the coin to hold its rank on the next updates.';
    if (hardRisk) upgrade = 'Wait for the active risk warning to clear before treating this as a clean setup.';
    else if (!volumeConfirms) upgrade = 'Wait for volume to turn positive and confirm the price move.';
    else if (alignmentLabel === 'Mixed') upgrade = 'Wait for 1m and 3m to point the same way, then hold for at least two updates.';
    else if (!persistenceGood) upgrade = 'Wait for the coin to hold or improve its live rank on the next two updates.';
    else if (breadthUp === null) upgrade = 'Wait for market breadth to become available before treating broad participation as confirmation.';
    else if (breadthUp < 0.45) upgrade = 'Wait for broader market support or unusually strong independent spot buying.';
    else if (label === 'EARLY SETUP') upgrade = 'Watch for the 1h view to turn positive and hold for at least two updates to confirm.';
    else if (label === 'STRONG SETUP') upgrade = 'Favor a controlled pullback or fresh hold; do not chase a sudden extension.';

    return {
      label,
      tone,
      headline,
      supports: supports.slice(0, 3),
      blockers: blockers.slice(0, 4),
      upgrade,
      invalidation: breakoutUp
        ? 'Stop trusting it if the breakout fails, volume fades, or the rank drops sharply.'
        : 'There is no active edge to invalidate yet.',
      history: historyLabel,
    };
  }, [
    metricsReady,
    coinLiveRanking,
    marketPressureSummary,
    breadthRead,
    alignmentLabel,
    coinPriorityEntry,
    persistenceStreak,
    breakoutState,
    signalFlags,
    coinAlerts,
    volumeConfirms,
    change1m,
    change3m,
  ]);

  const coinSupportRail = useMemo(() => ([
    {
      label: 'Alignment',
      value: alignmentLabel,
      tone: alignmentLabel === 'Aligned Up' ? 'positive' : alignmentLabel === 'Aligned Down' ? 'negative' : 'neutral',
      sub: alignmentDetail,
    },
    {
      label: 'Setup',
      value: setupQuality.label,
      tone: setupQuality.tone,
      sub: setupQuality.detail,
    },
    buildPriorityRailItem(coinPriorityEntry, persistenceStreak, 'Rank hold not established yet.'),
    {
      label: 'Updated',
      value: humanTime(lastCoinUpdateTs),
      tone: 'neutral',
      sub: [
        freshAgeMs !== null ? `fresh ${ageLabel(freshAgeMs)}` : 'waiting for next tape sample',
        storedTapeSamples ? `${storedTapeSamples} recent samples shown` : null,
      ].filter(Boolean).join(' · '),
    },
  ]), [alignmentLabel, alignmentDetail, setupQuality, coinPriorityEntry, persistenceStreak, lastCoinUpdateTs, freshAgeMs, storedTapeSamples]);

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
    if (breadthRead.risk) risks.push(breadthRead.risk);
    if (signalFlags.hasFakeout) risks.push('recent fakeout risk is still active');
    if (!risks.length) risks.push('invalidates if the next push fails to hold top cohort rank');
    return risks.slice(0, 4);
  }, [freshAgeMs, volumeConfirms, metricsReady, alignmentLabel, breadthRead, signalFlags]);

  const pulseSupportRail = useMemo(() => ([
    {
      label: 'Setup',
      value: setupQuality.label,
      tone: setupQuality.tone,
      sub: setupQuality.detail,
    },
    buildPriorityRailItem(
      coinPriorityEntry,
      persistenceStreak,
      'This coin has not repeated enough to confirm a rank hold.',
    ),
    {
      label: 'Breadth',
      value: breadthRead.status,
      tone: breadthRead.tone,
      sub: breadthRead.available ? (marketPressureSummary?.label || 'No broad tape label yet.') : 'Broad-market participation is missing.',
    },
    {
      label: 'Trigger',
      value: pulseTrigger,
      tone: !hasCanonicalNegativeState && freshAgeMs !== null && freshAgeMs <= PRIORITY_FRESH_MS ? 'positive' : 'neutral',
      sub: 'Fresh inside 2m. Fade threshold 3.5m.',
    },
  ]), [setupQuality, coinPriorityEntry, persistenceStreak, marketPressureSummary, breadthRead, pulseTrigger, freshAgeMs, hasCanonicalNegativeState]);

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
    {
      label: 'Live rank',
      value: coinLiveRanking ? `#${coinLiveRanking.live_rank} · ${coinLiveRanking.live_score}` : 'Building',
      tone: (coinLiveRanking?.live_score ?? 50) >= 65 ? 'positive' : (coinLiveRanking?.live_score ?? 50) < 45 ? 'negative' : 'neutral',
    },
    { label: 'Attention', value: socialHeatTrend ? (socialHeatTrend === 'rising' ? 'Rising' : socialHeatTrend === 'collapsing' ? 'Fading' : 'Flat') : 'Quiet', tone: socialHeatTrend === 'rising' ? 'positive' : socialHeatTrend === 'collapsing' ? 'negative' : 'neutral' },
    { label: 'Source mix', value: socialSourceLabel || (coinIntel?.events?.items?.length ? 'Events only' : 'Tape only'), tone: 'neutral' },
    { label: 'Feed status', ...computeFeedStatus(coinIntel, coinIntelError) },
  ]), [coinLiveRanking, socialHeatTrend, socialSourceLabel, coinIntel, coinIntelError]);

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
            {coinbaseTradeUrl ? (
              <a
                className="coinbase-trade-cta"
                href={coinbaseTradeUrl}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Trade ${coinSymbol} on Coinbase Advanced`}
                title={`Open ${coinSymbol}-USD on Coinbase Advanced Trade`}
              >
                <span className="coinbase-trade-cta-icon" aria-hidden="true">$</span>
                <span>Trade {coinSymbol}</span>
              </a>
            ) : null}
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
                <div className="tab-empty tab-empty--compact">Choose a coin from the board to load its local state.</div>
              ) : (
                <>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      padding: '0.6rem 0.9rem',
                      marginBottom: 12,
                      border: '1px solid rgba(255,255,255,0.08)',
                      borderRadius: 10,
                      background: 'rgba(255,255,255,0.02)',
                    }}
                  >
                    <span style={{ fontSize: 11, letterSpacing: '0.05em', color: '#8a8a8a', textTransform: 'uppercase' }}>Early read</span>
                    <span style={{ fontSize: 16, fontWeight: 600, color: { positive: '#45ffb3', negative: '#ff6b6b', caution: '#f1b43a', neutral: '#a3a3a3' }[earlyRead.tone] || '#a3a3a3' }}>{earlyRead.label}</span>
                    <span style={{ fontSize: 12.5, color: '#b8b8b8' }}>{earlyRead.note}</span>
                    <span style={{ marginLeft: 'auto', fontSize: 10.5, color: '#6f6f6f', fontStyle: 'italic' }}>fast · unconfirmed</span>
                  </div>

                  {alertBanner ? (
                    <div className="mw-alert-banner" data-tone={alertBanner.tone}>
                      <span className="mw-alert-banner__headline">{alertBanner.headline}</span>
                      <span className="mw-alert-banner__watch">{alertBanner.watchLine}</span>
                    </div>
                  ) : null}

                  <section className={`cp-simple-read cp-simple-read--${simpleCoinRead.tone}`}>
                    <div className="cp-simple-read__topline">
                      <span>{coinSymbol} · RIGHT NOW</span>
                      <span>
                        {coinLiveRanking
                          ? `Tape rank #${coinLiveRanking.live_rank}/${coinLiveRanking.universe_size} · Tape strength ${coinLiveRanking.live_score}/100 · ${coinLiveRanking.observed_inputs ?? Math.round((coinLiveRanking.data_quality || 0) * 6 / 100)}/${coinLiveRanking.expected_inputs || 6} inputs live`
                          : `updated ${humanTime(lastCoinUpdateTs)}`}
                      </span>
                    </div>
                    <div className="cp-simple-read__answer">{simpleCoinRead.label}</div>
                    <h2>{simpleCoinRead.headline}</h2>

                    <div className="cp-simple-read__columns">
                      <div>
                        <h3>What helps</h3>
                        {simpleCoinRead.supports.length ? (
                          <ul>{simpleCoinRead.supports.map((item) => <li key={item}>{item}</li>)}</ul>
                        ) : (
                          <p>Nothing meaningful is confirming the setup yet.</p>
                        )}
                      </div>
                      <div>
                        <h3>What blocks it</h3>
                        {simpleCoinRead.blockers.length ? (
                          <ul>{simpleCoinRead.blockers.map((item) => <li key={item}>{item}</li>)}</ul>
                        ) : (
                          <p>No major blocker is active.</p>
                        )}
                      </div>
                    </div>

                    <div className="cp-simple-read__next">
                      <span>WHAT WOULD IMPROVE IT</span>
                      <strong>{simpleCoinRead.upgrade}</strong>
                    </div>
                    <div className="cp-simple-read__fails">
                      <span>WHEN TO STOP TRUSTING IT</span>
                      <strong>{simpleCoinRead.invalidation}</strong>
                    </div>
                    {simpleCoinRead.history ? (
                      <div className="cp-simple-read__history">History: {simpleCoinRead.history}</div>
                    ) : null}
                  </section>

                  <details className="cp-evidence-drawer">
                    <summary>See the evidence</summary>
                    <div className="cp-evidence-drawer__body">
                      <SupportRail items={coinSupportRail} />

                      <div className="section-header">
                        <h3>Source health</h3>
                        <p className="section-desc">Unavailable sources are excluded; they are never filled with neutral guesses.</p>
                      </div>
                      <SupportRail items={sourceHealth} />

                      {coinBadges.length ? (
                        <div className="cp-badge-rail">
                          {coinBadges.map((badge) => (
                            <span key={badge.label} className={`cp-badge cp-badge--${badge.tone}`}>{badge.label}</span>
                          ))}
                        </div>
                      ) : null}

                      {coinInsightsLoading && !coinInsights ? (
                        <div className="coin-history-note coin-history-note--compact">Advanced insights are still loading.</div>
                      ) : null}
                      {coinInsightsError ? (
                        <div className="coin-history-note coin-history-note--compact error mw-fetch-note">Some supporting evidence is temporarily unavailable.</div>
                      ) : null}

                      <AlertsTab
                        filterSymbol={coinSymbol}
                        compact
                        hideHeader
                        hideFoot
                        emptyCopy={coinEvidenceEmptyCopy}
                      />
                    </div>
                  </details>

                  <details
                    className="cp-evidence-drawer cp-chart-drawer mw-coin-chart-block"
                    open={chartDrawerOpen}
                    onToggle={(e) => setChartDrawerOpen(e.currentTarget.open)}
                  >
                    <summary>Chart &amp; Read</summary>
                    <div className="cp-evidence-drawer__body">
                      {chartEventContext ? (
                        <ChartReadPanel
                          data={chartRead}
                          loading={chartReadLoading}
                          error={chartReadError}
                        />
                      ) : null}
                      <div className="section-header">
                        <p className="section-desc">{chartEventContext ? 'Chart below for reference.' : 'Chart first, plain-English read below.'}</p>
                      <div className="mini-toggle" role="group" aria-label="Chart source">
                        {['auto', 'coinbase', 'binance'].map((opt) => (
                          <button
                            key={opt}
                            type="button"
                            className={`mini-toggle-btn ${chartExchange === opt ? 'active' : ''}`}
                            onClick={() => setChartExchange(opt)}
                            aria-pressed={chartExchange === opt}
                          >
                            {opt === 'auto' ? 'Auto' : opt === 'coinbase' ? 'Coinbase' : 'Binance'}
                          </button>
                        ))}
                        <span className="mini-toggle-label">Using {tvResolved.source}</span>
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
                      {!chartEventContext ? (
                        <ChartReadPanel
                          data={chartRead}
                          loading={chartReadLoading}
                          error={chartReadError}
                        />
                      ) : null}
                    </div>
                  </details>

                  <CoinOutcomeHistory
                    data={coinHistory}
                    loading={coinHistoryLoading}
                    error={coinHistoryError}
                    symbol={coinSymbol}
                  />

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
                <div className="tab-empty tab-empty--compact">Choose a coin from the board to load its tactical read.</div>
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
                    <article className={`cp-quick-read cp-quick-read--${quickBuyRead.tone}`}>
                      <div className="cp-quick-read__main">
                        <span className="cp-quick-read__eyebrow">Quick Buy Read</span>
                        <strong className="cp-quick-read__label">{quickBuyRead.label}</strong>
                        <p>{quickBuyRead.intent}</p>
                      </div>
                      <div className="cp-quick-read__checks">
                        <span>{quickBuyRead.confirmation}</span>
                        <span>{quickBuyRead.sentiment || 'sentiment/attention unavailable'}</span>
                        <span>{quickBuyRead.reason}</span>
                      </div>
                    </article>
                  </section>

                  <section className="cp-section">
                    <SupportRail items={pulseSupportRail} />
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
                        <div className="cp-note-card__title">Risk / Trigger</div>
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
            <section className="tab-panel active cp-intel-panel" role="tabpanel">
              {!coinSymbol ? (
                <div className="tab-empty tab-empty--compact">Select a coin to load external context.</div>
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
                    <SupportRail items={intelSupport.map((item) => ({
                      ...item,
                      sub:
                        item.label === 'Trust level'
                          ? 'Plumbing is secondary. Use this only to calibrate trust.'
                          : item.label === 'Source mix'
                            ? 'What kind of context is actually feeding this read.'
                            : item.label === 'Attention'
                              ? 'Whether the move has external eyes on it.'
                              : 'Last external refresh.',
                    }))} />
                  </section>

                  <div className="info-section">
                    <div className="section-header">
                      <h3>Positioning</h3>
                      <p className="section-desc">Derivatives funding &amp; open interest (Hyperliquid). Context, not a signal.</p>
                    </div>
                    {coinPositioningLoading && !coinPositioning ? (
                      <div className="tab-empty tab-empty--compact">Loading positioning...</div>
                    ) : (
                      <CoinPositioning positioning={coinPositioning} />
                    )}
                  </div>

                  {coinIntelLoading && !coinIntel ? <div className="coin-history-note coin-history-note--compact">Loading coin intel...</div> : null}
                  {coinIntelError ? (
                    <div className="coin-history-note coin-history-note--compact error mw-fetch-note">External context is degraded. The read below is tape-led until outside sources reconnect.</div>
                  ) : null}

                  <div className="info-section">
                    <div className="section-header">
                      <h3>Events</h3>
                      <p className="section-desc">External catalyst evidence. If this is empty, the move is probably tape-led.</p>
                    </div>
                    {coinIntel?.events?.items?.length ? (
                      <div className="feed-list cp-intel-feed">
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
                      <div className="tab-empty tab-empty--compact">No meaningful external driver detected. Move appears tape-led.</div>
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
                          {socialTrendingRank !== null && socialTrendingRank > 0 ? (
                            <div className="mw-chip positive">
                              <span>CoinGecko Trending</span>
                              <strong>#{Math.round(socialTrendingRank)}</strong>
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
                          <div className="coin-history-note">
                            Community proxy only: this is audience/search/context data, not direct Reddit/X sentiment.
                            {socialTrendingSource ? ` Trending source: ${socialTrendingSource}.` : ''}
                          </div>
                        ) : null}
                        {socialActionLine ? <div className="coin-history-note mw-intel-action">{socialActionLine}</div> : null}
                      </>
                    ) : (
                      <div className="tab-empty tab-empty--compact">No meaningful external context detected. Treat this as tape-first until something confirms.</div>
                    )}
                  </div>

                  <div className="info-section">
                    <div className="section-header">
                      <h3>Social Pulse</h3>
                      <p className="section-desc">Recent external items, shown only as supporting evidence.</p>
                    </div>
                    {coinIntel?.social?.items?.length ? (
                      <div className="feed-list cp-intel-feed">
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
                      <div className="tab-empty tab-empty--compact">No social items available right now.</div>
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
              Coinbase live tape
              {storedTapeSamples ? ` · latest ${storedTapeSamples} shown` : ''}
              {tapeIsPersistent && Number(coinInsights?.history?.retention_seconds) ? ` · ${Math.round(Number(coinInsights.history.retention_seconds) / 3600)}h retained` : ''}
              {' · Coin scope only'}
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
