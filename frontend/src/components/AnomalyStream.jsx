import { useEffect, useMemo, useRef, useState } from "react";
import { formatPct, formatPrice } from "../utils/format";
import { deriveAlertType, parseImpulseMessage, windowLabelFromType } from "../utils/alertClassifier";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";

const safeSymbol = (value) => {
  if (!value) return "";
  const v = String(value);
  return v.replace(/-USD$|-USDT$|-PERP$/i, "").toUpperCase();
};

const toNum = (value) => {
  if (value == null) return NaN;
  if (typeof value === "number") return value;
  const normalized = Number(String(value).replace(/[%+]/g, ""));
  return Number.isFinite(normalized) ? normalized : NaN;
};

const pickNumber = (...values) => {
  for (const v of values) {
    const n = toNum(v);
    if (Number.isFinite(n)) return n;
  }
  return null;
};

const formatDeltaPct = (raw) => {
  if (!Number.isFinite(raw)) return null;
  const pct = Math.abs(raw) <= 1 ? raw * 100 : raw;
  return formatPct(pct, { sign: true });
};

const extractDivergenceRaw = (obj) =>
  obj?.google_trend_score ??
  obj?.google_trend_delta ??
  obj?.trend_score ??
  obj?.trend_delta ??
  obj?.divergence_score ??
  obj?.divergenceScore ??
  obj?.divergence ??
  obj?.divergence_value ??
  obj?.divergenceValue ??
  obj?.search_trend ??
  obj?.searchTrend ??
  obj?.divergence_analysis ??
  null;

const formatDivergence = (raw) => {
  if (raw == null) return null;
  if (typeof raw === "object") {
    const type = raw.divergence_type ?? raw.type ?? raw.label ?? null;
    const magnitude = pickNumber(raw.magnitude, raw.score, raw.value);
    if (type && Number.isFinite(magnitude)) return `Divergence ${type} ${magnitude.toFixed(2)}`;
    if (type) return `Divergence ${type}`;
    if (Number.isFinite(magnitude)) {
      const display = Math.abs(magnitude) <= 1 ? `${(magnitude * 100).toFixed(1)}%` : magnitude.toFixed(2);
      return `Divergence ${display}`;
    }
  }
  const n = toNum(raw);
  if (Number.isFinite(n)) {
    const display = Math.abs(n) <= 1 ? `${(n * 100).toFixed(1)}%` : n.toFixed(2);
    return `Divergence ${display}`;
  }
  const s = String(raw).trim();
  return s ? `Divergence ${s}` : null;
};

const classifyLog = (log) => {
  if (log?.label) {
    return { label: log.label, chipTone: "info" };
  }
  const pct = Number.isFinite(log?.pct) ? log.pct : toNum(log?.pct);
  const derivedType = deriveAlertType({
    type: log?.type,
    pct,
    severity: log?.severity || log?.sev,
  });
  let chipTone = "info";
  if (["MOONSHOT", "BREAKOUT", "IMPULSE", "FOMO"].includes(derivedType)) chipTone = "gain";
  else if (["CRATER", "DUMP", "FEAR"].includes(derivedType)) chipTone = "loss";
  else if (["SENTIMENT", "DIVERGENCE", "VOLUME", "WHALE", "STEALTH"].includes(derivedType)) chipTone = "sent";
  return { label: derivedType, chipTone };
};

const buildMessage = (log, label) => {
  let base = String(log?.body || log?.msg || "").trim();
  base = base
    .replace(/\bIMPULSE[_\s-]?1M\b/gi, "")
    .replace(/\bIMPULSE[_\s-]?3M\b/gi, "")
    .replace(/\s*—\s*—?/g, " — ")
    .replace(/\s{2,}/g, " ")
    .replace(/^\s*—\s*/, "")
    .replace(/\s*—\s*$/, "")
    .trim();
  const pct = Number.isFinite(log?.pct) ? log.pct : toNum(log?.pct);
  const win = log?.window || log?.window_label || windowLabelFromType(log?.type) || "";
  const pctText = Number.isFinite(pct) ? `${formatPct(pct, { sign: true })}${win ? ` in ${win}` : ""}` : null;

  const volPct = pickNumber(
    log?.vol_change_pct,
    log?.vol_pct,
    log?.volume_change_1h_pct,
    log?.volume_change_pct,
    log?.volumeChangePct
  );
  const volText = Number.isFinite(volPct) ? `Vol ${volPct > 0 ? "+" : ""}${volPct.toFixed(0)}%` : null;

  const sentimentDelta = pickNumber(
    log?.sentiment_delta,
    log?.sentimentDelta,
    log?.sentiment_change,
    log?.sentimentChange,
    log?.sentiment_score_delta,
    log?.sentimentScoreDelta
  );
  const sentimentText = Number.isFinite(sentimentDelta) ? `Sent ${formatDeltaPct(sentimentDelta)}` : null;

  const priceNow = pickNumber(log?.price_now, log?.price, log?.current_price);
  const priceThen = pickNumber(log?.price_then, log?.initial_price);
  let priceText = null;
  if (Number.isFinite(priceNow)) {
    const nowText = formatPrice(priceNow);
    priceText = Number.isFinite(priceThen) ? `${nowText} from ${formatPrice(priceThen)}` : nowText;
  }

  const divRaw = log?.divergence ?? log?.divergence_raw ?? extractDivergenceRaw(log);
  const divergenceText = formatDivergence(divRaw);

  const extras = [];
  if (pctText && !base.includes("%")) extras.push(pctText);
  if (volText && !base.includes("%")) extras.push(volText);
  if (sentimentText && !base.includes("%")) extras.push(sentimentText);
  if (priceText && !base.includes("$")) extras.push(priceText);
  if (divergenceText) extras.push(divergenceText);
  else if (label === "DIVERGENCE") extras.push("Divergence: unavailable");

  if (base) return extras.length ? `${base} · ${extras.join(" · ")}` : base;
  return extras.join(" · ");
};

const renderIntelMessage = (message) => {
  if (!message) return null;
  const text = String(message);
  const parts = [];
  const regex = /([+-]\d+(?:\.\d+)?%)/g;
  let lastIndex = 0;
  let match;
  while ((match = regex.exec(text))) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const token = match[1];
    const cls = token.startsWith("-") ? "bh-intel-pct bh-intel-pct--neg" : "bh-intel-pct bh-intel-pct--pos";
    parts.push(
      <span key={`pct-${match.index}`} className={cls}>
        {token}
      </span>
    );
    lastIndex = match.index + token.length;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts;
};

const spotUrl = (token, symbol) => {
  const productId =
    token?.product_id ||
    token?.symbol ||
    token?.ticker ||
    (symbol ? `${symbol}-USD` : null);
  return coinbaseSpotUrl({ product_id: productId, symbol });
};

const getAlertTradeUrl = (log) => {
  const u = log?.url;
  if (typeof u === "string" && u.startsWith("http")) return u;

  const pid = (log?.product_id || log?.symbol || "").toString().trim().toUpperCase();
  if (!pid) return null;
  const productId = pid.includes("-") ? pid : `${pid}-USD`;
  return `https://www.coinbase.com/advanced-trade/spot/${encodeURIComponent(productId)}`;
};

export default function AnomalyStream({ data = {}, volumeData = [] }) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [logs, setLogs] = useState([
    { id: "init-1", time: "INIT", msg: "ESTABLISHING NEURAL LINK...", label: "SYSTEM" },
    { id: "init-2", time: "INIT", msg: "M3_COPROCESSOR: ONLINE", label: "SYSTEM" },
  ]);

  const seenRef = useRef(new Set());
  const scrollRef = useRef(null);
  const lastHeartbeatRef = useRef(0);

  useEffect(() => {
    if (!isCollapsed && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, isCollapsed]);

  const visibleLogs = isCollapsed ? [] : logs.slice(-8);

  const gainers1m = useMemo(() => (Array.isArray(data?.gainers_1m) ? data.gainers_1m : []), [data]);
  const losers3m = useMemo(() => (Array.isArray(data?.losers_3m) ? data.losers_3m : []), [data]);
  const vol1h = useMemo(() => (Array.isArray(volumeData) ? volumeData : []), [volumeData]);
  const alerts = useMemo(() => (Array.isArray(data?.alerts) ? data.alerts : []), [data]);

  useEffect(() => {
    const hasAnything = gainers1m.length || losers3m.length || vol1h.length;
    if (!hasAnything) return;

    const now = new Date();
    const timeStr = now
      .toLocaleTimeString([], {
        hour12: false,
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
      .replace(/\u200E/g, "");

    const newLogs = [];

    for (const token of gainers1m) {
      const symbol = safeSymbol(token?.symbol || token?.ticker);
      const pct = pickNumber(token?.change_1m, token?.price_change_percentage_1min, token?.price_change_1m);
      if (!symbol || !Number.isFinite(pct)) continue;
      const key = `G-1m-${symbol}-${pct.toFixed(4)}`;
      if (seenRef.current.has(key)) continue;
      if (pct > 1.5) {
        const url = spotUrl(token, symbol);
        newLogs.push({
          id: `g-${Date.now()}-${Math.random()}`,
          time: timeStr,
          symbol,
          url,
          prefix: ">>>",
          body: `SPIKE DETECTED`,
          pct,
          window: "1m",
          type: "IMPULSE_1M",
          price_now: token?.current_price ?? token?.price ?? null,
          price_then: token?.previous_price_1m ?? token?.price_1m_ago ?? null,
          sentiment_delta: token?.sentiment_delta ?? token?.sentimentDelta ?? null,
          divergence: extractDivergenceRaw(token),
        });
        seenRef.current.add(key);
      }
    }

    for (const token of losers3m) {
      const symbol = safeSymbol(token?.symbol || token?.ticker);
      const pct = pickNumber(token?.change_3m, token?.price_change_percentage_3min, token?.price_change_3m);
      if (!symbol || !Number.isFinite(pct)) continue;
      const key = `L-3m-${symbol}-${pct.toFixed(4)}`;
      if (seenRef.current.has(key)) continue;
      if (pct < -2.0) {
        const url = spotUrl(token, symbol);
        newLogs.push({
          id: `l-${Date.now()}-${Math.random()}`,
          time: timeStr,
          symbol,
          url,
          prefix: "<<<",
          body: `RAPID DROP`,
          pct,
          window: "3m",
          type: "IMPULSE_3M",
          price_now: token?.current_price ?? token?.price ?? null,
          price_then: token?.previous_price_3m ?? token?.price_3m_ago ?? null,
          sentiment_delta: token?.sentiment_delta ?? token?.sentimentDelta ?? null,
          divergence: extractDivergenceRaw(token),
        });
        seenRef.current.add(key);
      }
    }

    for (const token of vol1h) {
      const symbol = safeSymbol(token?.symbol || token?.ticker);
      const pct = Math.floor(pickNumber(token?.volume_change_1h_pct, token?.volume_change_pct, token?.volumeChangePct));
      if (!symbol || !Number.isFinite(pct)) continue;
      const key = `V-1h-${symbol}-${pct}`;
      if (seenRef.current.has(key)) continue;
      if (pct > 80) {
        const url = spotUrl(token, symbol);
        newLogs.push({
          id: `v-${Date.now()}-${Math.random()}`,
          time: timeStr,
          symbol,
          url,
          prefix: "|||",
          body: `VOLUME SHOCK`,
          vol_change_pct: pct,
          window: "1h",
          type: "VOLUME_1H",
          divergence: extractDivergenceRaw(token),
        });
        seenRef.current.add(key);
      }
    }

    // NOTE: heartbeat/ping entries intentionally suppressed for cleaner intelligence log
    // (previous behavior inserted lightweight PING messages when no anomalies were present)

    if (newLogs.length) {
      setLogs((prev) => [...prev, ...newLogs].slice(-30));
    }
  }, [gainers1m, losers3m, vol1h]);

  useEffect(() => {
    if (!Array.isArray(alerts) || alerts.length === 0) return;

    const now = new Date();
    const timeStr = now
      .toLocaleTimeString([], {
        hour12: false,
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
      .replace(/\u200E/g, "");

    const newLogs = [];
    for (const a of alerts) {
      if (!a) continue;
      const id = a.id || `${a.ts || ""}-${a.symbol || ""}-${a.type || ""}`;
      const key = `A-${id}`;
      if (seenRef.current.has(key)) continue;

      const symbol = safeSymbol(a.symbol || a.product_id || a.pair);
      const url = a.trade_url || spotUrl({ product_id: a.product_id || (symbol ? `${symbol}-USD` : null) }, symbol);
      const sev = String(a.severity || "info").toLowerCase();
      const type = String(a.type || "alert").toUpperCase();
      const parsed = parseImpulseMessage(a);
      const pct = pickNumber(a?.pct, parsed?.parsed_pct);
      const windowLabel = windowLabelFromType(a?.type) || parsed?.parsed_window_label || "";
      const volPct = pickNumber(a?.vol_change_pct, a?.vol_pct, a?.meta?.vol_change_pct, a?.meta?.vol_pct);
      const sentimentDelta = pickNumber(
        a?.sentiment_delta,
        a?.sentimentDelta,
        a?.meta?.sentiment_delta,
        a?.meta?.sentimentDelta
      );
      const divergenceRaw = extractDivergenceRaw(a) ?? extractDivergenceRaw(a?.meta || {});
      const msg = a.message || a.title || "";

        newLogs.push({
          id: `a-${Date.now()}-${Math.random()}`,
          time: timeStr,
          symbol,
          url,
          prefix: "",
        body: msg ? `${type} — ${msg}` : type,
        type: a?.type || type,
        severity: a?.severity || "info",
        pct,
        window: windowLabel,
        vol_change_pct: volPct,
        sentiment_delta: sentimentDelta,
        divergence: divergenceRaw,
      });
      seenRef.current.add(key);
    }

    if (newLogs.length) {
      setLogs((prev) => [...prev, ...newLogs].slice(-40));
    }
  }, [alerts]);

  return (
    <section className="bh-intel-panel" data-collapsed={isCollapsed ? "1" : "0"}>
      <div className="bh-intel-head">
        <button
          type="button"
          className="bh-intel-toggle"
          onClick={() => setIsCollapsed((v) => !v)}
          aria-expanded={!isCollapsed}
        >
          <div className="bh-intel-title">
            INTELLIGENCE_LOG
            <span className={`bh-intel-state ${isCollapsed ? "is-standby" : "is-live"}`}>
              {isCollapsed ? "STANDBY" : "LIVE"}
            </span>
          </div>
          <div className="bh-intel-sub">Live anomalies</div>
        </button>
        <div className="bh-intel-meta">v4.0.2</div>
      </div>

      <div
        ref={scrollRef}
        className={`bh-intel-log ${isCollapsed ? "is-collapsed" : ""}`}
        role="log"
        aria-live="polite"
      >
        {visibleLogs.map((log) => {
          const tradeUrl = getAlertTradeUrl(log);
          const isClickable = Boolean(tradeUrl);
          const { label, chipTone } = classifyLog(log);
          const chipClass = `bh-intel-chip bh-intel-chip--${chipTone}`;
          const message = buildMessage(log, label);
          const showPrefix = Boolean(log.prefix) && log.prefix !== "!!!";

          return (
            <div
              key={log.id}
              className={`bh-intel-line ${isClickable ? "bh-intel-clickable" : ""}`}
              role={isClickable ? "link" : undefined}
              tabIndex={isClickable ? 0 : undefined}
              onClick={(e) => {
                if (!isClickable) return;
                const target = e.target;
                if (target && target.closest && target.closest("a")) return;
                window.open(tradeUrl, "_blank", "noreferrer");
              }}
              onKeyDown={(e) => {
                if (!isClickable) return;
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  window.open(tradeUrl, "_blank", "noreferrer");
                }
              }}
            >
              <span className="bh-intel-ts">[{log.time}]</span>
              <span className={chipClass}>{label}</span>
              <span className="bh-intel-msg">
                {showPrefix ? <span className="bh-intel-prefix">{log.prefix}</span> : null}{" "}
                {log.symbol ? (
                  tradeUrl ? (
                    <a className="bh-intel-sym" href={tradeUrl} target="_blank" rel="noreferrer">
                      {log.symbol}
                    </a>
                  ) : (
                    <span className="bh-intel-sym">{log.symbol}</span>
                  )
                ) : null}{" "}
                <span className="bh-intel-text">{renderIntelMessage(message)}</span>
              </span>
            </div>
          );
        })}
        {!isCollapsed ? <div className="bh-intel-cursor">_</div> : null}
      </div>
    </section>
  );
}
