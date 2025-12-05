import React, { useMemo } from "react";
import { useDataFeed } from "../hooks/useDataFeed";

export default function VolumeBannerScroll() {
  const { data } = useDataFeed();

  const rows = useMemo(() => {
    if (!data) return [];
    const payload = data?.data ?? data ?? {};

    const raw = Array.isArray(payload.banner_volume_1h)
      ? payload.banner_volume_1h
      : Array.isArray(payload.volume_1h?.data)
      ? payload.volume_1h.data
      : Array.isArray(payload.volume_1h_top)
      ? payload.volume_1h_top
      : Array.isArray(payload.volume_1h_tokens)
      ? payload.volume_1h_tokens
      : [];

    return raw;
  }, [data]);

  const items = useMemo(() => {
    const base = Array.isArray(rows) ? rows : [];
    if (!base.length) return [];

    const sorted = [...base].sort((a, b) => {
      const av = a?.volume_change_abs ?? a?.volume_change ?? 0;
      const bv = b?.volume_change_abs ?? b?.volume_change ?? 0;
      return bv - av;
    });
    const sliced = sorted.slice(0, 30);
    return [...sliced, ...sliced];
  }, [rows]);

  if (!items.length) {
    return (
      <div className="bh-banner-wrap bh-banner-wrap--volume">
        <p className="bh-banner-empty">No 1h volume activity yet.</p>
      </div>
    );
  }

  return (
    <div className="bh-banner-wrap bh-banner-wrap--volume">
      <div className="bh-banner-track">
        {items.map((row, idx) => (
          <a
            key={`${row.symbol || "item"}-${idx}`}
            className="bh-banner-chip"
            href={`https://www.coinbase.com/price/${(row.symbol || "").toLowerCase()}`}
            target="_blank"
            rel="noreferrer"
          >
            <span className="bh-banner-symbol">{row.symbol}</span>
            <span className="bh-banner-price">
              {row.current_price != null ? `$${row.current_price}` : "-"}
            </span>
            <span
              className={
                (row.change_1h_volume ?? row.volume_change ?? 0) >= 0
                  ? "bh-banner-pct bh-banner-pct--gain"
                  : "bh-banner-pct bh-banner-pct--loss"
              }
            >
              {row.change_1h_volume != null
                ? `${row.change_1h_volume.toFixed?.(2) ?? row.change_1h_volume}%`
                : `${row.volume_change?.toFixed?.(2) ?? row.volume_change ?? 0}%`}
            </span>
          </a>
        ))}
      </div>
    </div>
  );
}
