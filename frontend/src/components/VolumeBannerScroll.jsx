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
      .map((it, index) => ({ ...it, rank: index + 1 }));
  }, [list]);

  const required = 60;
  const panelStatus =
    error ? "error" :
    mapped.length > 0 ? "ready" :
    loading ? "loading" :
    historyMinutes < required ? "loading" : "empty";

  return (
    <PanelShell title="1H VOLUME">
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
          <div className="ticker bh-banner bh-banner--volume">
            <div className="bh-banner-track bh-banner-strip__inner">
              {mapped.map((it) => (
                <span
                  key={it.symbol}
                  className={`bh-banner-chip bh-banner-chip--volume ${
                    it.isGain ? "is-gain" : it.isLoss ? "is-loss" : ""
                  }`}
                >
                  <span className="bh-banner-chip__rank">{it.rank}</span>
                  <span className="bh-banner-chip__symbol">{it.symbol}</span>
                  <span className="bh-banner-chip__price">
                    {it.currentVolume != null
                      ? `Vol ${formatCompact(it.currentVolume)}`
                      : "Vol —"}
                  </span>
                  <span className="bh-banner-chip__pct">
                    {formatPct(it.pctChange, { sign: true })}
                  </span>
                </span>
              ))}
            </div>
          </div>
        </div>
      </StatusGate>
    </PanelShell>
  );
}
