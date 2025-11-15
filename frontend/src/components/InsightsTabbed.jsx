import React, { useState } from "react";
import SentimentCard from "./cards/SentimentCard.jsx";
import { tickerFromSymbol } from "../utils/format.js";

export default function InsightsTabbed({ row }) {
  const [active, setActive] = useState("charts");
  const raw = row?.symbol || row?.ticker || "";
  const symbol = tickerFromSymbol(raw || "");

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
        {active === "charts" && (
          <div className="insights-placeholder">[chart goes here]</div>
        )}
        {active === "sentiment" && (
          <SentimentCard symbol={symbol} ttlSec={30} />
        )}
        {active === "social" && (
          <div className="insights-placeholder">[social feed]</div>
        )}
      </div>
    </div>
  );
}
