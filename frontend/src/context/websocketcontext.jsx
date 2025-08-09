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
    watchlist: null
  });
  const [isPolling, setIsPolling] = useState(false);
  const pollingIntervalRef = useRef(null);

  // Polling fallback function
  const startPolling = () => {
    if (isPolling) return;

    console.log('🔄 Starting REST API polling fallback');
    setIsPolling(true);

    let inFlight = false;
    let backoffMs = 5000; // start at 5s
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
          backoffMs = 5000;
        }
      } catch (error) {
        if (error.name === 'AbortError') {
          // silent on abort
        } else {
          console.error('Polling error:', error);
          backoffMs = Math.min(backoffMs * 1.5, 60000); // exponential up to 60s
        }
      } finally {
        inFlight = false;
      }
    };

    // Kick off loop using adaptive timeout instead of fixed setInterval to respect backoff
    const scheduleNext = () => {
      pollingIntervalRef.current = setTimeout(async () => {
        await poll();
        scheduleNext();
      }, backoffMs);
    };
    poll();
    scheduleNext();

    // store abort so stopPolling can cancel
    pollingIntervalRef.current.abortController = () => {
      if (controller) controller.abort();
    };
  };
  
  const stopPolling = () => {
    if (pollingIntervalRef.current) {
      if (typeof pollingIntervalRef.current === 'number') {
        clearTimeout(pollingIntervalRef.current);
      } else {
        clearTimeout(pollingIntervalRef.current.id);
      }
      if (pollingIntervalRef.current.abortController) {
        pollingIntervalRef.current.abortController();
      }
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

    // Attempt to connect WebSocket (fallback to REST polling if fails)
    connectWebSocket();
    
    // Start polling immediately as fallback
    const initialPollTimer = setTimeout(() => {
      if (!isConnected) {
        startPolling();
      }
    }, 3000); // Wait 3 seconds before starting polling if no WebSocket connection

    // Cleanup on unmount
    return () => {
      clearTimeout(initialPollTimer);
      unsubscribeConnection();
      unsubscribeCrypto();
      unsubscribePrices();
      unsubscribeWatchlist();
      disconnectWebSocket();
      stopPolling();
    };
  }, []);

  const contextValue = {
    isConnected,
    connectionStatus,
    latestData,
    wsManager,
    isPolling,
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