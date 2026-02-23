// frontend/src/components/AssetTabbedPanel.jsx
import React, { useState } from "react";
import SentimentPopupAdvanced from "./SentimentPopupAdvanced.jsx";

export default function AssetTabbedPanel({ asset, onClose }) {
  const [isCoinPressureOpen, setIsCoinPressureOpen] = useState(false);
  if (!asset) return null;
  const { symbol } = asset;

  return (
    <div
      style={{
        position: "fixed",
        right: "1.5rem",
        top: "5.5rem",
        width: "360px",
        background: "rgba(0,0,0,0.85)",
        border: "1px solid rgba(255,255,255,0.05)",
        borderRadius: "0.75rem",
        padding: "1rem",
        backdropFilter: "blur(6px)",
        zIndex: 100,
      }}
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold">{symbol}</h3>
        <button onClick={onClose} className="text-xs opacity-70 hover:opacity-100">
          Close
        </button>
      </div>

      <div className="mw-coin-pressure-launch">
        <button
          type="button"
          className="btn-show-more"
          onClick={() => setIsCoinPressureOpen(true)}
        >
          Open Coin Pressure
        </button>

        <SentimentPopupAdvanced
          isOpen={isCoinPressureOpen}
          onClose={() => setIsCoinPressureOpen(false)}
          symbol={symbol}
          defaultTab="coin"
        />
      </div>
    </div>
  );
}
