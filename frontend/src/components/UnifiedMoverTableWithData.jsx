import React from "react";
import PropTypes from "prop-types";
import { useGainersLosersData } from "../hooks/useGainersLosersData";
import UnifiedMoverTable from "./UnifiedMoverTable";

export default function UnifiedMoverTableWithData({ title, variant, window = "3min", className = "" }) {
  const { rows, loading, error } = useGainersLosersData({ variant, window });

  if (loading && (!rows || rows.length === 0)) {
    return (
      <div className={`bg-black/40 border border-gray-800 rounded-xl p-3 shadow-[0_0_20px_rgba(0,0,0,0.8)] ${className}`}>
        <div className="h-64 flex items-center justify-center">
          <div className="animate-pulse text-gray-400 text-sm">Loading {title}...</div>
        </div>
      </div>
    );
  }

  if (error && (!rows || rows.length === 0)) {
    return (
      <div className={`bg-black/40 border border-gray-800 rounded-xl p-3 shadow-[0_0_20px_rgba(0,0,0,0.8)] ${className}`}>
        <div className="h-64 flex items-center justify-center">
          <div className="text-red-400 text-sm">Error loading {title}</div>
        </div>
      </div>
    );
  }

  return (
    <div className={className}>
      <UnifiedMoverTable title={title} rows={rows} />
    </div>
  );
}

UnifiedMoverTableWithData.propTypes = {
  title: PropTypes.string.isRequired,
  variant: PropTypes.string.isRequired,
  window: PropTypes.string,
  className: PropTypes.string,
};