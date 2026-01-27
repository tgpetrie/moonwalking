import { useEffect, useMemo, useRef, useState } from "react";
import { formatPct } from "../utils/format";
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
    { id: "init-1", time: "INIT", msg: "ESTABLISHING NEURAL LINK...", tone: "mint" },
    { id: "init-2", time: "INIT", msg: "M3_COPROCESSOR: ONLINE", tone: "mint" },
  ]);

  const seenRef = useRef(new Set());
  const scrollRef = useRef(null);
  const lastHeartbeatRef = useRef(0);

  useEffect(() => {
    if (!isCollapsed && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, isCollapsed]);

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
      const pct = toNum(token?.change_1m);
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
          body: `SPIKE DETECTED [${formatPct(pct, { sign: true })}]`,
          tone: "gold",
        });
        seenRef.current.add(key);
      }
    }

    for (const token of losers3m) {
      const symbol = safeSymbol(token?.symbol || token?.ticker);
      const pct = toNum(token?.change_3m);
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
          body: `RAPID DROP [${formatPct(pct, { sign: true })}]`,
          tone: "purple",
        });
        seenRef.current.add(key);
      }
    }

    for (const token of vol1h) {
      const symbol = safeSymbol(token?.symbol || token?.ticker);
      const pct = Math.floor(toNum(token?.volume_change_1h_pct));
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
          body: `VOLUME SHOCK [+${pct}%]`,
          tone: "cyan",
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
      const tone = sev === "critical" ? "purple" : sev === "high" ? "gold" : sev === "medium" ? "cyan" : "mint-dim";
      const type = String(a.type || "alert").toUpperCase();
      const msg = a.message || a.title || "";

      newLogs.push({
        id: `a-${Date.now()}-${Math.random()}`,
        time: timeStr,
        symbol,
        url,
        prefix: "!!!",
        body: `${type} — ${msg}`,
        tone,
      });
      seenRef.current.add(key);
    }

    if (newLogs.length) {
      setLogs((prev) => [...prev, ...newLogs].slice(-40));
    }
  }, [alerts]);

  return (
    <div className="bh-anom intelligence-log" style={{ height: isCollapsed ? "38px" : "160px" }} data-collapsed={isCollapsed ? "1" : "0"}>
      <button
        type="button"
        className="bh-anom-head"
        onClick={() => setIsCollapsed((v) => !v)}
        aria-expanded={!isCollapsed}
      >
        <div className="bh-anom-title">
          INTELLIGENCE_LOG //{" "}
          <span className={`bh-anom-state ${isCollapsed ? "is-standby" : "is-live"}`}>{isCollapsed ? "STANDBY" : "LIVE"}</span>
        </div>
        <div className="bh-anom-meta">v4.0.2</div>
      </button>

      <div ref={scrollRef} className={`bh-anom-body ${isCollapsed ? "is-hidden" : ""}`}>
        {logs.map((log) => {
          const tradeUrl = getAlertTradeUrl(log);
          const isClickable = Boolean(tradeUrl);
          return (
            <div
              key={log.id}
              className={`bh-anom-line bh-row tone-${log.tone} ${isClickable ? "bh-anom-clickable" : ""}`}
              data-side="flat"
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
            <span className="bh-anom-time">[{log.time}]</span>
            <span className="bh-anom-msg">
              {log.prefix ? <span className="bh-anom-prefix">{log.prefix}</span> : null}{" "}
              {log.symbol ? (
                tradeUrl ? (
                  <a
                    className="bh-anom-link"
                    href={tradeUrl}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: "inherit" }}
                  >
                    {log.symbol}
                  </a>
                ) : (
                  <span className="bh-anom-sym">{log.symbol}</span>
                )
              ) : null}{" "}
              <span className="bh-anom-text">{log.body || log.msg}</span>
            </span>
            </div>
          );
        })}
        <div className="bh-anom-cursor">_</div>
      </div>
    </div>
  );
}
