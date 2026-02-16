import { useMemo, useState, useEffect } from "react";
import { useData } from "../context/DataContext";
import { API_ENDPOINTS, fetchData } from "../api";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";
import { getMarketPressure } from "../utils/marketPressure";
import "../styles/alerts-tab.css";

const COIN_ALERT_REFRESH_MS = 60000;

const TYPE_LABEL = {
  moonshot: "MOONSHOT",
  crater: "CRATER",
  breakout: "BREAKOUT",
  dump: "DUMP",
  whale_move: "WHALE",
  stealth_move: "STEALTH",
  divergence: "DIVERGENCE",
  impulse_1m: "MOVE",
  impulse_3m: "MOVE",
  coin_fomo: "COIN FOMO",
  coin_breadth_thrust: "BREADTH THRUST",
  coin_breadth_failure: "BREADTH FAILURE",
  coin_reversal_up: "REVERSAL UP",
  coin_reversal_down: "REVERSAL DOWN",
  coin_fakeout: "FAKEOUT",
  coin_persistent_gainer: "PERSIST GAINER",
  coin_persistent_loser: "PERSIST LOSER",
  coin_volatility_expansion: "VOL EXPANSION",
  coin_liquidity_shock: "LIQ SHOCK",
  coin_trend_break_up: "TREND BREAK UP",
  coin_trend_break_down: "TREND BREAK DOWN",
  coin_squeeze_break: "SQUEEZE BREAK",
  coin_exhaustion_top: "EXHAUSTION TOP",
  coin_exhaustion_bottom: "EXHAUSTION BOTTOM",
  social_spike_1h: "SOCIAL SPIKE",
  engagement_surge_1h: "ENGAGEMENT SURGE",
  social_divergence: "SOCIAL DIVERGENCE",
  social_pulse: "SOCIAL PULSE",
  listing: "LISTING",
  delisting: "DELISTING",
  unlock: "UNLOCK",
  upgrade: "UPGRADE",
  hack_or_exploit: "HACK / EXPLOIT",
  governance_vote: "GOVERNANCE",
  partnership: "PARTNERSHIP",
  news_positive: "NEWS POSITIVE",
  news_negative: "NEWS NEGATIVE",
  external_event: "EXTERNAL EVENT",
  news_confirmed_breakout: "NEWS CONFIRMED",
  social_confirmed_momentum: "SOCIAL CONFIRMED",
  event_confirmed_volume: "EVENT CONFIRMED",
  fomo: "FOMO",
  fomo_alert: "FOMO",
  fear: "FEAR",
  fear_alert: "FEAR",
};

const TYPE_HELP = {
  MOONSHOT: "Fast surge",
  CRATER: "Fast drop",
  BREAKOUT: "Trend shift",
  DUMP: "Strong sell pressure",
  WHALE: "Unusual volume spike",
  STEALTH: "Volume warming quietly",
  DIVERGENCE: "Price vs sentiment mismatch",
  "COIN FOMO": "Coin acceleration with market heat context",
  "BREADTH THRUST": "Coin strength confirmed by broad participation",
  "BREADTH FAILURE": "Coin weakness in weak market breadth",
  "REVERSAL UP": "Coin reversed from sell pressure to buy pressure",
  "REVERSAL DOWN": "Coin reversed from buy pressure to sell pressure",
  FAKEOUT: "Breakout trap rejected quickly",
  "PERSIST GAINER": "Coin stayed in sustained upside streak",
  "PERSIST LOSER": "Coin stayed in sustained downside streak",
  "VOL EXPANSION": "Coin volatility expanded vs recent baseline",
  "LIQ SHOCK": "Volume surged while price stayed muted",
  "TREND BREAK UP": "Fast/slow trend crossover with volume support",
  "TREND BREAK DOWN": "Fast/slow trend rollover with volume support",
  "SQUEEZE BREAK": "Compression regime broke into a sharp move",
  "EXHAUSTION TOP": "Upside run lost energy and flipped",
  "EXHAUSTION BOTTOM": "Downside run lost energy and snapped back",
  "SOCIAL SPIKE": "Social attention accelerated quickly",
  "ENGAGEMENT SURGE": "Participation expanded beyond baseline",
  "SOCIAL DIVERGENCE": "Social direction disagrees with tape direction",
  "SOCIAL PULSE": "Social timeline activity is live",
  LISTING: "Major listing catalyst detected",
  DELISTING: "Delisting risk or removal notice",
  UNLOCK: "Token unlock / vesting pressure",
  UPGRADE: "Protocol upgrade event",
  "HACK / EXPLOIT": "Security incident / exploit risk",
  GOVERNANCE: "Governance proposal or vote event",
  PARTNERSHIP: "Partnership or integration event",
  "NEWS POSITIVE": "Bullish external news catalyst",
  "NEWS NEGATIVE": "Bearish external news catalyst",
  "EXTERNAL EVENT": "External event without directional bias",
  "NEWS CONFIRMED": "News and tape action aligned",
  "SOCIAL CONFIRMED": "Social momentum and tape aligned",
  "EVENT CONFIRMED": "Event and volume expansion aligned",
  MOVE: "Short-term move",
  FOMO: "Chasing behavior",
  FEAR: "Risk-off behavior",
};

const ALERT_TABS = [
  { key: "ALL", label: "All" },
  { key: "MOONSHOT", label: "Moonshot" },
  { key: "BREAKOUT", label: "Breakout" },
  { key: "CRATER", label: "Crater" },
  { key: "WHALE", label: "Whale" },
  { key: "STEALTH", label: "Stealth" },
  { key: "DUMP", label: "Dump" },
  { key: "COIN_FOMO", label: "Coin Fomo" },
  { key: "THRUST", label: "Thrust" },
  { key: "FAILURE", label: "Failure" },
  { key: "REVERSAL", label: "Reversal" },
  { key: "FAKEOUT", label: "Fakeout" },
  { key: "PERSIST", label: "Persist" },
  { key: "VOLX", label: "VolX" },
  { key: "LIQ", label: "Liq Shock" },
  { key: "TREND", label: "Trend Break" },
  { key: "SQUEEZE", label: "Squeeze" },
  { key: "EXHAUST", label: "Exhaustion" },
  { key: "SOCIAL", label: "Social" },
  { key: "NEWS", label: "News" },
  { key: "EVENTS", label: "Events" },
  { key: "DERIV", label: "Derivatives" },
  { key: "FOMO", label: "Fomo" },
  { key: "FEAR", label: "Fear" },
  { key: "DIVERGENCE", label: "Divergence" },
  { key: "IMPULSE", label: "Impulse" },
];

const marketMoodKey = (a) => {
  const mood = String(a?.evidence?.mood || a?.direction || "").toLowerCase();
  return mood === "fear" ? "FEAR" : "FOMO";
};

const tabKeyForAlert = (a) => {
  const raw = String(a?.type_key || a?.type || "").toLowerCase();
  if (!raw) return "ALL";
  if (raw.includes("social_") || raw.includes("engagement") || raw.includes("sentiment")) return "SOCIAL";
  if (raw.includes("news_")) return "NEWS";
  if (raw.includes("listing") || raw.includes("delisting") || raw.includes("unlock") || raw.includes("upgrade") || raw.includes("governance") || raw.includes("partnership") || raw.includes("hack") || raw.includes("external_event")) return "EVENTS";
  if (raw.includes("funding") || raw.includes("open_interest") || raw.includes("liquidation") || raw.includes("derivative") || raw === "oi_spike") return "DERIV";
  if (raw.includes("moonshot")) return "MOONSHOT";
  if (raw.includes("breakout")) return "BREAKOUT";
  if (raw.includes("crater")) return "CRATER";
  if (raw.includes("whale")) return "WHALE";
  if (raw.includes("stealth")) return "STEALTH";
  if (raw.includes("dump")) return "DUMP";
  if (raw.includes("coin_fomo")) return "COIN_FOMO";
  if (raw.includes("coin_breadth_thrust")) return "THRUST";
  if (raw.includes("coin_breadth_failure")) return "FAILURE";
  if (raw.includes("coin_reversal")) return "REVERSAL";
  if (raw.includes("coin_fakeout")) return "FAKEOUT";
  if (raw.includes("coin_persistent")) return "PERSIST";
  if (raw.includes("coin_volatility_expansion")) return "VOLX";
  if (raw.includes("coin_liquidity_shock")) return "LIQ";
  if (raw.includes("coin_trend_break")) return "TREND";
  if (raw.includes("coin_squeeze_break")) return "SQUEEZE";
  if (raw.includes("coin_exhaustion")) return "EXHAUST";
  if (raw.includes("fear") || raw.includes("fomo")) return marketMoodKey(a);
  if (raw.includes("divergence")) return "DIVERGENCE";
  if (raw.includes("impulse")) return "IMPULSE";
  return "ALL";
};

const SEV_RANK = { critical: 5, high: 4, medium: 3, low: 2, info: 1 };

const toUpperType = (alert) => {
  const k = String(alert?.type_key || alert?.type || "").toLowerCase();
  if (k.startsWith("coin_")) {
    return TYPE_LABEL[k] || k.toUpperCase();
  }
  if (k.includes("fear") || k.includes("fomo")) {
    return marketMoodKey(alert);
  }
  return TYPE_LABEL[k] || k.toUpperCase() || "ALERT";
};

const pickTsMs = (a) =>
  (Number.isFinite(a?.event_ts_ms) && a.event_ts_ms) ||
  (Number.isFinite(a?.ts_ms) && a.ts_ms) ||
  (Number.isFinite(a?.event_ts) && a.event_ts) ||
  (Number.isFinite(a?.ts) && a.ts) ||
  (Number.isFinite(a?.when) && a.when) ||
  (Number.isFinite(a?.date) && a.date) ||
  (() => {
    const parsed = Date.parse(String(a?.event_ts || a?.ts || a?.when || a?.date || ""));
    return Number.isFinite(parsed) ? parsed : null;
  })() ||
  null;

const ageLabel = (ms) => {
  if (!Number.isFinite(ms) || ms < 0) return "\u2014";
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h`;
  const d = Math.floor(h / 24);
  return `${d}d`;
};

const pickPct = (a) => {
  const ev = a?.evidence || {};
  const pct =
    ev.pct_1m ??
    ev.pct_3m ??
    ev.pct_5m ??
    ev.pct_15m ??
    ev.pct_1h ??
    a?.pct ??
    a?.magnitude ??
    null;
  const n = Number(pct);
  return Number.isFinite(n) ? n : null;
};

const pickVolPct = (a) => {
  const ev = a?.evidence || {};
  const v = ev.volume_change_1h_pct ?? ev.vol_change_1h_pct ?? ev.vol_pct ?? null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

const toProductId = (a) => {
  let p = String(a?.product_id || a?.symbol || "").trim().toUpperCase();
  if (!p) return "";
  if (!p.includes("-")) p = `${p}-USD`;
  return p;
};

const alertSymbol = (a) =>
  String(a?.symbol || a?.product_id || "").toUpperCase().replace(/-USD$|-USDT$|-PERP$/i, "");

const moodFromHeat = (heat) => {
  if (heat >= 67) return { mood: "Bullish", tone: "bull", detail: "Buy pressure is leading right now." };
  if (heat <= 33) return { mood: "Bearish", tone: "bear", detail: "Sell pressure is leading right now." };
  return { mood: "Neutral", tone: "neutral", detail: "Pressure is balanced. Signals may chop." };
};

const confidenceFromStale = (priceStale, volStale) => {
  const p = Number.isFinite(priceStale) ? priceStale : null;
  const v = Number.isFinite(volStale) ? volStale : null;
  const worst = Math.max(p ?? 0, v ?? 0);
  if (p == null && v == null) return { label: "Unknown", tone: "unknown", hint: "Data freshness unavailable." };
  if (worst <= 6) return { label: "High", tone: "high", hint: `Data is ${worst.toFixed(1)}s old.` };
  if (worst <= 15) return { label: "Medium", tone: "med", hint: `Data is ${worst.toFixed(1)}s old.` };
  return { label: "Low", tone: "low", hint: `Data is ${worst.toFixed(1)}s old.` };
};

function MarketMoodCard({ meta }) {
  const mp = getMarketPressure({ market_pressure: meta?.market_pressure });
  const heat = Number(mp.index ?? 50);

  const stale = meta?.stale_seconds || {};
  const priceStale = Number(stale?.price);
  const volStale = Number(stale?.volume);

  const { mood, tone, detail } = moodFromHeat(heat);
  const confidence = confidenceFromStale(priceStale, volStale);

  return (
    <div className="bh-pressure-card" data-tone={tone}>
      <div className="bh-pressure-toprow">
        <div className="bh-pressure-title">
          <span className="bh-mood-dot" aria-hidden="true" />
          Market Mood
        </div>
        <div className="bh-pressure-label">{mood}</div>
      </div>

      <div className="bh-pressure-sub">{detail}</div>

      <div className="bh-pressure-track" aria-label="Market mood gauge">
        <div className="bh-pressure-fill" style={{ width: `${heat}%` }} />
      </div>

      <div className="bh-pressure-row">
        <div className="bh-pressure-score">{heat.toFixed(0)} / 100</div>
        <div className="bh-pressure-confidence" data-tone={confidence.tone}>
          Confidence: {confidence.label}
        </div>
      </div>

      <div className="bh-pressure-fresh">
        <span>Price: {Number.isFinite(priceStale) ? `${priceStale.toFixed(1)}s old` : "\u2014"}</span>
        <span>Volume: {Number.isFinite(volStale) ? `${volStale.toFixed(1)}s old` : "\u2014"}</span>
      </div>

      <div className="bh-pressure-hint">{confidence.hint}</div>
    </div>
  );
}

function ProofFooter({ meta, activeCount, recentCount }) {
  const stale = meta?.stale_seconds || {};
  const priceStale = Number(stale?.price);
  const volStale = Number(stale?.volume);

  const healthy =
    Number.isFinite(priceStale) && priceStale < 30 &&
    Number.isFinite(volStale) && volStale < 60;

  return (
    <div className="bh-proof-footer">
      <div className="bh-proof-item">
        <span className="bh-proof-key">Signals healthy</span>
        <span className={`bh-proof-val ${healthy ? "bh-proof--ok" : "bh-proof--warn"}`}>
          {healthy ? "Yes" : "Degraded"}
        </span>
      </div>
      <div className="bh-proof-item">
        <span className="bh-proof-key">Active</span>
        <span className="bh-proof-val">{activeCount}</span>
      </div>
      <div className="bh-proof-item">
        <span className="bh-proof-key">Recent</span>
        <span className="bh-proof-val">{recentCount}</span>
      </div>
      <div className="bh-proof-item">
        <span className="bh-proof-key">Data age</span>
        <span className="bh-proof-val">
          price {Number.isFinite(priceStale) ? `${priceStale.toFixed(0)}s` : "\u2014"},
          vol {Number.isFinite(volStale) ? `${volStale.toFixed(0)}s` : "\u2014"}
        </span>
      </div>
    </div>
  );
}

function SignalRow({ a, nowMs }) {
  const type = toUpperType(a);
  const sev = String(a?.severity || "info").toLowerCase();
  const promotion = String(a?.promotion || "").toUpperCase();
  const sourceLabel = String(a?.source || "")
    .trim()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (s) => s.toUpperCase());
  const sym = String(a?.product_id || a?.symbol || "").toUpperCase().replace("-USD", "");
  const ts = pickTsMs(a);
  const age = ts ? ageLabel(nowMs - ts) : "\u2014";
  const windowLabel = String(a?.window || a?.evidence?.window || "").trim();

  // Build clean message without repeating coin name
  let rawMsg = String(a?.message || a?.title || TYPE_HELP[type] || "")
    .replace(/\s+/g, " ")
    .trim();
  // Strip leading "SYMBOL:" or "SYMBOL " patterns
  rawMsg = rawMsg.replace(new RegExp(`^${sym}[:\\s]+`, 'i'), "");
  const detail = rawMsg || TYPE_HELP[type] || "Signal detected";

  const pct = pickPct(a);
  const volPct = pickVolPct(a);

  const pctText = pct == null ? "" : `${pct > 0 ? "+" : ""}${pct.toFixed(Math.abs(pct) < 5 ? 3 : 2)}%`;
  const volText = volPct == null ? "" : `Vol ${volPct > 0 ? "+" : ""}${volPct.toFixed(0)}%`;

  const url = a?.url || a?.trade_url || coinbaseSpotUrl({ product_id: toProductId(a), symbol: a?.symbol });
  const cls = tabKeyForAlert(a);

  // Determine direction for color coding
  const direction = pct == null ? "neutral" : pct > 0 ? "up" : "down";

  return (
    <div
      className="bh-signal-row"
      data-sev={sev}
      data-class={cls.toLowerCase()}
      data-direction={direction}
      role="button"
      tabIndex={0}
      onClick={() => url && window.open(url, "_blank", "noopener,noreferrer")}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          url && window.open(url, "_blank", "noopener,noreferrer");
        }
      }}
      title={TYPE_HELP[type] ? `${type}: ${TYPE_HELP[type]}` : type}
    >
      <div className="bh-signal-main">
        <div className="bh-signal-meta">
          <span className="bh-signal-type">{type}</span>
          {windowLabel ? <span className="bh-signal-window">{windowLabel}</span> : null}
          <span className="bh-signal-sev" data-sev={sev}>{String(a?.severity || "INFO").toUpperCase()}</span>
          {promotion ? <span className="bh-signal-promo" data-promo={promotion}>{promotion}</span> : null}
          {sourceLabel ? <span className="bh-signal-source">{sourceLabel}</span> : null}
          <span className="bh-signal-age">{age}</span>
        </div>

        <div className="bh-signal-ticker">{sym || "\u2014"}</div>

        <div className="bh-signal-msg">{detail}</div>

        <div className="bh-signal-metrics">
          {pctText ? <span className="bh-metric" data-direction={direction}>{pctText}</span> : null}
          {volText ? <span className="bh-metric bh-metric--vol">{volText}</span> : null}
        </div>
      </div>
    </div>
  );
}

export default function AlertsTab({ filterSymbol = null, compact = false }) {
  const { activeAlerts = [], alertsRecent = [], alertsMeta = {} } = useData() || {};
  const forcedCoin = useMemo(() => {
    const raw = String(filterSymbol || "").toUpperCase().replace(/-USD$|-USDT$|-PERP$/i, "");
    return raw || null;
  }, [filterSymbol]);

  const [feed, setFeed] = useState("ACTIVE");
  const [typeTab, setTypeTab] = useState("ALL");
  const [sev, setSev] = useState("ALL");
  const [sort, setSort] = useState(() => "IMPORTANCE");
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [showHelp, setShowHelp] = useState(false);
  // Default to the full market stream; symbol-specific filtering is user-driven.
  const [coinFilter, setCoinFilter] = useState(() => forcedCoin || "ALL");
  const [coinAlertsPayload, setCoinAlertsPayload] = useState(() => ({
    active: [],
    recent: [],
    meta: {},
    status: "offline",
    sourcesUsed: [],
  }));
  const [coinAlertsLoading, setCoinAlertsLoading] = useState(false);
  const [coinAlertsError, setCoinAlertsError] = useState(null);
  const [coinAlertsHydrated, setCoinAlertsHydrated] = useState(false);

  useEffect(() => {
    if (!forcedCoin) return;
    setCoinFilter(forcedCoin);
  }, [forcedCoin]);

  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    setSort(feed === "ACTIVE" ? "IMPORTANCE" : "TIME");
  }, [feed]);

  useEffect(() => {
    if (!forcedCoin) {
      setCoinAlertsPayload({
        active: [],
        recent: [],
        meta: {},
        status: "offline",
        sourcesUsed: [],
      });
      setCoinAlertsLoading(false);
      setCoinAlertsError(null);
      setCoinAlertsHydrated(false);
      return undefined;
    }

    let cancelled = false;
    const load = async (silent = false) => {
      if (cancelled) return;
      if (!silent) setCoinAlertsLoading(true);
      try {
        const endpoint = API_ENDPOINTS.coinAlerts
          ? API_ENDPOINTS.coinAlerts(forcedCoin)
          : `/api/coin-alerts?symbol=${encodeURIComponent(forcedCoin)}`;
        const payload = await fetchData(endpoint);
        if (cancelled) return;
        const recent = Array.isArray(payload?.recent)
          ? payload.recent
          : Array.isArray(payload?.items)
            ? payload.items
            : [];
        const active = Array.isArray(payload?.active) ? payload.active : [];
        const meta = payload?.meta && typeof payload.meta === "object" ? payload.meta : {};
        const sourcesUsed = Array.isArray(payload?.sources_used)
          ? payload.sources_used
          : Array.isArray(payload?.sourcesUsed)
            ? payload.sourcesUsed
            : [];
        setCoinAlertsPayload({
          active,
          recent,
          meta,
          status: String(payload?.status || "offline"),
          sourcesUsed: sourcesUsed.map((src) => String(src || "").trim()).filter(Boolean),
        });
        setCoinAlertsError(null);
        setCoinAlertsHydrated(true);
      } catch (err) {
        if (cancelled) return;
        setCoinAlertsError(String(err?.message || err || "Coin alerts unavailable"));
      } finally {
        if (!silent && !cancelled) setCoinAlertsLoading(false);
      }
    };

    load(false);
    const id = window.setInterval(() => load(true), COIN_ALERT_REFRESH_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [forcedCoin]);

  const fallbackForcedActive = useMemo(() => {
    if (!forcedCoin) return [];
    return (Array.isArray(activeAlerts) ? activeAlerts : []).filter((a) => alertSymbol(a) === forcedCoin);
  }, [activeAlerts, forcedCoin]);

  const fallbackForcedRecent = useMemo(() => {
    if (!forcedCoin) return [];
    return (Array.isArray(alertsRecent) ? alertsRecent : []).filter((a) => alertSymbol(a) === forcedCoin);
  }, [alertsRecent, forcedCoin]);

  const effectiveActiveAlerts = useMemo(() => {
    if (!forcedCoin) return Array.isArray(activeAlerts) ? activeAlerts : [];
    return coinAlertsHydrated ? coinAlertsPayload.active : fallbackForcedActive;
  }, [forcedCoin, activeAlerts, coinAlertsHydrated, coinAlertsPayload.active, fallbackForcedActive]);

  const effectiveRecentAlerts = useMemo(() => {
    if (!forcedCoin) return Array.isArray(alertsRecent) ? alertsRecent : [];
    return coinAlertsHydrated ? coinAlertsPayload.recent : fallbackForcedRecent;
  }, [forcedCoin, alertsRecent, coinAlertsHydrated, coinAlertsPayload.recent, fallbackForcedRecent]);

  const effectiveMeta = useMemo(() => {
    if (forcedCoin && coinAlertsHydrated) {
      return coinAlertsPayload.meta || {};
    }
    return alertsMeta || {};
  }, [forcedCoin, coinAlertsHydrated, coinAlertsPayload.meta, alertsMeta]);

  const source = feed === "ACTIVE" ? effectiveActiveAlerts : effectiveRecentAlerts;

  // Build coin options from available alerts
  const coinOptions = useMemo(() => {
    if (forcedCoin) return [forcedCoin];
    const set = new Set(["ALL"]);
    for (const a of alertsRecent || []) {
      const s = alertSymbol(a);
      if (s) set.add(s);
    }
    for (const a of activeAlerts || []) {
      const s = alertSymbol(a);
      if (s) set.add(s);
    }
    return Array.from(set).sort();
  }, [forcedCoin, alertsRecent, activeAlerts]);

  const forcedFeedStatus = useMemo(() => {
    if (!forcedCoin) return null;
    if (coinAlertsLoading && !coinAlertsHydrated) return "Loading unified coin alerts...";
    if (coinAlertsError) return "Unified coin alerts unavailable. Showing tape feed fallback.";
    if (!coinAlertsHydrated) return "Syncing coin alerts...";
    const src = coinAlertsPayload.sourcesUsed || [];
    if (src.length > 0) return `Sources: ${src.join(" · ")}`;
    return null;
  }, [forcedCoin, coinAlertsLoading, coinAlertsHydrated, coinAlertsError, coinAlertsPayload.sourcesUsed]);

  const rows = useMemo(() => {
    let out = Array.isArray(source) ? source : [];

    // Coin filter
    const effectiveCoinFilter = forcedCoin || coinFilter;
    if (effectiveCoinFilter !== "ALL") {
      out = out.filter((a) => alertSymbol(a) === effectiveCoinFilter);
    }

    if (typeTab !== "ALL") {
      out = out.filter((a) => tabKeyForAlert(a) === typeTab);
    }

    // Urgency filter
    if (sev !== "ALL") out = out.filter((a) => String(a?.severity || "info").toUpperCase() === sev);

    // Sort
    if (sort === "URGENCY") {
      out = [...out].sort((a, b) =>
        (SEV_RANK[String(b?.severity || "info").toLowerCase()] || 0) -
        (SEV_RANK[String(a?.severity || "info").toLowerCase()] || 0)
      );
    } else if (sort === "MAGNITUDE") {
      out = [...out].sort((a, b) => Math.abs(pickPct(b) ?? 0) - Math.abs(pickPct(a) ?? 0));
    } else if (sort === "TIME") {
      out = [...out].sort((a, b) => (pickTsMs(b) || 0) - (pickTsMs(a) || 0));
    } else {
      // IMPORTANCE: Active is already score-ordered backend-side
      if (feed === "ACTIVE") return out;
      out = [...out].sort((a, b) => {
        const sb = (SEV_RANK[String(b?.severity || "info").toLowerCase()] || 0);
        const sa = (SEV_RANK[String(a?.severity || "info").toLowerCase()] || 0);
        if (sb !== sa) return sb - sa;
        return (pickTsMs(b) || 0) - (pickTsMs(a) || 0);
      });
    }

    return out;
  }, [source, forcedCoin, coinFilter, typeTab, sev, sort, feed]);

  return (
    <div className={`bh-alerts-tab ${compact ? "bh-alerts-tab--compact" : ""}`}>
      <div className="bh-alerts-layout">
        {!compact ? <MarketMoodCard meta={effectiveMeta} /> : null}

        <div className="bh-alerts-feed">
          <div className="bh-alerts-feed-head">
            <div className="bh-alerts-feed-title">{forcedCoin ? `${forcedCoin} Signals` : "Signals"}</div>

            {!compact ? (
              <div className="bh-alerts-toggle" role="tablist" aria-label="Signals feed">
                <button
                  className={`bh-toggle-btn ${feed === "ACTIVE" ? "active" : ""}`}
                  onClick={() => setFeed("ACTIVE")}
                  type="button"
                >
                  Active
                </button>
                <button
                  className={`bh-toggle-btn ${feed === "RECENT" ? "active" : ""}`}
                  onClick={() => setFeed("RECENT")}
                  type="button"
                >
                  Recent
                </button>
              </div>
            ) : null}
          </div>

          {forcedFeedStatus ? (
            <div className={`bh-alerts-inline-note ${coinAlertsError ? "bh-alerts-inline-note--warn" : ""}`}>
              {forcedFeedStatus}
            </div>
          ) : null}

          {!compact ? (
            <div className="bh-alerts-type-tabs" role="tablist" aria-label="Signal classes">
              {ALERT_TABS.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  className={`bh-type-tab ${typeTab === tab.key ? "active" : ""}`}
                  onClick={() => setTypeTab(tab.key)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          ) : null}

          {!compact ? (
            <div className="bh-alerts-tab-controls">
              <div className="bh-control">
                <div className="bh-control-label">Urgency</div>
                <select className="bh-control-select" value={sev} onChange={(e) => setSev(e.target.value)}>
                  {["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"].map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>

              <div className="bh-control">
                <div className="bh-control-label">Order By</div>
                <select className="bh-control-select" value={sort} onChange={(e) => setSort(e.target.value)}>
                  <option value="IMPORTANCE">Most Important</option>
                  <option value="TIME">Newest</option>
                  <option value="URGENCY">Urgency</option>
                  <option value="MAGNITUDE">Biggest Move</option>
                </select>
              </div>

              {!forcedCoin ? (
                <div className="bh-control">
                  <div className="bh-control-label">Coin</div>
                  <select className="bh-control-select" value={coinFilter} onChange={(e) => setCoinFilter(e.target.value)}>
                    {coinOptions.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
              ) : null}
            </div>
          ) : null}

          {!compact ? (
            <div className="bh-alerts-help-bar">
              <button
                type="button"
                className="bh-help-toggle"
                onClick={() => setShowHelp((v) => !v)}
                aria-expanded={showHelp}
              >
                {showHelp ? "Hide guide" : "Show guide"}
              </button>
            </div>
          ) : null}

          {!compact && showHelp ? (
            <div className="bh-alerts-help">
              <div className="bh-alerts-help-title">What you are looking at</div>
              <div className="bh-alerts-help-body">
                <div className="bh-alerts-help-line">
                  <strong>Active</strong> shows the strongest signal per coin and signal type.
                </div>
                <div className="bh-alerts-help-line">
                  <strong>Recent</strong> shows everything detected, newest first.
                </div>
              </div>

              <div className="bh-alerts-glossary" role="list" aria-label="Signal glossary">
                {Object.entries(TYPE_HELP).map(([k, v]) => (
                  <div key={k} className="bh-gloss-item" role="listitem">
                    <span className="bh-gloss-key">{k}</span>
                    <span className="bh-gloss-val">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className="bh-signal-list" role="list">
            {rows.length === 0 ? (
              <div className="bh-signal-empty">
                {feed === "ACTIVE" ? "No active signals right now." : "No recent signals yet."}
              </div>
            ) : (
              rows.slice(0, compact ? 10 : 60).map((a) => (
                <SignalRow
                  key={a.id || `${a.symbol}-${a.type_key}-${pickTsMs(a)}`}
                  a={a}
                  nowMs={nowMs}
                />
              ))
            )}
          </div>

          <div className="bh-signal-foot">
            Click any signal to open the source link or Coinbase Advanced Trade.
          </div>

          {!compact ? (
            <ProofFooter
              meta={effectiveMeta}
              activeCount={effectiveActiveAlerts.length}
              recentCount={effectiveRecentAlerts.length}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
