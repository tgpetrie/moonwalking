import React, { useEffect, useRef } from 'react';

const TradingViewChart = ({ symbol, theme = 'dark', autosize = true }) => {
  const containerRef = useRef(null);

  useEffect(() => {
    // Prevent duplicate script injection
    if (containerRef.current && containerRef.current.querySelector('script')) return;

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      autosize,
      symbol: `BINANCE:${symbol}USDT`, // Defaulting to Binance USDT pairs
      interval: '60',
      timezone: 'Etc/UTC',
      theme,
      style: '1',
      locale: 'en',
      enable_publishing: false,
      hide_top_toolbar: false,
      hide_legend: false,
      save_image: false,
      calendar: false,
      hide_volume: false,
      support_host: 'https://www.tradingview.com'
    });

    if (containerRef.current) {
      containerRef.current.appendChild(script);
    }
  }, [symbol, theme, autosize]);

  return (
    <div className="tradingview-widget-container" ref={containerRef} style={{ height: '100%', width: '100%' }}>
      <div className="tradingview-widget-container__widget" style={{ height: '100%', width: '100%' }} />
    </div>
  );
};

export default TradingViewChart;
