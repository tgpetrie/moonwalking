import React, { useState } from "react";
import SentimentCard from "./cards/SentimentCard.jsx";

export default function InsightsTabbed({ row }) {
  const [active, setActive] = useState("charts");

  return (
    <div className="insights-card">
      <div className="insights-tabs">
        <button
          className={active === "charts" ? "active" : ""}
          onClick={() => setActive("charts")}
        >
          Charts
        </button>
        <button
          className={active === "sentiment" ? "active" : ""}
          onClick={() => setActive("sentiment")}
        >
          Sentiment
        </button>
        <button
          className={active === "social" ? "active" : ""}
          onClick={() => setActive("social")}
        >
          Social
        </button>
      </div>

      <div className="insights-body">
        {active === "charts" && <div className="insights-placeholder">[chart goes here]</div>}
        {active === "sentiment" && <SentimentCard row={row} />}
        {active === "social" && <div className="insights-placeholder">[social feed]</div>}
      </div>
    </div>
  );
}
