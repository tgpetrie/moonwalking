import React, { useEffect, useMemo, useRef } from "react";
import { mapToTradingViewSymbol } from "./tradingViewSymbols.js";

/**
 * TradingView Advanced Chart embed. Lives inside an iframe so failures are contained.
 */
export default function TradingViewChart({ symbol, height = 320, theme = "dark", interval = "60" }) {
  const containerRef = useRef(null);
  const tvSymbol = mapToTradingViewSymbol(symbol);
  const widgetId = useMemo(
    () => `tv_${tvSymbol.replace(/[^a-zA-Z0-9_]/g, "_")}_${Math.random().toString(36).slice(2, 7)}`,
    [tvSymbol]
  );

  useEffect(() => {
    if (!containerRef.current) return;
    containerRef.current.id = widgetId;
    containerRef.current.innerHTML = "";

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/tv.js";
    script.async = true;

    script.onload = () => {
      try {
        // eslint-disable-next-line no-undef
        new TradingView.widget({
          autosize: true,
          symbol: tvSymbol,
          interval,
          timezone: "Etc/UTC",
          theme,
          style: "1",
          locale: "en",
          enable_publishing: false,
          allow_symbol_change: false,
          hide_top_toolbar: false,
          hide_legend: false,
          save_image: false,
          container_id: widgetId
        });
      } catch (err) {
        if (import.meta.env.DEV) {
          console.error("TradingView widget failed", err);
        }
      }
    };

    containerRef.current.appendChild(script);
  }, [tvSymbol, theme, interval, widgetId]);

  return (
    <div className="panel-soft" style={{ width: "100%", height }}>
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
    </div>
  );
}
