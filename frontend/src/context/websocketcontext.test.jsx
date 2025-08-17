import React, { useEffect, useRef, useState } from "react";
import { fetchData } from "../api.js";

// Find price approximately lookbackSec ago (±toleranceSec) from a sorted (asc) history array
function priceAt(history, nowMs, lookbackSec = 60, toleranceSec = 10) {
  const target = nowMs - lookbackSec * 1000;
  let best = null;
  for (let i = history.length - 1; i >= 0; i--) {
    const p = history[i];
    if (Math.abs(p.ts - target) <= toleranceSec * 1000) { best = p; break; }
    if (p.ts < target) { best = p; break; } // fallback: nearest older snapshot
  }
  return best?.price ?? null;
}

const formatPct = (v) => (typeof v === "number" && isFinite(v) ? `${v.toFixed(2)}%` : "—");
const formatNum = (v) => (typeof v === "number" && isFinite(v) ? v.toLocaleString() : "—");

function extractTickers(data) {
  // Prefer a canonical tickers list if present
  if (Array.isArray(data?.tickers)) return data.tickers;
  // Otherwise, merge from any sections that include {symbol, price}
  const pools = [
    data?.gainers,
    data?.losers,
    data?.banner,
    data?.top1m,
    data?.top3m,
    data?.all,
  ];
  const merged = [];
  const seen = new Set();
  for (const arr of pools) {
    if (!Array.isArray(arr)) continue;
    for (const t of arr) {
      const sym = t?.symbol;
      if (!sym || seen.has(sym)) continue;
      const price = (t?.price ?? t?.last ?? t?.current_price);
      if (price == null) continue;
      seen.add(sym);
      merged.push({ symbol: sym, price: Number(price) });
    }
  }
  return merged;
}

export default function GainersTable1Min({ refreshMs = 10000, limit = 10 }) {
  const [rows, setRows] = useState([]); // [{symbol, price, prev1m, pct1m}]
  const historyRef = useRef(new Map()); // Map<symbol, Array<{ts:number, price:number}>>

  useEffect(() => {
    let timer = null;
    let mounted = true;

    async function tick() {
      const now = Date.now();
      const data = await fetchData();
      const tickersRaw = extractTickers(data);
      const tickers = Array.isArray(tickersRaw) ? tickersRaw : [];

      // Append to per-symbol history
      for (const t of tickers) {
        const key = t.symbol; // keep EXACT same key everywhere (e.g., "BTC-USD")
        const arr = historyRef.current.get(key) ?? [];
        const price = Number(t.price);
        if (!Number.isNaN(price)) {
          arr.push({ ts: now, price });
          // keep ~5 minutes of snapshots
          const cutoff = now - 5 * 60 * 1000;
          while (arr.length && arr[0].ts < cutoff) arr.shift();
          historyRef.current.set(key, arr);
        }
      }

      // Build view rows with prev + pct
      const next = tickers.map((t) => {
        const arr = historyRef.current.get(t.symbol) ?? [];
        const prev = priceAt(arr, now, 60, 12);
        const curr = Number(t.price);
        const pct = prev ? ((curr - prev) / prev) * 100 : null;
        return { symbol: t.symbol, price: curr, prev1m: prev ?? null, pct1m: Number.isFinite(pct) ? pct : null };
      });

      // Sort by % desc for gainers, filter rows without pct
      const gainers = next.filter(r => r.pct1m != null).sort((a, b) => b.pct1m - a.pct1m);
      if (mounted) setRows(gainers.slice(0, limit));
    }

    tick();
    timer = setInterval(tick, refreshMs);
    return () => { mounted = false; if (timer) clearInterval(timer); };
  }, [refreshMs, limit]);

  return (
    <div className="text-sm">
      <div className="grid grid-cols-4 opacity-70">
        <div>Symbol</div><div>Price</div><div>Prev (1m)</div><div>% 1m</div>
      </div>
      {rows.map((r) => (
        <div key={r.symbol} className="grid grid-cols-4 py-1">
          <div>{r.symbol}</div>
          <div>{formatNum(r.price)}</div>
          <div>{formatNum(r.prev1m)}</div>
          <div>{formatPct(r.pct1m)}</div>
        </div>
      ))}
    </div>
  );
}
