import React from "react";
import { formatCompact, formatPct, calcVolumeChange1h } from "../utils/format.js";

export default function TopBannerVolume1h({ items = [] }) {
  // items: this should be your payload.banner_1h from /data
  if (!Array.isArray(items) || items.length === 0) {
    return (
      <div className="bh-top-banner">
        <span className="banner-empty">No 1h activity yet.</span>
      </div>
    );
  }

  return (
    <div className="bh-top-banner bh-top-banner-scroll">
      <div className="bh-top-banner-track">
        {items.map((t, idx) => {
          const symbol = t.symbol || t.ticker || `#${idx + 1}`;
          const volChange = calcVolumeChange1h(t);
          // show the actual 1h volume too if we have it
          const volActual =
            t.volume_1h ?? t.volume_60m ?? t.volume_last_1h ?? t.volume_1h_usd ?? null;

          return (
            <div key={symbol + idx} className="bh-banner-chip">
              <span className="bh-banner-symbol">{symbol}</span>
              {volChange != null ? (
                <span
                  className={
                    volChange >= 0 ? "bh-banner-change up" : "bh-banner-change down"
                  }
                >
                  {formatPct(volChange)}
                </span>
              ) : (
                <span className="bh-banner-change muted">—</span>
              )}
              {volActual != null ? (
                <span className="bh-banner-vol">{formatCompact(volActual)} / 1h</span>
              ) : null}
            </div>
          );
        })}
        {/* duplicate once so it can scroll infinitely if you animate it */}
        {items.map((t, idx) => {
          const symbol = t.symbol || t.ticker || `#${idx + 1}-dup`;
          const volChange = calcVolumeChange1h(t);
          const volActual =
            t.volume_1h ?? t.volume_60m ?? t.volume_last_1h ?? t.volume_1h_usd ?? null;

          return (
            <div key={symbol + "-dup"} className="bh-banner-chip">
              <span className="bh-banner-symbol">{symbol}</span>
              {volChange != null ? (
                <span
                  className={
                    volChange >= 0 ? "bh-banner-change up" : "bh-banner-change down"
                  }
                >
                  {formatPct(volChange)}
                </span>
              ) : (
                <span className="bh-banner-change muted">—</span>
              )}
              {volActual != null ? (
                <span className="bh-banner-vol">{formatCompact(volActual)} / 1h</span>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
