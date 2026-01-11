import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

const COINBASE_ORIGIN = "https://www.coinbase.com";

function toAdvancedTradeUrl(item) {
  const rawPair = item?.product_id || item?.productId || item?.pair || item?.symbol;
  if (!rawPair) return null;

  const rawSymbol = item?.symbol ?? null;
  const symbol = rawSymbol ? String(rawSymbol).replace(/-.*$/, "").toUpperCase().trim() : null;

  let pair = String(rawPair).toUpperCase().trim();
  if (!pair) return null;
  if (!pair.includes("-")) pair = `${pair}-USD`;
  if (!pair.endsWith("-USD") && symbol) pair = `${symbol}-USD`;

  return `${COINBASE_ORIGIN}/advanced-trade/spot/${encodeURIComponent(pair)}`;
}

function toNum(v) {
  if (v == null) return null;

  if (typeof v === "string") {
    let s = v.trim();
    if (!s) return null;
    s = s.replace(/,/g, "");
    s = s.replace(/%/g, "");
    const n = Number(s);
    return Number.isFinite(n) ? n : null;
  }

  return Number.isFinite(v) ? v : null;
}

function pickNumber(obj, fields = []) {
  if (!obj) return null;
  for (const key of fields) {
    const n = toNum(obj[key]);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function fmtPct(n) {
  if (!Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  const d = abs >= 100 ? 0 : abs >= 10 ? 1 : abs >= 1 ? 2 : abs >= 0.1 ? 3 : 4;
  const sign = n > 0 ? "+" : "";
  const trimmed = n
    .toFixed(d)
    .replace(/\.0+$/, "")
    .replace(/(\.\d*[1-9])0+$/, "$1");
  return `${sign}${trimmed}%`;
}

function fmtPrice(n) {
  if (!Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  const d = abs >= 100 ? 2 : abs >= 1 ? 4 : 6;
  return n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: d });
}

function normalizeItem(raw, idx) {
  if (!raw) return null;

  const symbol =
    raw.symbol ||
    raw.ticker ||
    (typeof raw.product_id === "string" ? raw.product_id.split("-")[0] : null) ||
    null;

  const productId = raw.product_id || (symbol ? `${symbol}-USD` : null);

  const current =
    pickNumber(raw, ["current_price", "price", "last", "latest_price", "close_price"]) ?? null;

  const baseline = pickNumber(raw, [
    "initial_price_1h",
    "initial_price_1min",
    "price_1h_ago",
    "price_1m_ago",
    "baseline_price",
    "open_price",
  ]);

  const directPct = toNum(raw?.price_change_1h);
  const pct =
    Number.isFinite(directPct) ? directPct : baseline && current && baseline !== 0 ? ((current - baseline) / baseline) * 100 : null;

  const price = current ?? baseline ?? null;

  const rank = toNum(raw.rank) ?? idx + 1;

  if (!symbol && !productId) return null;

  return {
    key: String(productId || symbol || idx),
    symbol: String(symbol || productId),
    productId: String(productId || symbol),
    pct,
    price,
    rank,
  };
}

export default function TopBannerScroll(props) {
  const {
    endpoint = null,
    speed = 36,
    className = "",
    title = "",
    items: itemsProp,
    data,
    banner,
    tokens,
    topBanner,
  } = props || {};

  const [localItems, setLocalItems] = useState([]);
  const [fetchErr, setFetchErr] = useState(null);
  const [paused, setPaused] = useState(false);

  const trackRef = useRef(null);
  const rafRef = useRef(null);
  const lastTsRef = useRef(null);
  const xRef = useRef(0);
  const halfWidthRef = useRef(0);

  const rawList = useMemo(() => {
    const candidate = itemsProp ?? data ?? banner ?? tokens ?? topBanner ?? localItems ?? [];
    return Array.isArray(candidate) ? candidate : [];
  }, [itemsProp, data, banner, tokens, topBanner, localItems]);

  const items = useMemo(() => {
    const out = [];
    for (let i = 0; i < rawList.length; i += 1) {
      const n = normalizeItem(rawList[i], i);
      if (n) out.push(n);
    }
    return out;
  }, [rawList]);

  useEffect(() => {
    const hasExternalList =
      Array.isArray(itemsProp) ||
      Array.isArray(data) ||
      Array.isArray(banner) ||
      Array.isArray(tokens) ||
      Array.isArray(topBanner);

    if (!endpoint || hasExternalList) return;

    const API_BASE = (import.meta?.env?.VITE_API_BASE_URL || "").trim();
    const url = endpoint.startsWith("http") ? endpoint : `${API_BASE}${endpoint}`;

    const ac = new AbortController();
    const t = setTimeout(() => ac.abort("signal timed out"), 6500);

    (async () => {
      try {
        setFetchErr(null);
        const res = await fetch(url, { signal: ac.signal, cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        const arr = Array.isArray(json) ? json : Array.isArray(json?.items) ? json.items : [];
        setLocalItems(arr);
      } catch (e) {
        setFetchErr(String(e?.message || e));
      } finally {
        clearTimeout(t);
      }
    })();

    return () => {
      clearTimeout(t);
      ac.abort();
    };
  }, [endpoint, itemsProp, data, banner, tokens, topBanner]);

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
        if (xRef.current <= -half) xRef.current = 0;
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

  const doubled = useMemo(() => (items.length ? [...items, ...items] : []), [items]);
  const showFallback = items.length === 0;

  return (
    <div className={`bh-topbanner ${className}`.trim()}>
      {title ? <div className="bh-topbanner__title">{title}</div> : null}

      <div className="bh-banner-scroll" onMouseEnter={onEnter} onMouseLeave={onLeave} role="region" aria-label="Top banner scroll">
        <div ref={trackRef} className="bh-banner-track bh-banner-track--manual" style={{ transform: "translate3d(0,0,0)" }}>
          {showFallback ? (
            <div className="bh-banner-chip bh-banner-chip--muted">
              <span className="bh-banner-chip__rank">LIVE</span>
              <span className="bh-banner-chip__sym">Waiting for banner data</span>
              <span className="bh-banner-chip__pct">—</span>
              <span className="bh-banner-chip__price">{fetchErr ? "fetch failed" : ""}</span>
            </div>
          ) : (
            doubled.map((it, i) => {
              const isUp = Number.isFinite(it.pct) ? it.pct >= 0 : true;
              const href = toAdvancedTradeUrl({ product_id: it.productId, symbol: it.symbol }) || "#";

              return (
                <a
                  key={`${it.key}-${i}`}
                  className={`bh-banner-chip ${isUp ? "is-up" : "is-down"}`}
                  href={href}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(e) => {
                    if (href === "#") e.preventDefault();
                  }}
                >
                  <span className="bh-banner-chip__rank">{it.rank}</span>
                  <span className="bh-banner-chip__sym">{it.symbol}</span>
                  <span className="bh-banner-right">
                    <span className="bh-banner-chip__pct">{fmtPct(it.pct ?? NaN)}</span>
                    <span className="bh-banner-chip__price">{fmtPrice(it.price ?? NaN)}</span>
                  </span>
                </a>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
