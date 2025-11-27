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

  const shouldScroll = (mapped?.length || 0) >= 15;
  const looped = shouldScroll ? [...mapped, ...mapped] : mapped;

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
            <div className="bh-banner-strip bh-banner-strip--volume">
              <div
                className={
                  "bh-banner-strip__inner" +
                  (shouldScroll ? " bh-banner-strip__inner--scroll" : "")
                }
              >
                {looped.map((it, i) => {
                  if (!it) return null;
                  const baseLen = mapped.length || 1;
                  const pct = Number(it?.pctChange ?? 0);
                  const chipState = pct > 0 ? "is-gain" : pct < 0 ? "is-loss" : "";
                  const rank = (i % baseLen) + 1;

                  return (
                    <span
                      key={`${it.symbol || "item"}-${i}`}
                      className={`bh-banner-chip bh-banner-chip--volume ${chipState}`}
                    >
                      <span className="bh-banner-chip__rank">{rank}</span>
                      <span className="bh-banner-chip__symbol">{it.symbol}</span>
                      <span className="bh-banner-chip__price">
                        {it.currentVolume != null
                          ? `Vol ${formatCompact(it.currentVolume)}`
                          : "Vol —"}
                      </span>
                      <span className="bh-banner-chip__pct">
                        {formatPct(pct, { sign: true })}
                      </span>
                    </span>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </StatusGate>
    </PanelShell>
  );
}
