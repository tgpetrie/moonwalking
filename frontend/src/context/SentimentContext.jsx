import React, { createContext, useContext, useEffect, useState, useCallback } from "react";

const SentimentContext = createContext(null);

export function SentimentProvider({ children, pollMs = 60000 }) {
  const [sentiment, setSentiment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchSentiment = useCallback(async () => {
    try {
      const res = await fetch("/api/sentiment-basic");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setSentiment(json);
      setError(null);
      setLoading(false);
    } catch (err) {
      console.warn("[sentiment] failed:", err);
      setError(err);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSentiment();
    const id = setInterval(fetchSentiment, pollMs);
    return () => clearInterval(id);
  }, [fetchSentiment, pollMs]);

  return (
    <SentimentContext.Provider value={{ sentiment, loading, error, refetch: fetchSentiment }}>
      {children}
    </SentimentContext.Provider>
  );
}

export function useSentiment() {
  const ctx = useContext(SentimentContext);
  if (!ctx) throw new Error("useSentiment must be used inside SentimentProvider");
  return ctx;
}

