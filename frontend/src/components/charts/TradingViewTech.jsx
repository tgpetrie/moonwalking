import React, { useEffect, useMemo, useRef } from "react";
import { mapToTradingViewSymbol } from "./tradingViewSymbols.js";

/**
 * TradingView Technical Analysis widget embed for sentiment insights.
 */
export default function TradingViewTech({ symbol, height = 360, theme = "dark" }) {
  const containerRef = useRef(null);
  const tvSymbol = mapToTradingViewSymbol(symbol);
  const widgetId = useMemo(
    () => `tv_ta_${tvSymbol.replace(/[^a-zA-Z0-9_]/g, "_")}_${Math.random().toString(36).slice(2, 7)}`,
    [tvSymbol]
  );

  useEffect(() => {
    if (!containerRef.current) return;
    containerRef.current.innerHTML = "";

    const script = document.createElement("script");
    script.src =
      "https://s3.tradingview.com/external-embedding/embed-widget-technical-analysis.js";
    script.async = true;
    script.innerHTML = JSON.stringify({
      interval: "1h",
      width: "100%",
      height,
      isTransparent: true,
      symbol: tvSymbol,
      showIntervalTabs: true,
      locale: "en",
      colorTheme: theme
    });

    containerRef.current.appendChild(script);
  }, [tvSymbol, height, theme]);

  return <div id={widgetId} ref={containerRef} style={{ width: "100%", height }} />;
}
