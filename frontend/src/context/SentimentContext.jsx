import React, { createContext, useContext, useMemo } from "react";
import { useDataFeed } from "../hooks/useDataFeed";

const SentimentContext = createContext(null);

export function SentimentProvider({ children }) {
  const { data, error, isLoading } = useDataFeed();

  const sentiment = useMemo(() => {
    const payload = data?.data ?? data ?? {};
    return (
      payload.sentiment ||
      payload.sentiment_overview ||
      payload.sentiment_panel ||
      null
    );
  }, [data]);

  return (
    <SentimentContext.Provider value={{ sentiment, loading: isLoading, error }}>
      {children}
    </SentimentContext.Provider>
  );
}

export function useSentimentContext() {
  const ctx = useContext(SentimentContext);
  if (!ctx) throw new Error("useSentimentContext must be used inside SentimentProvider");
  return ctx;
}
