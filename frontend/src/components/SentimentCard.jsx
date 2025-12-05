import React from "react";
import { useSentiment } from "../context/SentimentContext.jsx";

const TABS = ["Overview", "Funding", "Sources"];

export default function SentimentCard() {
  const { sentiment, loading, error } = useSentiment();
  const [active, setActive] = React.useState("Overview");
  const noData = !loading && !error && !sentiment;

  return (
    <div className="bh-panel sentiment-card">
      <div className="sentiment-card-header">
        <div>
          <h3 className="sentiment-title">Market Psychology</h3>
          <p className="sentiment-subtitle">Blended sentiment signal</p>
        </div>
        <div className="sentiment-tabs">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActive(tab)}
              className={tab === active ? "active" : ""}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {loading && <p className="sentiment-hint">Loading sentiment…</p>}
      {error && <p className="sentiment-error">Sentiment unavailable.</p>}
      {noData && <p className="sentiment-hint">Sentiment warming up – no live data yet.</p>}

      {!loading && !error && sentiment && (
        <div className="sentiment-body">
          {active === "Overview" && <OverviewView sentiment={sentiment} />}
          {active === "Funding" && <FundingView sentiment={sentiment} />}
          {active === "Sources" && <SourcesView sentiment={sentiment} />}
        </div>
      )}
    </div>
  );
}

function OverviewView({ sentiment }) {
  const fg = sentiment?.fear_greed;
  return (
    <div className="sentiment-overview">
      <div className="sentiment-pill">
        <span className="sentiment-score">{fg?.value ?? "—"}</span>
        <small>{fg?.classification ?? "neutral"}</small>
      </div>
      <p className="sentiment-caption">
        Updated {sentiment.timestamp ? new Date(sentiment.timestamp).toLocaleTimeString() : "recently"}
      </p>
    </div>
  );
}

function FundingView({ sentiment }) {
  const f = sentiment?.btc_funding;
  return (
    <div className="sentiment-funding">
      <p>
        BTC funding: {f?.rate_percentage != null ? `${f.rate_percentage.toFixed(4)}%` : "—"}
      </p>
      <p className="sentiment-caption">
        Positive → perp premium (long bias). Negative → short pressure.
      </p>
    </div>
  );
}

function SourcesView({ sentiment }) {
  return (
    <div className="sentiment-sources">
      <p>Sources blended from your sentiment orchestrator.</p>
      <pre className="sentiment-raw">{JSON.stringify(sentiment.sources || {}, null, 2)}</pre>
    </div>
  );
}

