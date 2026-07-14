import { createContext, useContext, useEffect, useMemo, useRef, useState, useCallback } from "react";

const IntelligenceContext = createContext(null);

// Use relative paths - Vite proxy handles routing to backend
const API_BASE =
    import.meta.env.VITE_API_BASE_URL || "";
const apiBase = API_BASE.replace(/\/$/, "");
const POLL_MS = Number(import.meta.env.VITE_INTEL_POLL_MS || 300000); // 5 minutes default
const MIN_FETCH_MS = Number(import.meta.env.VITE_INTEL_MIN_FETCH_MS || 60000); // minimum 1 minute between fetches

const normalizeCoinIntelAsReport = (symbol, payload) => {
    const eventsCount = Array.isArray(payload?.events?.items) ? payload.events.items.length : 0;
    const socialCount = Array.isArray(payload?.social?.items) ? payload.social.items.length : 0;
    const signalStrength = Math.min(1, (eventsCount + socialCount) / 10);
    return {
        symbol: String(symbol || "").toUpperCase(),
        metrics: {
            finbert_score: signalStrength,
            finbert_label: "Tape",
            fear_greed_index: null,
            social_volume: socialCount,
            confidence: signalStrength,
            divergence: null,
        },
        narrative: `Coin intel: ${eventsCount} events, ${socialCount} social items.`,
        freshness: String(payload?.status || "offline"),
        generated_at: new Date().toISOString(),
        ttl_seconds: POLL_MS / 1000,
        coin_intel: payload || null,
    };
};

export function useIntelligence() {
    const ctx = useContext(IntelligenceContext);
    if (!ctx) throw new Error("useIntelligence must be used within IntelligenceProvider");
    return ctx;
}

function uniqSymbols(symbols) {
    return Array.from(new Set((symbols || []).map(s => String(s).toUpperCase().trim()).filter(Boolean)));
}

export function IntelligenceProvider({ children, watchSymbols }) {
    const symbolsKey = useMemo(() => uniqSymbols(watchSymbols).join(","), [watchSymbols]);
    const symbols = useMemo(() => (symbolsKey ? symbolsKey.split(",") : []), [symbolsKey]);

    const [reports, setReports] = useState({});
    const [loading, setLoading] = useState(false);
    const [lastError, setLastError] = useState(null);

    const abortRef = useRef(null);
    const timerRef = useRef(null);
    const visibleRef = useRef(true);
    const lastFetchRef = useRef(0);
    const failCountRef = useRef(0);
    const lastFetchOkRef = useRef(true);
    const pollStartedRef = useRef(false);

    const fetchBatch = useCallback(async () => {
        if (!symbols.length) return true;

        // Pause polling when tab is hidden (N100 optimization)
        if (!visibleRef.current) return true;

        // Prevent rapid repeated fetches (safeguard against duplicate mounts)
        const now = Date.now();
        if (now - lastFetchRef.current < MIN_FETCH_MS) return true;
        lastFetchRef.current = now;

        // Abort any in-flight request
        if (abortRef.current) abortRef.current.abort();
        const ac = new AbortController();
        abortRef.current = ac;

        setLoading(true);
        setLastError(null);

        try {
            const pairs = await Promise.all(
                symbols.map(async (sym) => {
                    const res = await fetch(`${apiBase}/api/coin-intel?symbol=${encodeURIComponent(sym)}`, {
                        cache: "no-store",
                        signal: ac.signal,
                    });
                    if (!res.ok) return [sym, null];

                    const contentType = res.headers.get("content-type") || "";
                    if (!contentType.includes("application/json")) {
                        console.warn(`[Intelligence] Non-JSON response from /api/coin-intel (${sym}):`, contentType);
                        return [sym, null];
                    }

                    const payload = await res.json();
                    return [sym, normalizeCoinIntelAsReport(sym, payload)];
                }),
            );
            const merged = Object.fromEntries(pairs.filter(([, val]) => val));

            setReports(prev => ({ ...prev, ...(merged || {}) }));
            failCountRef.current = 0;
            setLastError(null);
            if (!lastFetchOkRef.current) {
                console.info("[Intelligence] Batch fetch recovered");
                lastFetchOkRef.current = true;
            }
            return true;
        } catch (e) {
            if (e.name !== "AbortError") {
                setLastError(String(e.message || e));
                failCountRef.current += 1;
                if (lastFetchOkRef.current) {
                    console.error("[Intelligence] Batch fetch failed:", e);
                    lastFetchOkRef.current = false;
                }
            }
            return false;
        } finally {
            setLoading(false);
        }
    }, [symbols]);

    // Track tab visibility
    useEffect(() => {
        const onVis = () => {
            const wasHidden = !visibleRef.current;
            visibleRef.current = !document.hidden;

            // When tab becomes visible again, trigger immediate refresh
            if (wasHidden && visibleRef.current) {
                fetchBatch();
            }
        };
        document.addEventListener("visibilitychange", onVis);
        onVis();
        return () => document.removeEventListener("visibilitychange", onVis);
    }, [fetchBatch]);

    // Polling loop
    useEffect(() => {
        if (timerRef.current) clearTimeout(timerRef.current);

        // Initial fetch
        if (pollStartedRef.current) return undefined;
        pollStartedRef.current = true;
        fetchBatch();

        const scheduleNext = (delayMs) => {
            timerRef.current = setTimeout(async () => {
                const ok = await fetchBatch();
                const backoff = Math.min(10_000, 2000 * Math.pow(2, Math.max(0, failCountRef.current - 1)));
                scheduleNext(ok ? POLL_MS : backoff);
            }, delayMs);
        };

        // Conservative polling (5 minutes default for N100)
        scheduleNext(POLL_MS);

        return () => {
            pollStartedRef.current = false;
            if (timerRef.current) clearTimeout(timerRef.current);
            if (abortRef.current) abortRef.current.abort();
        };
    }, [fetchBatch]);

    const value = useMemo(() => ({
        reports,
        loading,
        lastError,
        refresh: fetchBatch
    }), [reports, loading, lastError, fetchBatch]);

    return <IntelligenceContext.Provider value={value}>{children}</IntelligenceContext.Provider>;
}
