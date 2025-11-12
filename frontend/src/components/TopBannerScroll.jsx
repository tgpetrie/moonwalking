import React from "react";
import { formatPrice, formatPct } from "../utils/format.js";

export default function TopBannerScroll({ banner = [] }) {
  if (!banner || !banner.length) return null;
  return (
    <div className="bh-top-banner">
      <div className="bh-banner-track">
        {banner.map((item) => (
          <div key={item.symbol} className="bh-banner-chip">
            <span>{item.symbol}</span>
            <span>{formatPrice(item.current_price)}</span>
            <span className={item.price_change_1h >= 0 ? "up small" : "down small"}>
              {formatPct(item.price_change_1h)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
import React from "react";
import { formatPrice, formatPct } from "../utils/format.js";

export default function TopBannerScroll({ items = [], loading }) {
  return (
    <div className="bh-top-banner">
      {loading && !items.length ? (
        <span style={{ opacity: 0.6, fontSize: "0.7rem", padding: "0.35rem 0.75rem", display: "inline-block" }}>
          loading 1h volume…
        </span>
      ) : !items.length ? (
        <span style={{ opacity: 0.5, fontSize: "0.7rem", padding: "0.35rem 0.75rem", display: "inline-block" }}>
          no 1h banner data
        </span>
      ) : (
        <div className="bh-banner-strip">
          {items.map((it, i) => (
            <div key={(it.symbol || it.ticker || i) + "-chip"} className="bh-banner-chip">
              <span>{it.symbol || it.ticker}</span>
              {it.current_price != null && <span>{formatPrice(it.current_price)}</span>}
              {it.price_change_1h != null && <span>{formatPct(it.price_change_1h)}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

