import React, { useMemo } from "react";
import PropTypes from "prop-types";
import UnifiedMoverTable from "./UnifiedMoverTable";
import { useWebSocket } from "../context/websocketcontext.jsx";

export default function Unified1MinGainersTable({ className = "" }) {
  const { latestData, isPolling, error } = useWebSocket();
  const rows = useMemo(
    () => (Array.isArray(latestData?.crypto) ? latestData.crypto.slice(0, 20) : []),
    [latestData?.crypto],
  );

  if (error && rows.length === 0) {
    return (
      <div className={`bg-black/40 border border-gray-800 rounded-xl p-3 shadow-[0_0_20px_rgba(0,0,0,0.8)] ${className}`}>
        <div className="h-64 flex items-center justify-center">
          <div className="text-red-400 text-sm">Error loading 1-min gainers</div>
        </div>
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className={`bg-black/40 border border-gray-800 rounded-xl p-3 shadow-[0_0_20px_rgba(0,0,0,0.8)] ${className}`}>
        <div className="h-64 flex items-center justify-center">
          <div className="animate-pulse text-gray-400 text-sm">
            {isPolling ? "Loading 1-min gainers..." : "No 1-min gainers yet"}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={className}>
      <UnifiedMoverTable title="1-MIN GAINERS" rows={rows} />
    </div>
  );
}

Unified1MinGainersTable.propTypes = {
  className: PropTypes.string,
};
