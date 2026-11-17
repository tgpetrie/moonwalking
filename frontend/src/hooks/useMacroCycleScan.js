import { useEffect, useState } from "react";
import { fetchMacroCycleScan, normalizeScanSymbols } from "../api.js";

/**
 * The industry cycle scan from /api/macro-cycle-scan, kept fresh.
 *
 * The server answers `status: "warming"` (no industry read) right after a
 * restart and `status: "refreshing"` while it recomputes, so those are polled
 * sooner. A failed request keeps the last good scan on screen.
 */

export const SCAN_REFRESH_MS = 10 * 60_000; // the server reuses a scan for 30 minutes
export const SCAN_PENDING_MS = 12_000; // warming or refreshing: ask again soon
export const SCAN_RETRY_MS = 60_000;

export function useMacroCycleScan(symbols, { enabled = true } = {}) {
  const key = normalizeScanSymbols(symbols).join(",");
  const [state, setState] = useState({ scan: null, loading: enabled, error: null, status: "warming", key });

  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    let timer = null;

    const load = async () => {
      let delay = SCAN_REFRESH_MS;
      try {
        const scan = await fetchMacroCycleScan(key ? key.split(",") : []);
        if (cancelled) return;
        if (scan.status !== "ready" || scan.atlas_refreshing) delay = SCAN_PENDING_MS;
        // A warming answer carries no read; keep a scan we already have.
        setState((prev) => ({
          scan: scan.status === "warming" && prev.scan?.status !== "warming" && prev.scan ? prev.scan : scan,
          loading: false,
          error: null,
          status: scan.status,
          key,
        }));
      } catch (error) {
        if (cancelled || error?.name === "AbortError") return;
        delay = SCAN_RETRY_MS;
        setState((prev) => ({ ...prev, loading: false, error: "unavailable", status: "unavailable", key }));
      }
      if (!cancelled) timer = setTimeout(load, delay);
    };

    load();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [key, enabled]);

  return state.key === key ? state : { ...state, loading: enabled, status: "warming" };
}

export default useMacroCycleScan;
