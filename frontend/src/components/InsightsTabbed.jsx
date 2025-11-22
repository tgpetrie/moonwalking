import React, { useMemo, useState } from "react";
import SentimentCard from "./cards/SentimentCard.jsx";
import { useSentimentLatest } from "../hooks/useSentimentLatest.js";
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
  const { data: d, raw, loading, error } = useSentimentLatest(symbol);

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

  const socialSeries = useMemo(() => {
    const series = Array.isArray(d?.socialHistory) ? d.socialHistory : [];
    return series
      .map((p) => {
        const ts = p?.timestamp ?? null;
        const t = ts ? new Date(ts).getTime() : null;
        return {
          ts,
          t,
          reddit: Number.isFinite(Number(p?.reddit)) ? Number(p.reddit) : null,
          twitter: Number.isFinite(Number(p?.twitter)) ? Number(p.twitter) : null,
          telegram: Number.isFinite(Number(p?.telegram)) ? Number(p.telegram) : null,
          chan: Number.isFinite(Number(p?.chan)) ? Number(p.chan) : null,
        };
      })
      .filter(
        (p) =>
          p.t && (p.reddit != null || p.twitter != null || p.telegram != null || p.chan != null)
      )
      .sort((a, b) => a.t - b.t);
  }, [d]);

  const trendingTopics = useMemo(() => {
    return Array.isArray(d?.trendingTopics) ? d.trendingTopics : [];
  }, [d]);

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

  const renderSocialTab = () => {
    if (loading && !d) return renderLoading();
    if (error) return renderError();

    const volChange = d?.socialMetrics?.volumeChange ?? null;
    const mentions24h = d?.socialMetrics?.mentions24h ?? null;
    const engagement = d?.socialMetrics?.engagementRate ?? null;
    const hasMetrics =
      Number.isFinite(Number(volChange)) ||
      Number.isFinite(Number(mentions24h)) ||
      Number.isFinite(Number(engagement));
    const hasSeries = socialSeries.length > 1;

    const socialBreakdown = d?.socialBreakdown ?? {};
    const hasBreakdown = Object.values(socialBreakdown).some((v) => Number.isFinite(Number(v)));
    const hasTopics = trendingTopics.length > 0;
    const hasDivergences = divergenceAlerts.length > 0;
    const showWidget = Boolean(symbol);
    const hasAny = hasMetrics || hasBreakdown || hasSeries || hasTopics || hasDivergences || showWidget;

    if (!hasAny) {
      return renderEmpty("No social signals yet. Give it a minute to breathe.");
    }

    return (
      <div style={{ display: "grid", gap: 14 }}>
        {hasMetrics && (
          <div className="panel-soft">
            <div className="section-title">Latest social pulse</div>
            <div
              className="social-grid"
              style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10 }}
            >
              <div className="metric-chip">
                <div className="label">Volume change (24h)</div>
                <div className="value">{fmtPct(volChange)}</div>
              </div>
              <div className="metric-chip">
                <div className="label">Mentions (24h)</div>
                <div className="value">
                  {Number.isFinite(Number(mentions24h)) ? Number(mentions24h).toLocaleString() : "--"}
                </div>
              </div>
              <div className="metric-chip">
                <div className="label">Engagement rate</div>
                <div className="value">{fmtNum(engagement, 2)}</div>
              </div>
            </div>
          </div>
        )}

        {hasBreakdown && (
          <div className="panel-soft">
            <div className="section-title">Source breakdown (latest)</div>
            <div
              className="social-grid"
              style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10 }}
            >
              <div className="metric-chip">
                <div className="label">Reddit</div>
                <div className="value">{fmtNum(socialBreakdown.reddit, 2)}</div>
              </div>
              <div className="metric-chip">
                <div className="label">Twitter</div>
                <div className="value">{fmtNum(socialBreakdown.twitter, 2)}</div>
              </div>
              <div className="metric-chip">
                <div className="label">Telegram</div>
                <div className="value">{fmtNum(socialBreakdown.telegram, 2)}</div>
              </div>
              <div className="metric-chip">
                <div className="label">Fringe</div>
                <div className="value">{fmtNum(socialBreakdown.chan, 2)}</div>
              </div>
            </div>
          </div>
        )}

        {hasTopics && (
          <div className="panel-soft">
            <div className="section-title">Trending topics</div>
            <div style={{ display: "grid", gap: 8 }}>
              {trendingTopics.map((t, i) => (
                <div key={`${t.tag ?? "topic"}-${i}`} className="topic-row">
                  <div className="tag">{t.tag ?? "--"}</div>
                  <div className="sent">{t.sentiment ?? "--"}</div>
                  <div className="vol">{t.volume ?? "--"}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {hasSeries && (
          <div className="panel-soft">
            <div className="section-title">Social trend</div>
            <div style={{ width: "100%", height: 220 }}>
              <ResponsiveContainer>
                <LineChart data={socialSeries}>
                  <CartesianGrid stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="ts" hide />
                  <YAxis hide domain={[0, 1]} />
                  <Tooltip
                    contentStyle={{ background: "#111", border: "1px solid rgba(255,255,255,0.08)" }}
                    labelFormatter={() => ""}
                    formatter={(val, key) => [fmtNum(val, 2), key]}
                  />
                  <Line
                    type="monotone"
                    dataKey="reddit"
                    stroke="var(--bh-blue, #7dd3fc)"
                    dot={false}
                    strokeWidth={2}
                  />
                  <Line
                    type="monotone"
                    dataKey="twitter"
                    stroke="var(--bh-purple, #c084fc)"
                    dot={false}
                    strokeWidth={2}
                  />
                  <Line
                    type="monotone"
                    dataKey="telegram"
                    stroke="var(--bh-gold, #f5d061)"
                    dot={false}
                    strokeWidth={2}
                  />
                  <Line
                    type="monotone"
                    dataKey="chan"
                    stroke="var(--bh-pink, #f9a8d4)"
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

    const sb = {
      tier1: Number(d?.sourceBreakdown?.tier1) || 0,
      tier2: Number(d?.sourceBreakdown?.tier2) || 0,
      tier3: Number(d?.sourceBreakdown?.tier3) || 0,
      fringe: Number(d?.sourceBreakdown?.fringe) || 0,
    };
    const hasSources = Object.values(sb).some((v) => Number.isFinite(Number(v)) && Number(v) !== 0);

    return (
      <div style={{ display: "grid", gap: 12 }}>
        {!hasSources ? (
          renderEmpty("No source breakdown yet.")
        ) : (
          <div className="panel-soft">
            <div className="section-title">Coverage mix</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10 }}>
              <div className="metric-chip">
                <div className="label">Tier 1</div>
                <div className="value">{fmtNum(sb.tier1, 0)}</div>
              </div>
              <div className="metric-chip">
                <div className="label">Tier 2</div>
                <div className="value">{fmtNum(sb.tier2, 0)}</div>
              </div>
              <div className="metric-chip">
                <div className="label">Tier 3</div>
                <div className="value">{fmtNum(sb.tier3, 0)}</div>
              </div>
              <div className="metric-chip">
                <div className="label">Fringe</div>
                <div className="value">{fmtNum(sb.fringe, 0)}</div>
              </div>
            </div>
          </div>
        )}

        {trendingTopics.length > 0 && (
          <div className="panel-soft">
            <div className="section-title">Trending topics</div>
            <div style={{ display: "grid", gap: 8 }}>
              {trendingTopics.map((t, i) => (
                <div key={`${t.tag}-${i}`} className="topic-row">
                  <div className="tag">{t.tag ?? "--"}</div>
                  <div className="sent">{t.sentiment ?? "--"}</div>
                  <div className="vol">{t.volume ?? "--"}</div>
                </div>
              ))}
            </div>
          </div>
        )}

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
