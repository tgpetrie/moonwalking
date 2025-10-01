import React, { createContext, useContext, useEffect, useState, useRef, useCallback, useMemo } from 'react';
import PropTypes from 'prop-types';
// Use SSE instead of WebSocket for free tier compatibility
import sseManager, { connectSSE, disconnectSSE, subscribeToSSE } from '../services/sse.js';
import { API_ENDPOINTS, fetchData } from '../api.js';
import { isMobileDevice, getMobileOptimizedConfig } from '../utils/mobileDetection.js';
import { computeTop20Gainers } from '../utils/gainersProcessing.js';
import { reconcileRows } from '../utils/rowsStable.js';
import { scheduleIdle, cancelIdle } from '../utils/idle.js';
import { flags } from '../config.js';

// Aliases for compatibility
const wsManager = sseManager;
const connectWebSocket = connectSSE;
const disconnectWebSocket = disconnectSSE;
const subscribeToWebSocket = subscribeToSSE;

const WebSocketContext = createContext(null);

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};

export const WebSocketProvider = ({ children, pollingScheduler }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [latestData, setLatestData] = useState({
    crypto: null,
    prices: {},
    watchlist: null,
    topBanner: null,
    bottomBanner: null
  });
  const [isPolling, setIsPolling] = useState(false);
  const [networkStatus, setNetworkStatus] = useState('good'); // retained for potential UI, referenced to avoid unused warning
  // Hold an object { id: timeoutId, abort: fn }
  const pollingIntervalRef = useRef(null);
  
  // Mobile-specific configuration
  const isMobile = isMobileDevice();
  const mobileConfig = getMobileOptimizedConfig();

  // Debug flag & helper logger (verbose logs suppressed unless enabled)
  const debugEnabled = useMemo(() => flags.VITE_DEBUG_LOGS === true, []);
  const vLog = useCallback((...args) => {
    if (debugEnabled) {
      console.log(...args);
    }
  }, [debugEnabled]);

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

  // Small helpers to normalize REST payload shapes and map to UI items
  const extractRows = useCallback((resp) => {
    if (!resp) return null;
    if (Array.isArray(resp)) return resp;
    if (Array.isArray(resp.rows)) return resp.rows;
    if (Array.isArray(resp.data)) return resp.data;
    return null;
  }, []);
  const mapOneMin = useCallback((rows) => rows.map((item, idx) => ({
    rank: item.rank || (idx + 1),
    symbol: (item.symbol || 'N/A').replace('-USD', ''),
    price: (item.current_price ?? item.price ?? 0),
    change: (item.price_change_percentage_1min ?? item.change ?? 0),
    initial_price_1min: item.initial_price_1min ?? null,
    peakCount: typeof item.peak_count === 'number' ? item.peak_count : 0,
  })), []);
  const mapThreeMin = useCallback((rows) => rows.map((item, idx) => ({
    rank: item.rank || (idx + 1),
    symbol: (item.symbol || 'N/A').replace('-USD', ''),
    price: (item.current_price ?? item.price ?? 0),
    // Provide both a dedicated 3-minute field and a generic `change` alias so UI consumers
    // that expect either name will receive numeric values immediately.
    change3m: Number(item.price_change_percentage_3min ?? item.change ?? item.change3m ?? item.gain ?? 0),
    change: Number(item.price_change_percentage_3min ?? item.change ?? item.change3m ?? item.gain ?? 0),
    initial_price_3min: item.initial_price_3min ?? null,
    peakCount: typeof item.peak_count === 'number' ? item.peak_count : 0,
  })), []);

  const computeUpdates = useCallback((gainersData, gainers3mData, losers3mData, topBannerData, bottomBannerData) => {
    let hasUpdate = false;
    const updates = {};

    const gRows = extractRows(gainersData);
    if (Array.isArray(gRows) && gRows.length) {
      updates.crypto = mapOneMin(gRows);
      hasUpdate = true;
    }

    const g3Rows = extractRows(gainers3mData);
    if (Array.isArray(g3Rows) && g3Rows.length) {
      updates.gainers3m = mapThreeMin(g3Rows);
      hasUpdate = true;
    }

    const l3Rows = extractRows(losers3mData);
    if (Array.isArray(l3Rows) && l3Rows.length) {
      updates.losers3m = mapThreeMin(l3Rows);
      hasUpdate = true;
    }

    const tbRows = extractRows(topBannerData);
    if (Array.isArray(tbRows) && tbRows.length) {
      updates.topBanner = tbRows;
      hasUpdate = true;
    }

    const bbRows = extractRows(bottomBannerData);
    if (Array.isArray(bbRows) && bbRows.length) {
      updates.bottomBanner = bbRows;
      hasUpdate = true;
    }

    return { updates, hasUpdate };
  }, [extractRows, mapOneMin, mapThreeMin]);

  // Polling fallback function using useCallback to avoid stale closures
  // Use injected scheduler or default to setTimeout
  const schedule = useMemo(() => pollingScheduler || ((fn, ms) => setTimeout(fn, ms)), [pollingScheduler]);

  const startPolling = useCallback(() => {
    if (isPolling) {
      vLog('🔄 Polling already active, skipping');
      return;
    }
    vLog('🔄 Starting REST API polling fallback');
    setIsPolling(true);

    let inFlight = false;
    // Use mobile-optimized polling interval
    // Align to requested cadence: update roughly every 15 seconds
    let backoffMs = 15000;
    let controller = null;

    const poll = async () => {
      if (inFlight) {
        return; // concurrency guard
      }
      inFlight = true;
      controller = new AbortController();
      try {
        const fetchOptions = {
          signal: controller.signal,
          timeout: isMobile ? mobileConfig.fetchTimeout : 5000
        };
        vLog('[WebSocket Context] Polling - fetching data...');
        const [gainersData, gainers3mData, losers3mData, topBannerData, bottomBannerData] = await Promise.all([
          fetchData(API_ENDPOINTS.gainersTable1Min, fetchOptions).catch(()=>null),
          fetchData(API_ENDPOINTS.gainersTable3Min, fetchOptions).catch(()=>null),
          fetchData(API_ENDPOINTS.losersTable3Min, fetchOptions).catch(()=>null),
          fetchData(API_ENDPOINTS.topBanner, fetchOptions).catch(()=>null),
          fetchData(API_ENDPOINTS.bottomBanner, fetchOptions).catch(()=>null)
        ]);

  const { updates, hasUpdate } = computeUpdates(gainersData, gainers3mData, losers3mData, topBannerData, bottomBannerData);

        if (hasUpdate) {
          vLog('[WebSocket Context] Polling - updating state with fetched data', updates);
          setLatestData(prev => ({
            ...prev,
            crypto: updates.crypto || prev.crypto,
            gainers3m: updates.gainers3m || prev.gainers3m,
            losers3m: updates.losers3m || prev.losers3m,
            topBanner: updates.topBanner || prev.topBanner,
            bottomBanner: updates.bottomBanner || prev.bottomBanner,
          }));
          // reset backoff on success
          backoffMs = isMobile ? mobileConfig.pollingInterval : 10000;
        } else {
          vLog('[WebSocket Context] Polling - no data received or malformed response');
          // Increase backoff if all fetches fail
          backoffMs = Math.min(backoffMs * 1.5, 90000);
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
      const timeoutId = schedule(async () => {
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
  }, [isPolling, debugEnabled, isMobile, mobileConfig.fetchTimeout, mobileConfig.pollingInterval, vLog, computeUpdates, schedule]);
  
  const stopPolling = useCallback(() => {
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
  }, [vLog]);

  // Manual, immediate refresh (pull latest via REST once, regardless of WS state)
  const refreshNow = useCallback(async () => {
    // 1) Nudge the WebSocket to push a fresh snapshot if connected
    try {
      if (wsManager && wsManager.isConnected) {
        wsManager.send('snapshot_request', { reason: 'manual_refresh', at: Date.now() });
      }
    } catch (err) {
      if (debugEnabled) {
        console.warn('Snapshot request send failed (ignored)', err);
      }
    }

    // 2) Also fetch the REST fallbacks and merge so UI updates even if WS can't respond
    let controller;
    try {
      controller = new AbortController();
      const fetchOptions = { signal: controller.signal };
      const [one, threeG, threeL, topBan, bottomBan] = await Promise.all([
        fetchData(API_ENDPOINTS.gainersTable1Min, fetchOptions).catch(() => null),
        fetchData(API_ENDPOINTS.gainersTable3Min, fetchOptions).catch(() => null),
        fetchData(API_ENDPOINTS.losersTable3Min, fetchOptions).catch(() => null),
        fetchData(API_ENDPOINTS.topBanner, fetchOptions).catch(() => null),
        fetchData(API_ENDPOINTS.bottomBanner, fetchOptions).catch(() => null)
      ]);

      const { updates, hasUpdate } = computeUpdates(one, threeG, threeL, topBan, bottomBan);

      if (hasUpdate) {
        setLatestData(prev => ({
          ...prev,
          crypto: updates.crypto || prev.crypto,
          gainers3m: updates.gainers3m || prev.gainers3m,
          losers3m: updates.losers3m || prev.losers3m,
          topBanner: updates.topBanner || prev.topBanner,
          bottomBanner: updates.bottomBanner || prev.bottomBanner,
        }));
        return true;
      }
    } catch (e) {
      console.error('Manual refresh failed', e);
    } finally {
      try {
        if (controller) controller.abort();
      } catch (err) {
        if (debugEnabled) {
          console.warn('Manual refresh abort cleanup failed (ignored)', err);
        }
      }
    }
    return false;
  }, [debugEnabled, computeUpdates]);

  // Fetch real-time prices for specific symbols from cached data
  const fetchPricesForSymbols = useCallback(async (symbols) => {
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
  }, [latestData]);

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
      vLog('📈 Received crypto update via WebSocket:', data.payload);
      if (data && data.payload) {
        setLatestData(prev => ({
          ...prev,
          crypto: data.payload.gainers1m || prev.crypto,
          gainers3m: data.payload.gainers3m || prev.gainers3m,
          losers3m: data.payload.losers3m || prev.losers3m,
          topBanner: data.payload.topBanner || prev.topBanner,
          bottomBanner: data.payload.bottomBanner || prev.bottomBanner,
        }));
      }
    });

    const unsubscribePrices = subscribeToWebSocket('price_update', (data) => {
      setLatestData(prev => ({ 
        ...prev, 
        prices: { ...prev.prices, ...data } 
      }));
    });

    const unsubscribeWatchlist = subscribeToWebSocket('watchlist_update', (data) => {
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

  // Treat VITE_DISABLE_WS as an opt-in override; default to false so WS is enabled in dev.
  // Some tests (and potentially non-Vite host environments) may shim a window.importMeta.env.
  const disableWs = flags.VITE_DISABLE_WS === true;
    if (disableWs) {
      // Skip WS entirely and use polling
      setIsConnected(true);
      setConnectionStatus('connected');
      startPolling();
      // Immediate one-off fetch so initial paint has data before first polling interval
      (async () => {
        try {
          if (!latestData.crypto || !latestData.crypto?.length) {
            const [oneMin, threeMin, losers3, topBan, bottomBan] = await Promise.all([
              fetchData(API_ENDPOINTS.gainersTable1Min).catch(()=>null),
              fetchData(API_ENDPOINTS.gainersTable3Min).catch(()=>null),
              fetchData(API_ENDPOINTS.losersTable3Min).catch(()=>null),
              fetchData(API_ENDPOINTS.topBanner).catch(()=>null),
              fetchData(API_ENDPOINTS.bottomBanner).catch(()=>null)
            ]);
      const dRows = extractRows(oneMin);
      const g3Rows = extractRows(threeMin);
      const l3Rows = extractRows(losers3);
      const tbRows = extractRows(topBan);
      const bbRows = extractRows(bottomBan);
            if (Array.isArray(dRows) && dRows.length) {
              setLatestData(prev => ({
                ...prev,
        crypto: mapOneMin(dRows),
        gainers3m: Array.isArray(g3Rows) && g3Rows.length ? mapThreeMin(g3Rows) : prev.gainers3m || null,
        losers3m: Array.isArray(l3Rows) && l3Rows.length ? mapThreeMin(l3Rows) : prev.losers3m || null,
        topBanner: Array.isArray(tbRows) && tbRows.length ? tbRows : prev.topBanner || null,
        bottomBanner: Array.isArray(bbRows) && bbRows.length ? bbRows : prev.bottomBanner || null
              }));
              vLog('[WebSocket Context] Immediate REST primed crypto + 3m + banners (WS disabled)');
            }
          }
        } catch (e) {
          if (debugEnabled) {
            console.warn('Immediate REST seed failed', e);
          }
        }
      })();
    } else {
      // Attempt to connect WebSocket (fallback to REST polling if fails)
      connectWebSocket();
      // Start polling if WS doesn't connect quickly
      const initialPollTimer = schedule(() => {
        if (!isConnected) {
          startPolling();
        }
      }, 3000);
      // Also attempt an immediate REST seed to reduce initial latency for 3min lists
      // (run once, non-blocking). This helps when WS doesn't yet provide t3m snapshots.
      (async () => {
        try {
          if ((!latestData.gainers3m || latestData.gainers3m.length === 0) && !isPolling) {
            vLog('[WebSocket Context] Performing immediate REST seed for 3min lists');
            await refreshNow();
          }
        } catch (e) {
          if (debugEnabled) console.warn('Immediate REST seed failed (ignored)', e);
        }
      })();
      // track timer handle via ref so cleanup can clear it
      pollingIntervalRef.current = pollingIntervalRef.current || {};
      pollingIntervalRef.current._initialTimer = initialPollTimer;
    }

    // Development convenience: inject small mock dataset so UI renders while backend is offline.
    // DISABLED: Real data is now available from API
    // try {
    //   if (import.meta?.env?.MODE === 'development') {
    //     // Only inject when we have no live crypto data yet
    //     setLatestData(prev => {
    //       if (Array.isArray(prev.crypto) && prev.crypto.length > 0) return prev;
    //       return { ...prev, crypto: DEV_MOCK_CRYPTO };
    //     });
    //     vLog('[WebSocket Context] Development mock crypto data injected');
    //   }
    // } catch (e) {
    //   // Ignore in constrained environments intentionally
    //   // eslint-disable-next-line no-unused-vars
    //   const _ignored = e;
    // }

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
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Derive top 20 gainers whenever crypto list changes
  useEffect(() => {
    if (!Array.isArray(latestData.crypto) || !latestData.crypto.length) return;
    const { combined, nextPrev } = computeTop20Gainers(latestData.crypto, prevGainersRef.current, { limit: 20, mergePrev: true });
    prevGainersRef.current = nextPrev;
    const reconciled = reconcileRows(combined, prevRenderedGainersRef.current);
    prevRenderedGainersRef.current = reconciled;
    setGainersTop20(reconciled);
  }, [latestData.crypto]);

  // Derive 3m movers whenever their source data changes
  useEffect(() => {
    if (latestData.gainers3m) {
      const recGainers3 = reconcileRows(latestData.gainers3m, prevGainers3mRef.current);
      prevGainers3mRef.current = recGainers3;
      setGainers3mTop(recGainers3);
    }
    if (latestData.losers3m) {
      const recLosers3 = reconcileRows(latestData.losers3m, prevLosers3mRef.current);
      prevLosers3mRef.current = recLosers3;
      setLosers3mTop(recLosers3);
    }
  }, [latestData.gainers3m, latestData.losers3m]);

  // Self-healing fetch: if 3m lists are empty (WS may omit), poll gently until filled
  useEffect(() => {
    let cancelled = false;
    let timer = null;
    const ensureThreeMin = async () => {
      try {
        const haveG = Array.isArray(gainers3mTop) && gainers3mTop.length > 0;
        const haveL = Array.isArray(losers3mTop) && losers3mTop.length > 0;
        if (haveG && haveL) return; // both ready, stop
        const [g3, l3] = await Promise.all([
          fetchData(API_ENDPOINTS.gainersTable3Min).catch(() => null),
          fetchData(API_ENDPOINTS.losersTable3Min).catch(() => null),
        ]);
        const { updates, hasUpdate } = computeUpdates(null, g3, l3);
        if (hasUpdate && !cancelled) {
          setLatestData(prev => ({
            ...prev,
            gainers3m: updates.gainers3m || prev.gainers3m,
            losers3m: updates.losers3m || prev.losers3m,
          }));
        }
      } catch (_e) {
        if (debugEnabled) {
          console.warn('[WebSocket Context] ensureThreeMin fetch error (ignored for retry)', _e);
        }
      } finally {
        if (!cancelled) {
          // Try again in ~12s until both lists are hydrated
          timer = setTimeout(ensureThreeMin, 12000);
        }
      }
    };
    ensureThreeMin();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gainers3mTop.length, losers3mTop.length]);

  useEffect(() => {
    // Idle housekeeping example (no-op placeholder for now)
    if (idleTrimRef.current) {
      cancelIdle(idleTrimRef.current);
    }
    idleTrimRef.current = scheduleIdle(() => {
      // Could trim historical arrays or perform light GC tasks
    }, { timeout: 800 });
  }, [latestData.crypto, latestData.gainers3m, latestData.losers3m]);

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
  oneMinThrottleMs: flags.VITE_ONE_MIN_WS_THROTTLE_MS || 15000,
    subscribe: subscribeToWebSocket,
    getStatus: () => wsManager.getStatus(),
    send: (event, data) => wsManager.send(event, data),
    fetchPricesForSymbols,
    startPolling,
    stopPolling,
    refreshNow
  }), [isConnected, connectionStatus, latestData, isPolling, gainersTop20, debugEnabled, gainers3mTop, losers3mTop, networkStatus, fetchPricesForSymbols, startPolling, stopPolling, refreshNow, vLog]);

    return (
      <WebSocketContext.Provider value={contextValue}>
        {children}
      </WebSocketContext.Provider>
    );
};

export default WebSocketContext;

WebSocketProvider.propTypes = {
  children: PropTypes.node,
  pollingScheduler: PropTypes.func
};
