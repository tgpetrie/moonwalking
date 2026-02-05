import React, { useMemo, useState } from "react";
import SentimentCard from "./cards/SentimentCard.jsx";
import { useMarketHeat } from "../hooks/useMarketHeat.js";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid
} from "recharts";
import TradingViewChart from "./charts/TradingViewChart.jsx";
import TradingViewTech from "./charts/TradingViewTech.jsx";

class TabErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(err, info) {
    if (import.meta.env.DEV) {
      console.error("[InsightsTabbed] tab crashed:", err, info);
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="state-copy error" style={{ padding: "12px 0" }}>
          This tab hit a runtime snag. Refreshing should recover.
        </div>
      );
    }
    return this.props.children;
  }
}

const fmtPct = (v) => (Number.isFinite(Number(v)) ? `${Number(v).toFixed(1)}%` : "--");
const fmtNum = (v, digits = 2) => (Number.isFinite(Number(v)) ? Number(v).toFixed(digits) : "--");

export default function InsightsTabbed({ symbol = "", onClose }) {
  const [active, setActive] = useState("overview");
  const { data: d, raw, loading, error } = useMarketHeat();

  const sentimentSeries = useMemo(() => {
    const series = Array.isArray(d?.sentimentHistory) ? d.sentimentHistory : [];
    return series
      .map((p) => {
        const ts = p?.timestamp ?? null;
        const t = ts ? new Date(ts).getTime() : null;
        return {
          ts,
          t,
          sentiment: Number.isFinite(Number(p?.sentiment)) ? Number(p.sentiment) : null,
          price: Number.isFinite(Number(p?.priceNormalized)) ? Number(p.priceNormalized) : null,
        };
      })
      .filter((p) => p.t && p.sentiment != null)
      .sort((a, b) => a.t - b.t);
  }, [d]);

  const components = d?.components || {};
  const heatLabel = d?.heatLabel || "NEUTRAL";
  const regimeRaw = (d?.regime || "unknown").toString();

  const divergenceAlerts = useMemo(() => {
    return Array.isArray(d?.divergenceAlerts) ? d.divergenceAlerts : [];
  }, [d]);

  const renderLoading = () => <div className="insights-empty-card">Loading sentiment…</div>;
  const renderError = () => (
    <div className="insights-empty-card">
      Sentiment feed is offline. Last snapshot will return when available.
    </div>
  );
  const renderEmpty = (msg) => <div className="insights-empty-card">{msg}</div>;

  const renderTapeTab = () => {
    if (loading && !d) return renderLoading();
    if (error) return renderError();

    const hasComponents = components.total_symbols > 0;
    const hasDivergences = divergenceAlerts.length > 0;
    const showWidget = Boolean(symbol);
    const hasAny = hasComponents || hasDivergences || showWidget;

    if (!hasAny) {
      return renderEmpty("Warming up — collecting tape data...");
    }

    return (
      <div style={{ display: "grid", gap: 14 }}>
        {hasComponents && (
          <div className="panel-soft">
            <div className="section-title">Tape components ({components.total_symbols} symbols)</div>
            <div
              className="social-grid"
              style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10 }}
            >
              <div className="metric-chip">
                <div className="label">Breadth (3m)</div>
                <div className="value">{fmtPct(components.breadth_3m)}</div>
              </div>
              <div className="metric-chip">
                <div className="label">Breadth (1m)</div>
                <div className="value">{fmtPct(components.breadth_1m)}</div>
              </div>
              <div className="metric-chip">
                <div className="label">Momentum</div>
                <div className="value">{components.momentum_alignment != null ? fmtPct(components.momentum_alignment * 100) : "--"}</div>
              </div>
              <div className="metric-chip">
                <div className="label">Volatility</div>
                <div className="value">{fmtPct(components.volatility)}</div>
              </div>
            </div>
          </div>
        )}

        {hasComponents && (
          <div className="panel-soft">
            <div className="section-title">Regime: {regimeRaw.replace(/_/g, " ").toUpperCase()} · Heat: {heatLabel}</div>
            <div
              className="social-grid"
              style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10 }}
            >
              <div className="metric-chip">
                <div className="label">Avg Return (3m)</div>
                <div className="value">{fmtNum(components.avg_return_3m, 3)}%</div>
              </div>
              <div className="metric-chip">
                <div className="label">Avg Return (1m)</div>
                <div className="value">{fmtNum(components.avg_return_1m, 3)}%</div>
              </div>
              <div className="metric-chip">
                <div className="label">Green/Red (3m)</div>
                <div className="value">{components.green_3m ?? 0}/{components.red_3m ?? 0}</div>
              </div>
            </div>
          </div>
        )}

        {sentimentSeries.length > 1 && (
          <div className="panel-soft">
            <div className="section-title">Heat trend</div>
            <div style={{ width: "100%", height: 220 }}>
              <ResponsiveContainer>
                <LineChart data={sentimentSeries}>
                  <CartesianGrid stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="ts" hide />
                  <YAxis hide domain={[0, 1]} />
                  <Tooltip
                    contentStyle={{ background: "#111", border: "1px solid rgba(255,255,255,0.08)" }}
                    labelFormatter={() => ""}
                    formatter={(val) => [fmtNum(val * 100, 0), "Heat"]}
                  />
                  <Line
                    type="monotone"
                    dataKey="sentiment"
                    stroke="var(--bh-purple, #c084fc)"
                    dot={false}
                    strokeWidth={2}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {hasDivergences && (
          <div className="panel-soft">
            <div className="section-title">Divergence alerts</div>
            <div style={{ display: "grid", gap: 8 }}>
              {divergenceAlerts.map((a, i) => (
                <div key={`${a.type ?? "div"}-${i}`} className="alert-row">
                  <div className="type">{a.type ?? "alert"}</div>
                  <div className="msg">{a.message ?? ""}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {showWidget && (
          <div className="panel-soft">
            <div className="section-title">Technical pulse</div>
            <TradingViewTech symbol={symbol} height={340} />
          </div>
        )}
      </div>
    );
  };

  const renderChartsTab = () => {
    if (loading && !d) return renderLoading();
    if (error) return renderError();

    return (
      <div style={{ display: "grid", gap: 14 }}>
        <div className="section-title">Price action</div>
        <TradingViewChart symbol={symbol} height={360} interval="15" />

        <div className="section-title">Higher timeframe</div>
        <TradingViewChart symbol={symbol} height={260} interval="60" />
      </div>
    );
  };

  const renderSourcesTab = () => {
    if (loading && !raw) return renderLoading();
    if (error) return renderError();

    const fg = d?.fearGreedIndex;
    const hasFG = Number.isFinite(Number(fg));

    return (
      <div style={{ display: "grid", gap: 12 }}>
        <div className="panel-soft">
          <div className="section-title">Data sources</div>
          <div style={{ display: "grid", gap: 8 }}>
            <div className="alert-row">
              <div className="type" style={{ color: "var(--bh-green, #45ffb3)" }}>PRIMARY</div>
              <div className="msg">Coinbase Price Tape — {components.total_symbols ?? 0} symbols, ~8s refresh</div>
            </div>
            <div className="alert-row">
              <div className="type" style={{ color: "var(--bh-gold, #f5d061)" }}>VOLUME</div>
              <div className="msg">Coinbase 1-min Candles — whale &amp; stealth detection</div>
            </div>
            <div className="alert-row">
              <div className="type" style={{ color: hasFG ? "var(--bh-blue, #7dd3fc)" : "#666" }}>{hasFG ? "LIVE" : "N/A"}</div>
              <div className="msg">Fear &amp; Greed Index — external macro signal{hasFG ? ` (${Number(fg).toFixed(0)})` : ""}</div>
            </div>
          </div>
        </div>

        {divergenceAlerts.length > 0 && (
          <div className="panel-soft">
            <div className="section-title">Divergence alerts</div>
            <div style={{ display: "grid", gap: 8 }}>
              {divergenceAlerts.map((a, i) => (
                <div key={`${a.type}-${i}`} className="alert-row">
                  <div className="type">{a.type ?? "alert"}</div>
                  <div className="msg">{a.message ?? ""}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="sentiment-modal-shell">
      <div className="sentiment-modal-content">
        <div className="insights-tabbed">
          <div className="insights-tabs">
            <button
              className={`insights-tab ${active === "overview" ? "active" : ""}`}
              onClick={() => setActive("overview")}
            >
              Overview
            </button>
            <button
              className={`insights-tab ${active === "social" ? "active" : ""}`}
              onClick={() => setActive("social")}
            >
              Social Sentiment
            </button>
            <button
              className={`insights-tab ${active === "charts" ? "active" : ""}`}
              onClick={() => setActive("charts")}
            >
              Charts
            </button>
            <button
              className={`insights-tab ${active === "sources" ? "active" : ""}`}
              onClick={() => setActive("sources")}
            >
              Data Sources
            </button>

            {typeof onClose === "function" && (
              <button
                className="close-btn"
                onClick={onClose}
                aria-label="Close insights"
                style={{ marginLeft: "auto" }}
              >
                ×
              </button>
            )}
          </div>

          <div className="tab-body">
            {active === "overview" && <SentimentCard symbol={symbol} />}

            {active === "social" && <TabErrorBoundary>{renderSocialTab()}</TabErrorBoundary>}

            {active === "charts" && <TabErrorBoundary>{renderChartsTab()}</TabErrorBoundary>}

            {active === "sources" && <TabErrorBoundary>{renderSourcesTab()}</TabErrorBoundary>}
          </div>
        </div>
      </div>
    </div>
  );
}
