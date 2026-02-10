import { useMemo, useState, useEffect } from "react";
import { useData } from "../context/DataContext";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";

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
  fomo: "FOMO",
  fear: "FEAR",
};

const TYPE_HELP = {
  MOONSHOT: "Fast surge",
  CRATER: "Fast drop",
  BREAKOUT: "Trend shift",
  DUMP: "Strong sell pressure",
  WHALE: "Unusual volume spike",
  STEALTH: "Volume warming quietly",
  DIVERGENCE: "Price vs sentiment mismatch",
  MOVE: "Short-term move",
  FOMO: "Chasing behavior",
  FEAR: "Risk-off behavior",
};

// Signal Class: plain-English buckets for everyday users
const SIGNAL_CLASSES = {
  ALL: { label: "All Signals", types: null },
  OPPORTUNITY: { label: "Opportunity", types: ["MOONSHOT", "BREAKOUT", "STEALTH"] },
  RISK: { label: "Risk", types: ["CRATER", "DUMP"] },
  WHALE: { label: "Whale Activity", types: ["WHALE"] },
  MOMENTUM: { label: "Momentum", types: ["MOVE", "FOMO", "FEAR"] },
  WEIRDNESS: { label: "Unusual", types: ["DIVERGENCE"] },
};

const classForType = (upperType) => {
  for (const [cls, def] of Object.entries(SIGNAL_CLASSES)) {
    if (cls === "ALL") continue;
    if (def.types && def.types.includes(upperType)) return cls;
  }
  return "ALL";
};

const SEV_RANK = { critical: 5, high: 4, medium: 3, low: 2, info: 1 };

const toUpperType = (typeKey) => {
  const k = String(typeKey || "").toLowerCase();
  return TYPE_LABEL[k] || k.toUpperCase() || "ALERT";
};

const pickTsMs = (a) =>
  (Number.isFinite(a?.event_ts_ms) && a.event_ts_ms) ||
  (Number.isFinite(a?.ts_ms) && a.ts_ms) ||
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
  const mp = meta?.market_pressure || {};
  const heatRaw = Number(mp.heat);
  const heat = Number.isFinite(heatRaw) ? Math.max(0, Math.min(100, heatRaw)) : 50;

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
  const type = toUpperType(a?.type_key || a?.type);
  const sev = String(a?.severity || "info").toLowerCase();
  const sym = String(a?.product_id || a?.symbol || "").toUpperCase().replace("-USD", "");
  const ts = pickTsMs(a);
  const age = ts ? ageLabel(nowMs - ts) : "\u2014";

  const pct = pickPct(a);
  const volPct = pickVolPct(a);

  const pctText = pct == null ? "" : `${pct > 0 ? "+" : ""}${pct.toFixed(Math.abs(pct) < 5 ? 3 : 2)}%`;
  const volText = volPct == null ? "" : `Vol ${volPct > 0 ? "+" : ""}${volPct.toFixed(0)}%`;

  const url = a?.trade_url || coinbaseSpotUrl({ product_id: toProductId(a), symbol: a?.symbol });
  const cls = classForType(type);

  return (
    <div
      className="bh-signal-row"
      data-sev={sev}
      data-class={cls.toLowerCase()}
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
        <div className="bh-signal-top">
          <span className="bh-signal-type">{type}</span>
          <span className="bh-signal-sym">{sym || "\u2014"}</span>
          <span className="bh-signal-age">{age}</span>
        </div>

        <div className="bh-signal-chips">
          {pctText ? <span className="bh-chip">{pctText}</span> : null}
          {volText ? <span className="bh-chip">{volText}</span> : null}
          {TYPE_HELP[type] ? <span className="bh-chip bh-chip--hint">{TYPE_HELP[type]}</span> : null}
        </div>
      </div>

      <div className="bh-signal-side">
        <span className="bh-sev-pill">{String(a?.severity || "info").toUpperCase()}</span>
      </div>
    </div>
  );
}

export default function AlertsTab({ filterSymbol = null }) {
  const { activeAlerts = [], alertsRecent = [], alertsMeta = {} } = useData() || {};

  const [feed, setFeed] = useState("ACTIVE");
  const [signalClass, setSignalClass] = useState("ALL");
  const [sev, setSev] = useState("ALL");
  const [sort, setSort] = useState(() => "IMPORTANCE");
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [showHelp, setShowHelp] = useState(false);
  // Coin-aware: if opened with a symbol, default-filter to it
  const [coinFilter, setCoinFilter] = useState(filterSymbol ? filterSymbol.toUpperCase() : "ALL");

  // Reset coin filter when symbol prop changes
  useEffect(() => {
    setCoinFilter(filterSymbol ? filterSymbol.toUpperCase() : "ALL");
  }, [filterSymbol]);

  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    setSort(feed === "ACTIVE" ? "IMPORTANCE" : "TIME");
  }, [feed]);

  const source = feed === "ACTIVE" ? activeAlerts : alertsRecent;

  // Build coin options from available alerts
  const coinOptions = useMemo(() => {
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
  }, [alertsRecent, activeAlerts]);

  const rows = useMemo(() => {
    let out = Array.isArray(source) ? source : [];

    // Coin filter
    if (coinFilter !== "ALL") {
      out = out.filter((a) => alertSymbol(a) === coinFilter);
    }

    // Signal Class filter
    if (signalClass !== "ALL") {
      const allowedTypes = SIGNAL_CLASSES[signalClass]?.types;
      if (allowedTypes) {
        out = out.filter((a) => allowedTypes.includes(toUpperType(a?.type_key || a?.type)));
      }
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
  }, [source, coinFilter, signalClass, sev, sort, feed]);

  return (
    <div className="bh-alerts-tab">
      <div className="bh-alerts-layout">
        <MarketMoodCard meta={alertsMeta} />

        <div className="bh-alerts-feed">
          <div className="bh-alerts-feed-head">
            <div className="bh-alerts-feed-title">Signals</div>

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
          </div>

          <div className="bh-alerts-tab-controls">
            {/* Signal Class (everyday filter) */}
            <div className="bh-control">
              <div className="bh-control-label">Signal Class</div>
              <select className="bh-control-select" value={signalClass} onChange={(e) => setSignalClass(e.target.value)}>
                {Object.entries(SIGNAL_CLASSES).map(([k, v]) => (
                  <option key={k} value={k}>{v.label}</option>
                ))}
              </select>
            </div>

            {/* Urgency */}
            <div className="bh-control">
              <div className="bh-control-label">Urgency</div>
              <select className="bh-control-select" value={sev} onChange={(e) => setSev(e.target.value)}>
                {["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"].map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            {/* Order By */}
            <div className="bh-control">
              <div className="bh-control-label">Order By</div>
              <select className="bh-control-select" value={sort} onChange={(e) => setSort(e.target.value)}>
                <option value="IMPORTANCE">Most Important</option>
                <option value="TIME">Newest</option>
                <option value="URGENCY">Urgency</option>
                <option value="MAGNITUDE">Biggest Move</option>
              </select>
            </div>

            {/* Coin filter */}
            <div className="bh-control">
              <div className="bh-control-label">Coin</div>
              <select className="bh-control-select" value={coinFilter} onChange={(e) => setCoinFilter(e.target.value)}>
                {coinOptions.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Help toggle */}
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

          {showHelp ? (
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
              rows.slice(0, 60).map((a) => (
                <SignalRow
                  key={a.id || `${a.symbol}-${a.type_key}-${pickTsMs(a)}`}
                  a={a}
                  nowMs={nowMs}
                />
              ))
            )}
          </div>

          <div className="bh-signal-foot">
            Click any signal to open Coinbase Advanced Trade.
          </div>

          <ProofFooter
            meta={alertsMeta}
            activeCount={activeAlerts.length}
            recentCount={alertsRecent.length}
          />
        </div>
      </div>
    </div>
  );
}
