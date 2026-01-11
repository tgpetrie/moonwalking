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

    // Show heartbeat only once every 30 seconds when no anomalies
    const nowMs = Date.now();
    if (newLogs.length === 0 && nowMs - lastHeartbeatRef.current > 30000) {
      const systems = ["CACHE_SYNC", "SNAPSHOT_ENGINE", "COINBASE_POLL", "BANNER_LOOP"];
      const sys = systems[Math.floor(Math.random() * systems.length)];
      newLogs.push({
        id: `hb-${nowMs}`,
        time: timeStr,
        msg: `PING >> ${sys} heartbeat verified...`,
        tone: "mint-dim",
      });
      lastHeartbeatRef.current = nowMs;
    }

    if (newLogs.length) {
      setLogs((prev) => [...prev, ...newLogs].slice(-30));
    }
  }, [gainers1m, losers3m, vol1h]);

  return (
    <div className="bh-anom" style={{ height: isCollapsed ? "38px" : "160px" }} data-collapsed={isCollapsed ? "1" : "0"}>
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
        {logs.map((log) => (
          <div key={log.id} className={`bh-anom-line bh-row tone-${log.tone}`} data-side="flat">
            <span className="bh-anom-time">[{log.time}]</span>
            <span className="bh-anom-msg">
              {log.prefix ? <span className="bh-anom-prefix">{log.prefix}</span> : null}{" "}
              {log.symbol ? (
                log.url ? (
                  <a
                    className="bh-anom-link"
                    href={log.url}
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
        ))}
        <div className="bh-anom-cursor">_</div>
      </div>
    </div>
  );
}
