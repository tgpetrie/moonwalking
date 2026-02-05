// frontend/src/components/AssetTabbedPanel.jsx
import React from "react";
import SentimentCard from "./cards/SentimentCard.jsx";

export default function AssetTabbedPanel({ asset, onClose }) {
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
      <SentimentCard symbol={symbol} ttlSec={30} />
    </div>
  );
}

