import { createContext, useContext, useEffect, useMemo, useRef, useState, useCallback } from "react";

const IntelligenceContext = createContext(null);

// Use relative paths - Vite proxy handles routing to backend
const API_BASE =
    import.meta.env.VITE_API_BASE_URL || "";
const apiBase = API_BASE.replace(/\/$/, "");
const POLL_MS = Number(import.meta.env.VITE_INTEL_POLL_MS || 300000); // 5 minutes default
const MIN_FETCH_MS = Number(import.meta.env.VITE_INTEL_MIN_FETCH_MS || 60000); // minimum 1 minute between fetches
const USE_MOCK = String(import.meta.env.VITE_USE_MOCK || "false") === "true";

export function useIntelligence() {
    const ctx = useContext(IntelligenceContext);
    if (!ctx) throw new Error("useIntelligence must be used within IntelligenceProvider");
    return ctx;
}

function uniqSymbols(symbols) {
    return Array.from(new Set((symbols || []).map(s => String(s).toUpperCase().trim()).filter(Boolean)));
}

export function IntelligenceProvider({ children, watchSymbols }) {
    const symbols = useMemo(() => uniqSymbols(watchSymbols), [watchSymbols]);

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

        if (USE_MOCK) {
            // Mock mode for UI testing
            const mock = {};
            for (const sym of symbols) {
                mock[sym] = {
                    symbol: sym,
                    price: 0,
                    metrics: {
                        finbert_score: 0.9,
                        finbert_label: "Bullish",
                        fear_greed_index: 20,
                        social_volume: 450,
                        confidence: 0.92,
                        divergence: "bullish_divergence"
                    },
                    narrative: "Mock divergence: institutional tone bullish into retail fear.",
                    freshness: "fresh",
                    generated_at: new Date().toISOString(),
                    ttl_seconds: 300,
                    model: { name: "mock", device: "cpu", quantized: false }
                };
            }
            setReports(prev => ({ ...prev, ...mock }));
            setLoading(false);
            failCountRef.current = 0;
            if (!lastFetchOkRef.current) {
                console.info("[Intelligence] Batch fetch recovered");
                lastFetchOkRef.current = true;
            }
            return true;
        }

        try {
            const qs = encodeURIComponent(symbols.join(","));
            const res = await fetch(
                `${apiBase}/api/intelligence-reports?symbols=${qs}`,
                { cache: "no-store", signal: ac.signal }
            );

            if (!res.ok) throw new Error(`HTTP ${res.status}`);

            const json = await res.json();
            if (!json.success) {
                throw new Error(json?.error?.message || "Unknown backend error");
            }

            setReports(prev => ({ ...prev, ...json.data }));
            failCountRef.current = 0;
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
        if (timerRef.current) clearInterval(timerRef.current);

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
