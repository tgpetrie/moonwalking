import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useData } from "../hooks/useData";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";

function toNum(v) {
  const n = typeof v === "string" ? Number(v) : v;
  return Number.isFinite(n) ? n : null;
}

function fmtVolume(n) {
  const v = Number(n);
  if (!Number.isFinite(v) || v <= 0) return "—";
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toFixed(0);
}

function fmtPct(n) {
  if (!Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  const d = abs < 0.1 ? 4 : abs < 1 ? 3 : 2;
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(d)}%`;
}

function normalizeVolItem(raw, idx) {
  if (!raw) return null;

  const symbolRaw =
    raw.symbol ||
    raw.ticker ||
    (typeof raw.product_id === "string" ? raw.product_id.split("-")[0] : null) ||
    null;

  const symbol = symbolRaw ? symbolRaw.replace(/-usd$|-usdt$|-perp$/i, "").toUpperCase() : null;
  const productId = raw.product_id || raw.productId || (symbol ? `${symbol}-USD` : null);

  const volumeNow =
    toNum(raw.volume_1h_now) ??
    toNum(raw.volume_1h) ??
    toNum(raw.volume_now) ??
    toNum(raw.vol1h) ??
    toNum(raw.volume) ??
    toNum(raw.volume_24h) ??
    null;

  const pct =
    toNum(raw.volume_change_1h_pct) ??
    toNum(raw.volume_change_pct_1h) ??
    toNum(raw.volume_change_pct) ??
    toNum(raw.changePct) ??
    toNum(raw.pct_change) ??
    toNum(raw.pct) ??
    null;

  const baseline =
    toNum(raw.volume_1h_prev) ??
    toNum(raw.volume_prev_1h) ??
    toNum(raw.volume_prev) ??
    toNum(raw.volume_1h_ago) ??
    null;

  const rank = toNum(raw.rank) ?? idx + 1;

  if (!symbol && !productId) return null;

  return {
    key: String(productId || symbol || idx),
    symbol: String(symbol || productId),
    product_id: productId,
    volumeNow,
    pct,
    baseline,
    rank,
  };
}

export function VolumeBannerScroll({
  tokens,
  items: itemsProp,
  data,
  volume,
  speed = 36,
  loading = false,
}) {
  const { volume1h } = useData();
  const [paused, setPaused] = useState(false);

  const trackRef = useRef(null);
  const rafRef = useRef(null);
  const lastTsRef = useRef(null);
  const xRef = useRef(0);
  const halfWidthRef = useRef(0);

  const rawList = useMemo(() => {
    const candidate = tokens ?? itemsProp ?? data ?? volume ?? volume1h ?? [];
    return Array.isArray(candidate) ? candidate : [];
  }, [tokens, itemsProp, data, volume, volume1h]);

  const items = useMemo(() => {
    const out = [];
    for (let i = 0; i < rawList.length; i += 1) {
      const n = normalizeVolItem(rawList[i], i);
      if (n) out.push(n);
    }
    return out;
  }, [rawList]);

  const doubled = useMemo(() => (items.length ? [...items, ...items] : []), [items]);
  const showFallback = items.length === 0;

  const computeHalfWidth = useCallback(() => {
    const el = trackRef.current;
    if (!el) {
      halfWidthRef.current = 0;
      return;
    }
    const w = el.scrollWidth;
    halfWidthRef.current = w > 0 ? w / 2 : 0;
  }, []);

  useEffect(() => {
    computeHalfWidth();

    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => computeHalfWidth()) : null;
    if (ro && trackRef.current) ro.observe(trackRef.current);

    const onResize = () => computeHalfWidth();
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      if (ro) ro.disconnect();
    };
  }, [computeHalfWidth, items.length]);

  useEffect(() => {
    xRef.current = 0;
    lastTsRef.current = null;
    if (trackRef.current) trackRef.current.style.transform = "translate3d(0,0,0)";
  }, [items.length]);

  const tick = useCallback(
    (ts) => {
      if (lastTsRef.current == null) lastTsRef.current = ts;
      const dt = Math.max(0, ts - lastTsRef.current);
      lastTsRef.current = ts;

      const prefersReduce =
        typeof window !== "undefined" &&
        window.matchMedia &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      const half = halfWidthRef.current;

      if (!paused && !prefersReduce && half > 0) {
        const dx = (Number(speed) || 0) * (dt / 1000);
        xRef.current -= dx;
        if (xRef.current <= -half) xRef.current += half;
        if (trackRef.current) {
          trackRef.current.style.transform = `translate3d(${xRef.current}px, 0, 0)`;
        }
      }

      rafRef.current = window.requestAnimationFrame(tick);
    },
    [paused, speed]
  );

  useEffect(() => {
    rafRef.current = window.requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) window.cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      lastTsRef.current = null;
    };
  }, [tick]);

  const onEnter = useCallback(() => setPaused(true), []);
  const onLeave = useCallback(() => setPaused(false), []);

  if (showFallback) {
    const emptyCopy = loading ? "Warming up volume feed…" : "No 1h volume activity yet.";
    return (
      <div className="bh-banner bh-banner--bottom">
        <div className="bh-banner-wrap" onMouseEnter={onEnter} onMouseLeave={onLeave}>
          <div className="bh-banner-track bh-banner-track--manual">
            <span className="bh-banner-empty">{emptyCopy}</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bh-banner bh-banner--bottom">
      <div className="bh-banner-wrap" onMouseEnter={onEnter} onMouseLeave={onLeave}>
        <div ref={trackRef} className="bh-banner-track bh-banner-track--manual" style={{ transform: "translate3d(0,0,0)" }}>
          {doubled.map((it, i) => {
            const pct = Number.isFinite(it.pct) ? it.pct : null;
            const stateClass = pct == null ? "is-flat" : pct >= 0 ? "is-gain" : "is-loss";
            const url = coinbaseSpotUrl({ ...it, product_id: it.product_id });

            const chip = (
              <>
                <span className="bh-banner-chip__rank">{it.rank}</span>
                <span className="bh-banner-chip__sym">{it.symbol || "--"}</span>
                <span className="bh-banner-right">
                  <span className="bh-banner-chip__price">{fmtVolume(it.volumeNow)} vol</span>
                  <span className={`bh-banner-chip__pct ${stateClass === "is-gain" ? "bh-banner-change--pos" : stateClass === "is-loss" ? "bh-banner-change--neg" : ""}`}>
                    {fmtPct(pct)}
                  </span>
                </span>
              </>
            );

            if (!url) {
              return (
                <div key={`${it.key}-${i}`} className={`bh-banner-chip ${stateClass}`}>
                  {chip}
                </div>
              );
            }

            return (
              <a
                key={`${it.key}-${i}`}
                className={`bh-banner-chip ${stateClass}`}
                href={url}
                target="_blank"
                rel="noreferrer"
                onClick={(e) => {
                  if (!url) e.preventDefault();
                }}
              >
                {chip}
              </a>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default VolumeBannerScroll;
