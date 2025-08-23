import React, { createContext, useContext, useEffect, useState, useRef } from 'react';
import wsManager, { connectWebSocket, disconnectWebSocket, subscribeToWebSocket } from '../services/websocket.js';
import { API_ENDPOINTS, fetchData } from '../api.js';

const WebSocketContext = createContext(null);

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};

export const WebSocketProvider = ({ children }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [latestData, setLatestData] = useState({
    crypto: null,
    prices: {},
    watchlist: null,
    tables: null,
    alerts: null
  });
  const [isPolling, setIsPolling] = useState(false);
  // Hold an object { id: timeoutId, abort: fn }
  const pollingIntervalRef = useRef(null);

  // Polling fallback function
  const startPolling = () => {
    if (isPolling) return;

    console.log('🔄 Starting REST API polling fallback');
    setIsPolling(true);

  let inFlight = false;
  let backoffMs = 10000; // start at 10s to reduce churn
    let controller = null;

  const poll = async () => {
      if (inFlight) return; // concurrency guard
      inFlight = true;
      controller = new AbortController();
      try {
        const gainersData = await fetchData(API_ENDPOINTS.gainersTable1Min, { signal: controller.signal });
        if (gainersData && gainersData.data) {
          const pricesUpdate = {};
            gainersData.data.forEach(coin => {
              if (coin.symbol && (coin.price !== undefined || coin.current_price !== undefined)) {
                const priceVal = coin.price ?? coin.current_price;
                pricesUpdate[coin.symbol] = {
                  price: priceVal,
                  change: coin.price_change_percentage_1min || coin.change || 0,
                  changePercent: coin.price_change_percentage_1min || coin.changePercent || 0,
                  timestamp: Date.now()
                };
              }
            });
          setLatestData(prev => ({
            ...prev,
            crypto: gainersData.data,
            prices: { ...prev.prices, ...pricesUpdate }
          }));
          // reset backoff on success
          backoffMs = 10000;
        }
      } catch (error) {
        if (error.name === 'AbortError') {
          // silent on abort
        } else {
          console.error('Polling error:', error);
          backoffMs = Math.min(backoffMs * 1.5, 90000); // exponential up to 90s
        }
      } finally {
        inFlight = false;
      }
    };

    // Kick off loop using adaptive timeout instead of fixed setInterval to respect backoff
    const scheduleNext = () => {
      const timeoutId = setTimeout(async () => {
        await poll();
        scheduleNext();
      }, backoffMs);
      // Store controller abort alongside timer id in a small control object
      pollingIntervalRef.current = {
        id: timeoutId,
        abort: () => {
          try { if (controller) controller.abort(); } catch (_) {}
        }
      };
    };
    poll();
    scheduleNext();
  };
  
  const stopPolling = () => {
    if (pollingIntervalRef.current) {
      // Clear any scheduled timeout
      const id = typeof pollingIntervalRef.current === 'number'
        ? pollingIntervalRef.current
        : pollingIntervalRef.current.id;
      if (id) clearTimeout(id);
      // Abort any in-flight fetch
      if (pollingIntervalRef.current.abort) pollingIntervalRef.current.abort();
      pollingIntervalRef.current = null;
    }
    setIsPolling(false);
    console.log('⏹️ Stopped REST API polling');
  };

  // Fetch real-time prices for specific symbols from cached data
  const fetchPricesForSymbols = async (symbols) => {
    try {
      // Use already cached data from polling instead of making new API call
      if (latestData.crypto && latestData.crypto.length > 0) {
        const prices = {};
        latestData.crypto.forEach(coin => {
          if (symbols.includes(coin.symbol)) {
            prices[coin.symbol] = {
              price: coin.current_price || coin.price,
              change: coin.price_change_percentage_1min || coin.change || 0,
              changePercent: coin.price_change_percentage_1min || coin.changePercent || 0,
              timestamp: Date.now()
            };
          }
        });
        return prices;
      }
      
      // Fallback: use cached prices data
      const prices = {};
      symbols.forEach(symbol => {
        if (latestData.prices[symbol]) {
          prices[symbol] = latestData.prices[symbol];
        }
      });
      return prices;
    } catch (error) {
      console.error('Error fetching prices for symbols:', error);
    }
    return {};
  };

  useEffect(() => {
    // Subscribe to connection status changes
    const unsubscribeConnection = subscribeToWebSocket('connection', (data) => {
      setIsConnected(data.status === 'connected');
      setConnectionStatus(data.status);
      
      if (data.status === 'connected') {
        console.log('✅ WebSocket connected successfully');
        stopPolling(); // Stop polling if WebSocket connects
      } else if (data.status === 'error') {
        console.warn('⚠️ WebSocket connection error:', data.error);
      } else if (data.status === 'failed') {
        console.error('❌ WebSocket connection failed after', data.attempts, 'attempts');
        startPolling(); // Start polling fallback
      }
    });

    // Subscribe to real-time data updates
    const unsubscribeCrypto = subscribeToWebSocket('crypto_update', (data) => {
      console.log('📈 Received crypto update via WebSocket:', data);
      setLatestData(prev => ({ ...prev, crypto: data }));
    });

    const unsubscribePrices = subscribeToWebSocket('price_update', (data) => {
      console.log('💰 Received price update via WebSocket:', data);
      setLatestData(prev => ({ 
        ...prev, 
        prices: { ...prev.prices, ...data } 
      }));
    });

    const unsubscribeWatchlist = subscribeToWebSocket('watchlist_update', (data) => {
      console.log('⭐ Received watchlist update via WebSocket:', data);
      setLatestData(prev => ({ ...prev, watchlist: data }));
    });

    // Subscribe to new table and alert events
    const unsubscribeTables = subscribeToWebSocket('tables:update', (data) => {
      console.log('📊 Received tables update via WebSocket:', data);
      setLatestData(prev => ({ ...prev, tables: data }));
      
      // Store in sessionStorage for SWR
      if (data.t1m) {
        sessionStorage.setItem('cache:tables:t1m', JSON.stringify({
          data: data.t1m,
          timestamp: Date.now()
        }));
      }
      if (data.t3m) {
        sessionStorage.setItem('cache:tables:t3m', JSON.stringify({
          data: data.t3m,
          timestamp: Date.now()
        }));
      }
    });

    const unsubscribeAlerts = subscribeToWebSocket('alerts:update', (data) => {
      console.log('🚨 Received alerts update via WebSocket:', data);
      setLatestData(prev => ({ ...prev, alerts: data }));
      
      // Store in sessionStorage for centralized alerts
      sessionStorage.setItem('cache:alerts:recent', JSON.stringify({
        data: data,
        timestamp: Date.now()
      }));
    });

  // Default to enabling WebSocket in dev unless explicitly disabled via env
  const disableWs = String(import.meta?.env?.VITE_DISABLE_WS || 'false').toLowerCase() === 'true';
    if (disableWs) {
      // Skip WS entirely and use polling
      startPolling();
    } else {
      // Attempt to connect WebSocket (fallback to REST polling if fails)
      connectWebSocket();
      // Start polling if WS doesn't connect quickly
      const initialPollTimer = setTimeout(() => {
        if (!isConnected) startPolling();
      }, 3000);
      // track timer handle via ref so cleanup can clear it
      pollingIntervalRef.current = pollingIntervalRef.current || {};
      pollingIntervalRef.current._initialTimer = initialPollTimer;
    }

    // Cleanup on unmount
    return () => {
      try {
        if (pollingIntervalRef.current?._initialTimer) {
          clearTimeout(pollingIntervalRef.current._initialTimer);
          delete pollingIntervalRef.current._initialTimer;
        }
      } catch (_) {}
      unsubscribeConnection();
      unsubscribeCrypto();
      unsubscribePrices();
      unsubscribeWatchlist();
      unsubscribeTables();
      unsubscribeAlerts();
      disconnectWebSocket();
      stopPolling();
    };
  }, []);

  // Developer fixture: inject sample table data for visual preview when enabled.
  // Controlled by VITE_DEV_FILL_TABLES=true (useful when backend/ws are not available).
  useEffect(() => {
    const enabled = String(import.meta?.env?.VITE_DEV_FILL_TABLES || '').toLowerCase() === 'true';
    if (!enabled) return;

    // A lightweight, realistic-looking fixture used purely for visual previews.
    const sampleCrypto = [
      { symbol: 'TNSR', current_price: 0.1260, price_change_percentage_1min: 2.44 },
      { symbol: 'SUKU', current_price: 0.0383, price_change_percentage_1min: 2.13 },
      { symbol: 'CVX', current_price: 4.2, price_change_percentage_1min: 1.82 },
      { symbol: 'HIGH', current_price: 0.5650, price_change_percentage_1min: 1.62 },
      { symbol: 'XTZ', current_price: 0.8520, price_change_percentage_1min: 1.07 },
      { symbol: 'MINA', current_price: 0.19, price_change_percentage_1min: 1.06 },
      { symbol: 'RARE', current_price: 0.0554, price_change_percentage_1min: 0.911 },
      // Right-column losers (still included in array so components can pick slices)
      { symbol: 'HOPR', current_price: 0.0611, price_change_percentage_1min: -1.93 },
      { symbol: 'NCT', current_price: 0.0207, price_change_percentage_1min: -1.57 },
      { symbol: 'AVAX', current_price: 23.79, price_change_percentage_1min: -0.335 },
      { symbol: 'ALGO', current_price: 0.2557, price_change_percentage_1min: -0.156 },
      { symbol: 'ATOM', current_price: 4.55, price_change_percentage_1min: -0.154 },
      { symbol: 'INJ', current_price: 15.3, price_change_percentage_1min: -0.111 },
      { symbol: 'SKY', current_price: 0.0775, price_change_percentage_1min: -0.103 }
    ];

    const pricesMap = {};
    sampleCrypto.forEach(c => {
      pricesMap[c.symbol] = {
        price: c.current_price,
        change: (c.price_change_percentage_1min || 0) * (c.current_price / 100),
        changePercent: c.price_change_percentage_1min || 0,
        timestamp: Date.now()
      };
    });

    // Inject fixture and stop polling so fixture is stable
    setLatestData(prev => ({ ...prev, crypto: sampleCrypto, prices: { ...prev.prices, ...pricesMap } }));
    try { stopPolling(); } catch (_) {}
  }, []);

  const contextValue = {
    isConnected,
    connectionStatus,
    latestData,
    wsManager,
    isPolling,
  oneMinThrottleMs: Number(import.meta?.env?.VITE_ONE_MIN_WS_THROTTLE_MS) || 7000,
    // Convenience methods
    subscribe: subscribeToWebSocket,
    getStatus: () => wsManager.getStatus(),
    send: (event, data) => wsManager.send(event, data),
    fetchPricesForSymbols,
    startPolling,
    stopPolling
  };

  return (
    <WebSocketContext.Provider value={contextValue}>
      {children}
    </WebSocketContext.Provider>
  );
};

export default WebSocketContext;