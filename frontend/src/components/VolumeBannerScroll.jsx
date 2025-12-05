import React, { useEffect, useState, useMemo } from "react";
import { formatCompact, formatPct, map1hVolumeBannerItemBase } from "../utils/format";
import PanelShell from "./ui/PanelShell";
import StatusGate from "./ui/StatusGate";
import SkeletonBlock from "./ui/SkeletonBlock";

// historyMinutes is passed from Dashboard/useData for warm-up logic
export default function VolumeBannerScroll({
  items,
  historyMinutes = 0,
  loading = false,
  error = null,
}) {
  const [data, setData] = useState(items || []);

  useEffect(() => {
    if (items && items.length) return;
    fetch("/api/component/bottom-banner-scroll")
      .then((r) => r.json())
      .then((json) => {
        const arr = json?.items || json || [];
        setData(arr);
      })
      .catch(() => {});
  }, [items]);

  const list = items && items.length ? items : data;

  const mapped = useMemo(() => {
    return list
      .map((row) => map1hVolumeBannerItemBase(row))
      .filter((it) => it && it.currentVolume != null && it.pctChange !== 0)
      .sort((a, b) => Math.abs(b.pctChange) - Math.abs(a.pctChange))
      .slice(0, 20);
  }, [list]);

  const required = 60;
  const panelStatus =
    error ? "error" :
    mapped.length > 0 ? "ready" :
    loading ? "loading" :
    historyMinutes < required ? "loading" : "empty";

  const looped = mapped && mapped.length ? [...mapped, ...mapped] : [];

  return (
    <PanelShell title="1H VOLUME" timeframe="ACTIVITY" tone="loss">
      <StatusGate
        status={panelStatus}
        skeleton={
          <div className="bh-banner-wrap">
            <SkeletonBlock lines={2} />
          </div>
        }
        empty={
          <div className="bh-banner-wrap">
            <div className="ticker bh-banner bh-banner--volume">
              <div className="bh-banner-track">
                <span className="state-copy">No 1h volume activity yet.</span>
              </div>
            </div>
          </div>
        }
        error={<div className="state-copy">Feed hiccup. Retrying.</div>}
      >
        <div className="bh-banner-wrap">
          <div className="bh-banner-track">
            {(looped.length ? looped : [{ symbol: "--", currentVolume: null, pctChange: 0 }]).map((it, i) => {
              if (!it) return null;
              const baseLen = mapped.length || 1;
              const pct = Number(it?.pctChange ?? 0);
              const pctClass =
                pct > 0
                  ? "bh-banner-chip__pct bh-banner-chip__pct--gain"
                  : pct < 0
                  ? "bh-banner-chip__pct bh-banner-chip__pct--loss"
                  : "bh-banner-chip__pct bh-banner-chip__pct--flat";
              const rank = baseLen > 0 ? (i % baseLen) + 1 : i + 1;

              return (
                <a
                  key={`${it.symbol || "item"}-${i}`}
                  className="bh-banner-chip bh-banner-chip--volume"
                  href={it.symbol ? `https://www.coinbase.com/advanced-trade/spot/${it.symbol}-USD` : "#"}
                  target="_blank"
                  rel="noreferrer"
                >
                  <span className="bh-banner-chip__rank">{rank}</span>
                  <span className="bh-banner-chip__symbol">{it.symbol}</span>
                  <span className="bh-banner-chip__price">
                    {it.currentVolume != null
                      ? `Vol ${formatCompact(it.currentVolume)}`
                      : "Vol —"}
                  </span>
                  <span className={pctClass}>
                    {formatPct(pct, { sign: true })}
                  </span>
                </a>
              );
            })}
          </div>
        </div>
      </StatusGate>
    </PanelShell>
  );
}
