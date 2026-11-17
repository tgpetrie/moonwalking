import { useEffect, useState } from "react";
import { fetchPortfolio } from "../../mvp/portfolioApi.js";

/**
 * Real portfolio holdings as a relevance signal for the For You stream.
 *
 * Reuses the existing portfolio client (same endpoint, same session auth) —
 * no new endpoint, no duplicated fetch logic. There is deliberately no error
 * state: holdings are an *additional* personalization source, and any failure
 * (signed out, Coinbase unavailable, empty portfolio) simply yields an empty
 * set so watchlist/rule relevance carries on. Raw errors never reach the UI.
 *
 * A module-level cache keeps repeated panel opens from refetching; the
 * backend snapshot itself is cached server-side, so one call per minute per
 * session is the ceiling.
 */

const TTL_MS = 60_000;

let _cache = { ts: 0, symbols: null, promise: null };
const EMPTY_SYMBOLS = new Set();

/** Pure: extract non-cash holding symbols from a portfolio snapshot. */
export function extractHoldingSymbols(snapshot) {
  const out = new Set();
  for (const row of snapshot?.holdings || []) {
    if (!row || row.is_cash) continue;
    const symbol = String(row.symbol || row.currency || "").toUpperCase().trim();
    if (symbol) out.add(symbol);
  }
  return out;
}

export function __resetHoldingsCacheForTests() {
  _cache = { ts: 0, symbols: null, promise: null };
}

export default function useHoldingSymbols({ enabled = true, cached = true } = {}) {
  const [symbols, setSymbols] = useState(() => cached ? _cache.symbols || EMPTY_SYMBOLS : EMPTY_SYMBOLS);

  useEffect(() => {
    if (!enabled) return undefined;
    let active = true;

    if (!cached) {
      // The public board must confirm the current session before showing holdings.
      let request = 0;
      const load = () => {
        const id = ++request;
        setSymbols(EMPTY_SYMBOLS);
        fetchPortfolio().then(extractHoldingSymbols).then((result) => {
          if (active && id === request) setSymbols(result);
        }).catch(() => {
          if (active && id === request) setSymbols(EMPTY_SYMBOLS);
        });
      };
      load();
      window.addEventListener("focus", load);
      return () => {
        active = false;
        window.removeEventListener("focus", load);
      };
    }

    if (_cache.symbols && Date.now() - _cache.ts < TTL_MS) {
      setSymbols(_cache.symbols);
      return undefined;
    }

    if (!_cache.promise) {
      _cache.promise = fetchPortfolio()
        .then((snapshot) => {
          const extracted = extractHoldingSymbols(snapshot);
          _cache = { ts: Date.now(), symbols: extracted, promise: null };
          return extracted;
        })
        .catch(() => {
          // Signed out, no Coinbase connection, or upstream failure: holdings
          // are simply unknown. Clear the in-flight marker so a later mount
          // can retry, and let the caller keep its other relevance signals.
          _cache.promise = null;
          return null;
        });
    }

    _cache.promise.then((result) => {
      if (active && result) setSymbols(result);
    });

    return () => {
      active = false;
    };
  }, [enabled, cached]);

  return enabled ? symbols : EMPTY_SYMBOLS;
}
