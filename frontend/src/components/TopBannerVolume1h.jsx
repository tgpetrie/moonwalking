// frontend/src/components/TopBannerVolume1h.jsx — cleaned single export
import React, { useMemo } from "react";
import { formatCompact, formatPct, tickerFromSymbol } from "../utils/format";
import { useBannerLensMarquee } from "../hooks/useBannerLensMarquee";

export default function TopBannerVolume1h({ rows = [], items: propItems = [] }) {
  const raw = Array.isArray(propItems) && propItems.length ? propItems : (Array.isArray(rows) ? rows : []);

  const items = useMemo(
    () =>
      raw
        .map((t) => ({
          symbol: tickerFromSymbol(t?.symbol ?? t?.ticker ?? ""),
          volume_now: Number(t?.volume_1h ?? t?.volume ?? 0),
          pct: Number(
            t?.volume_change_percentage_1h ??
              t?.volume_change_pct_1h ??
              t?.volume_change_pct ??
              0
          ),
        }))
        .filter((t) => t.symbol && t.volume_now && t.pct !== 0),
    [raw]
  );

  const { wrapRef, trackRef } = useBannerLensMarquee(42, [items?.length]);

  const source = items;
  const looped = source.length ? [...source, ...source] : source;

  if (!items.length) {
    return (
      <section className="banner-section banner-section--volume">
        <div className="banner-section-heading">
          <span className="banner-section-heading__label">1H VOLUME</span>
          <span className="banner-section-heading__rail" />
        </div>
        <div className="bh-top-banner bh-banner--volume">
          <div className="bh-banner-wrap">
            <span className="banner-empty">No 1h volume activity yet.</span>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="banner-section banner-section--volume">
      <div className="banner-heading">
        <span className="banner-heading__label">1H VOLUME</span>
        <span className="banner-heading__rail" />
      </div>
      <div className="ticker bh-banner bh-banner--volume">
        <div className="bh-banner-wrap" ref={wrapRef}>
          <div className="bh-banner-track bh-banner-track--manual" ref={trackRef}>
            {looped.map((it, i) => {
              if (!it) return null;
              const cls = it.pct >= 0 ? "is-gain" : "is-loss";
              return (
                <span
                  key={`${it.symbol}-${i}`}
                  className={`bh-banner-item ${cls}`}
                >
                  <b className="bh-banner-symbol">{it.symbol || "--"}</b>
                  <span className="bh-banner-price">{it.volume_now ? formatCompact(it.volume_now) : "--"}</span>
                  <span className="bh-banner-pct">
                    {Number.isFinite(it.pct) ? formatPct(it.pct) : "--"}
                  </span>
                </span>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
