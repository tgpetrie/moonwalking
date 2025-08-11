import React, { useEffect, useRef } from 'react';

const TradingViewChart = ({ symbol, theme = 'dark', height = 400 }) => {
  const containerRef = useRef(null);
  const widgetRef = useRef(null);

  useEffect(() => {
    // Clean up any existing widget
    if (widgetRef.current) {
      widgetRef.current = null;
    }

    if (containerRef.current) {
      containerRef.current.innerHTML = '';
    }

    // Only create widget if symbol is provided
    if (!symbol) return;

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.type = 'text/javascript';
    script.async = true;

    const config = {
      width: "100%",
      height: height,
      symbol: `COINBASE:${symbol.toUpperCase()}USD`,
      interval: "15",
      timezone: "Etc/UTC",
      theme: theme,
      style: "1",
      locale: "en",
      enable_publishing: false,
      backgroundColor: theme === 'dark' ? "rgba(19, 23, 34, 1)" : "rgba(255, 255, 255, 1)",
      gridColor: theme === 'dark' ? "rgba(42, 46, 57, 1)" : "rgba(233, 233, 234, 1)",
      hide_top_toolbar: false,
      hide_legend: false,
      save_image: false,
      container_id: `tradingview_chart_${symbol}`,
      studies: [
        "RSI@tv-basicstudies",
        "MASimple@tv-basicstudies",
        "MACD@tv-basicstudies"
      ],
      show_popup_button: true,
      popup_width: "1000",
      popup_height: "650",
      withdateranges: true,
      hide_side_toolbar: false,
      allow_symbol_change: false,
      details: true,
      hotlist: true,
      calendar: false,
      support_host: "https://www.tradingview.com"
    };

    script.innerHTML = JSON.stringify(config);

    if (containerRef.current) {
      containerRef.current.appendChild(script);
      widgetRef.current = script;
    }

    return () => {
      if (widgetRef.current && containerRef.current && containerRef.current.contains(widgetRef.current)) {
        containerRef.current.removeChild(widgetRef.current);
      }
    };
  }, [symbol, theme, height]);

  return (
    <div className="tradingview-widget-container w-full">
      <div 
        ref={containerRef}
        id={`tradingview_chart_${symbol}`}
        className="tradingview-widget w-full rounded-lg overflow-hidden"
        style={{ height: `${height}px` }}
      />
      <div className="tradingview-widget-copyright">
        <a 
          href={`https://www.tradingview.com/symbols/COINBASE-${symbol}USD/`} 
          rel="noopener noreferrer" 
          target="_blank"
          className="text-xs text-gray-500 hover:text-gray-400"
        >
          <span>View {symbol} on TradingView</span>
        </a>
      </div>
    </div>
  );
};

// Lightweight chart component for smaller spaces
export const TradingViewMiniChart = ({ symbol, theme = 'dark', height = 200 }) => {
  const containerRef = useRef(null);
  const widgetRef = useRef(null);

  useEffect(() => {
    if (widgetRef.current) {
      widgetRef.current = null;
    }

    if (containerRef.current) {
      containerRef.current.innerHTML = '';
    }

    if (!symbol) return;

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js';
    script.type = 'text/javascript';
    script.async = true;

    const config = {
      symbol: `COINBASE:${symbol.toUpperCase()}USD`,
      width: "100%",
      height: height,
      locale: "en",
      dateRange: "12M",
      colorTheme: theme,
      trendLineColor: "rgba(41, 98, 255, 1)",
      underLineColor: "rgba(41, 98, 255, 0.3)",
      underLineBottomColor: "rgba(41, 98, 255, 0)",
      isTransparent: true,
      autosize: true,
      largeChartUrl: ""
    };

    script.innerHTML = JSON.stringify(config);

    if (containerRef.current) {
      containerRef.current.appendChild(script);
      widgetRef.current = script;
    }

    return () => {
      if (widgetRef.current && containerRef.current && containerRef.current.contains(widgetRef.current)) {
        containerRef.current.removeChild(widgetRef.current);
      }
    };
  }, [symbol, theme, height]);

  return (
    <div className="tradingview-widget-container w-full">
      <div 
        ref={containerRef}
        id={`tradingview_mini_${symbol}`}
        className="tradingview-widget w-full rounded-lg overflow-hidden"
        style={{ height: `${height}px` }}
      />
    </div>
  );
};

export default TradingViewChart;