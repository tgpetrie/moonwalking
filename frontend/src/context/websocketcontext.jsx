import React, { createContext, useContext, useEffect, useState, useRef, useCallback, useMemo } from 'react';
import PropTypes from 'prop-types';
import wsManager, { connectWebSocket, disconnectWebSocket, subscribeToWebSocket } from '../services/websocket.js';
import { API_ENDPOINTS, fetchData } from '../api.js';
import { isMobileDevice, getMobileOptimizedConfig } from '../utils/mobileDetection.js';
import { computeTop20Gainers } from '../utils/gainersProcessing.js';
import { reconcileRows } from '../utils/rowsStable.js';
import { scheduleIdle, cancelIdle } from '../utils/idle.js';

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
  const [networkStatus, setNetworkStatus] = useState('good'); // retained for potential UI, referenced to avoid unused warning
  // Hold an object { id: timeoutId, abort: fn }
  const pollingIntervalRef = useRef(null);
  
  // Mobile-specific configuration
  const isMobile = isMobileDevice();
  const mobileConfig = getMobileOptimizedConfig();

  // Debug flag & helper logger (verbose logs suppressed unless enabled)
  const debugEnabled = useMemo(() => {
    return ['true','1','yes','on'].includes(String(import.meta?.env?.VITE_DEBUG_LOGS || import.meta?.env?.VITE_DEBUG || '').toLowerCase());
  }, []);
  const vLog = (...args) => {
    if (debugEnabled) {
      console.log(...args);
    }
  };

  // Derived top 20 gainers list (updated on crypto updates) with stable identity
  const [gainersTop20, setGainersTop20] = useState([]);
  const prevGainersRef = useRef([]); // previous ranked gainers for merge logic
  const prevRenderedGainersRef = useRef([]); // previous rendered list for reconciliation
  // Derived 3m gainers/losers lists
  const [gainers3mTop, setGainers3mTop] = useState([]);
  const [losers3mTop, setLosers3mTop] = useState([]);
  const prevGainers3mRef = useRef([]);
  const prevLosers3mRef = useRef([]);
  const idleTrimRef = useRef(null);

  // Polling fallback function using useCallback to avoid stale closures
  const startPolling = useCallback(() => {
    if (isPolling) {
      vLog('🔄 Polling already active, skipping');
      return;
    }
    vLog('🔄 Starting REST API polling fallback');
    setIsPolling(true);

    let inFlight = false;
    // Use mobile-optimized polling interval
    let backoffMs = isMobile ? mobileConfig.pollingInterval : 10000;
    let controller = null;

    const poll = async () => {
      if (inFlight) {
        return; // concurrency guard
      }
      inFlight = true;
      controller = new AbortController();
      try {
  vLog('[WebSocket Context] Polling - fetching data from:', API_ENDPOINTS.gainersTable1Min);
        const fetchOptions = { 
          signal: controller.signal,
          timeout: isMobile ? mobileConfig.fetchTimeout : 5000
        };
        const gainersData = await fetchData(API_ENDPOINTS.gainersTable1Min, fetchOptions);
  vLog('[WebSocket Context] Polling - received data:', gainersData);
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
          vLog('[WebSocket Context] Polling - updating state with', gainersData.data.length, 'items');
          setLatestData(prev => ({
            ...prev,
            crypto: gainersData.data,
            prices: { ...prev.prices, ...pricesUpdate }
          }));
          // reset backoff on success
          backoffMs = isMobile ? mobileConfig.pollingInterval : 10000;
        } else {
          vLog('[WebSocket Context] Polling - no data received or malformed response');
        }
      } catch (error) {
        if (error.name === 'AbortError') {
          vLog('[WebSocket Context] Polling - aborted');
        } else {
          console.error('[WebSocket Context] Polling error:', error);
          backoffMs = Math.min(backoffMs * 1.5, 90000); // exponential up to 90s
        }
      } finally {
        inFlight = false;
      }
    };

    // Kick off loop using adaptive timeout instead of fixed setInterval to respect backoff
    const scheduleNext = () => {
      const timeoutId = setTimeout(async () => {
        if (pollingIntervalRef.current) { // Check if still should be polling
          await poll();
          scheduleNext();
        }
      }, backoffMs);
      // Store controller abort alongside timer id in a small control object
      pollingIntervalRef.current = {
        id: timeoutId,
        abort: () => {
          try {
            if (controller) {
              controller.abort();
            }
          } catch (abortErr) {
            if (debugEnabled) {
              console.warn('Polling abort error ignored', abortErr);
            }
          }
        }
      };
    };
    
    // Start immediately and then schedule
    poll().then(() => scheduleNext());
  }, [isPolling]); // Add isPolling as dependency
  
  const stopPolling = () => {
    if (pollingIntervalRef.current) {
      // Clear any scheduled timeout
      const id = typeof pollingIntervalRef.current === 'number'
        ? pollingIntervalRef.current
        : pollingIntervalRef.current.id;
      if (id) {
        clearTimeout(id);
      }
      // Abort any in-flight fetch
      if (pollingIntervalRef.current.abort) {
        pollingIntervalRef.current.abort();
      }
      pollingIntervalRef.current = null;
    }
    setIsPolling(false);
  vLog('⏹️ Stopped REST API polling');
  };

  // Manual, immediate refresh (pull latest via REST once, regardless of WS state)
  const refreshNow = async () => {
    let controller;
    try {
      controller = new AbortController();
      const res = await fetchData(API_ENDPOINTS.gainersTable1Min, { signal: controller.signal });
      if (res && res.data && Array.isArray(res.data)) {
        const pricesUpdate = {};
        res.data.forEach((coin) => {
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
        setLatestData((prev) => ({
          ...prev,
          crypto: res.data,
          prices: { ...prev.prices, ...pricesUpdate }
        }));
        return true;
      }
    } catch (e) {
      console.error('Manual refresh failed', e);
    } finally {
      try {
        if (controller) {
          controller.abort();
        }
      } catch (e) {
        if (debugEnabled) {
          console.warn('Stop polling abort cleanup error', e);
        }
      }
    }
    return false;
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
  vLog('✅ WebSocket connected successfully');
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
      vLog('📈 Received crypto update via WebSocket:', data);
      setLatestData(prev => ({ ...prev, crypto: data }));
    });

    const unsubscribePrices = subscribeToWebSocket('price_update', (data) => {
      vLog('💰 Received price update via WebSocket:', data);
      setLatestData(prev => ({ 
        ...prev, 
        prices: { ...prev.prices, ...data } 
      }));
    });

    const unsubscribeWatchlist = subscribeToWebSocket('watchlist_update', (data) => {
      vLog('⭐ Received watchlist update via WebSocket:', data);
      setLatestData(prev => ({ ...prev, watchlist: data }));
    });

    // Mobile-specific network monitoring
    const unsubscribeNetworkDegraded = subscribeToWebSocket('network_degraded', (data) => {
      vLog('📱 Network degraded, switching to more aggressive polling:', data);
      setNetworkStatus('poor');
      if (!isPolling && !isConnected) {
        startPolling();
      }
    });

    const unsubscribeNetworkImproved = subscribeToWebSocket('network_improved', (data) => {
      vLog('📱 Network improved:', data);
      setNetworkStatus('good');
    });

  const disableWs = String(import.meta?.env?.VITE_DISABLE_WS || 'true').toLowerCase() === 'true';
    if (disableWs) {
      // Skip WS entirely and use polling
      startPolling();
    } else {
      // Attempt to connect WebSocket (fallback to REST polling if fails)
      connectWebSocket();
      // Start polling if WS doesn't connect quickly
      const initialPollTimer = setTimeout(() => {
        if (!isConnected) {
          startPolling();
        }
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
      } catch (e) {
        if (debugEnabled) {
          console.warn('Initial timer cleanup error', e);
        }
      }
      unsubscribeConnection();
      unsubscribeCrypto();
      unsubscribePrices();
      unsubscribeWatchlist();
      unsubscribeNetworkDegraded();
      unsubscribeNetworkImproved();
      disconnectWebSocket();
      stopPolling();
    };
  }, []);

  // Derive top 20 gainers whenever crypto list changes
  useEffect(() => {
    if (!Array.isArray(latestData.crypto) || !latestData.crypto.length) {
      return;
    }
    // 1m gainers
    const { combined, nextPrev } = computeTop20Gainers(latestData.crypto, prevGainersRef.current, { limit: 20, mergePrev: true });
    prevGainersRef.current = nextPrev;
    const reconciled = reconcileRows(combined, prevRenderedGainersRef.current);
    prevRenderedGainersRef.current = reconciled;
    setGainersTop20(reconciled);

    // 3m movers
    const with3m = latestData.crypto.map((c, idx) => ({
      rank: c.rank || idx + 1,
      symbol: c.symbol?.replace('-USD','') || 'N/A',
      price: c.current_price ?? c.price ?? 0,
      change3m: c.price_change_percentage_3min ?? c.change3m ?? c.change ?? 0,
      peakCount: typeof c.peak_count === 'number' ? c.peak_count : 0,
    }));
    const gainers3Raw = with3m
      .filter(r => typeof r.change3m === 'number')
      .sort((a,b)=> (b.change3m||0) - (a.change3m||0))
      .slice(0,20)
      .map((it,i)=> ({ ...it, rank: i+1 }));
    const losers3Raw = with3m
      .filter(r => typeof r.change3m === 'number')
      .sort((a,b)=> (a.change3m||0) - (b.change3m||0))
      .slice(0,20)
      .map((it,i)=> ({ ...it, rank: i+1 }));
    const recGainers3 = reconcileRows(gainers3Raw, prevGainers3mRef.current);
    const recLosers3 = reconcileRows(losers3Raw, prevLosers3mRef.current);
    prevGainers3mRef.current = recGainers3;
    prevLosers3mRef.current = recLosers3;
    setGainers3mTop(recGainers3);
    setLosers3mTop(recLosers3);

    // Idle housekeeping example (no-op placeholder for now)
    if (idleTrimRef.current) {
      cancelIdle(idleTrimRef.current);
    }
    idleTrimRef.current = scheduleIdle(() => {
      // Could trim historical arrays or perform light GC tasks
    }, { timeout: 800 });
  }, [latestData.crypto]);

  const contextValue = useMemo(() => ({
    isConnected,
    connectionStatus,
    latestData,
    wsManager,
    isPolling,
    gainersTop20,
    debugEnabled,
    vLog,
    gainers3mTop,
    losers3mTop,
    networkStatus,
    oneMinThrottleMs: Number(import.meta?.env?.VITE_ONE_MIN_WS_THROTTLE_MS) || 15000,
    subscribe: subscribeToWebSocket,
    getStatus: () => wsManager.getStatus(),
    send: (event, data) => wsManager.send(event, data),
    fetchPricesForSymbols,
    startPolling,
    stopPolling,
    refreshNow
  }), [isConnected, connectionStatus, latestData, wsManager, isPolling, gainersTop20, debugEnabled, gainers3mTop, losers3mTop, networkStatus]);

  return (
    <WebSocketContext.Provider value={contextValue}>
      {children}
    </WebSocketContext.Provider>
  );
};

export default WebSocketContext;

WebSocketProvider.propTypes = {
  children: PropTypes.node
};
