import { createContext, useContext, useEffect, useMemo, useRef, useState, useCallback } from "react";

const IntelligenceContext = createContext(null);

const API_BASE =
    import.meta.env.VITE_API_BASE_URL ||
    "http://127.0.0.1:5003";
const apiBase = API_BASE.replace(/\/$/, "");
const POLL_MS = Number(import.meta.env.VITE_INTEL_POLL_MS || 300000); // 5 minutes default
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

    const fetchBatch = useCallback(async () => {
        if (!symbols.length) return;

        // Pause polling when tab is hidden (N100 optimization)
        if (!visibleRef.current) return;

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
            return;
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
        } catch (e) {
            if (e.name !== "AbortError") {
                setLastError(String(e.message || e));
                console.error("[Intelligence] Batch fetch failed:", e);
            }
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
        fetchBatch();

        // Conservative polling (5 minutes default for N100)
        timerRef.current = setInterval(fetchBatch, POLL_MS);

        return () => {
            if (timerRef.current) clearInterval(timerRef.current);
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
