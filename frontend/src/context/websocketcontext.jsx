import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import PropTypes from 'prop-types';
import { API_ENDPOINTS, fetchData } from '../api.js';
import { flags } from '../config.js';

const WebSocketContext = createContext(null);

const mapRows = (payload) => {
  if (!payload) return [];
  if (Array.isArray(payload?.rows)) return payload.rows;
  if (Array.isArray(payload?.data)) return payload.data;
  if (Array.isArray(payload)) return payload;
  return [];
};

const sanitizeSymbol = (symbol = '') => String(symbol).toUpperCase().replace(/-USD$/i, '');

const buildPriceMap = (rows, timestamp) => {
  const map = {};
  rows.forEach((row) => {
    const base = sanitizeSymbol(row.symbol || row.pair || row.product_id || '');
    const price = Number(row.current_price ?? row.price ?? 0);
    const change = Number(row.change);
    const payload = {
      price,
      change,
      changePercent: change,
      timestamp,
    };
    [
      base,
      `${base}-USD`,
      String(row.symbol || '').toUpperCase(),
      String(row.pair || '').toUpperCase(),
      String(row.product_id || '').toUpperCase(),
    ]
      .filter(Boolean)
      .forEach((key) => {
        map[key] = payload;
      });
  });
  return map;
};

const safeFetch = async (endpoint) => {
  try {
    return await fetchData(endpoint);
  } catch (err) {
    console.error('Polling fetch failed for', endpoint, err);
    return null;
  }
};

export const useWebSocket = () => {
  const ctx = useContext(WebSocketContext);
  if (!ctx) throw new Error('useWebSocket must be used within a WebSocketProvider');
  return ctx;
};

export const WebSocketProvider = ({ children, pollIntervalMs = 12000 }) => {
  const [latestData, setLatestData] = useState({
    crypto: [],
    gainers3m: [],
    losers3m: [],
    topBanner: [],
    bottomBanner: [],
    prices: {},
    updatedAt: 0,
  });
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('offline');
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState(null);
  const networkStatus = 'good';
  const mountedRef = useRef(true);
  const timerRef = useRef(null);
  const fetchingRef = useRef(false);

  const debugEnabled = useMemo(() => flags.VITE_DEBUG_LOGS === true, []);
  const vLog = useCallback((...args) => {
    if (debugEnabled) console.log(...args);
  }, [debugEnabled]);

  const pollOnce = useCallback(async () => {
    if (fetchingRef.current) {
      return true;
    }
    fetchingRef.current = true;
    setIsPolling(true);
    try {
      const [oneMin, threeMin, losersRes, topBannerRes, bottomBannerRes] = await Promise.all([
        safeFetch(API_ENDPOINTS.gainersTable1Min || '/api/component/gainers-table-1min'),
        safeFetch(API_ENDPOINTS.gainersTable3Min || '/api/component/gainers-table-3min'),
        safeFetch(API_ENDPOINTS.losersTable3Min || '/api/component/losers-table-3min'),
        safeFetch(API_ENDPOINTS.topBanner || '/api/component/top-banner-scroll'),
        safeFetch(API_ENDPOINTS.bottomBanner || '/api/component/bottom-banner-scroll'),
      ]);

      const now = Date.now();
      const oneMinRows = mapRows(oneMin).map((item, idx) => {
        const symbol = sanitizeSymbol(item.symbol || item.pair || item.product_id || '');
        const price = Number(item.current_price ?? item.price ?? 0);
        const change = Number(
          item.price_change_percentage_1min ?? item.change ?? item.change1m ?? item.gain ?? 0,
        );
        return {
          ...item,
          rank: item.rank || idx + 1,
          symbol,
          price,
          change,
          current_price: price,
          price_change_percentage_1min: change,
        };
      });

      const threeMinRowsRaw = mapRows(threeMin).map((item, idx) => {
        const symbol = sanitizeSymbol(item.symbol || item.pair || item.product_id || '');
        const change3m = Number(
          item.price_change_percentage_3min ?? item.change ?? item.change3m ?? item.gain ?? 0,
        );
        return {
          ...item,
          rank: item.rank || idx + 1,
          symbol,
          change3m,
          change: change3m,
          price_change_percentage_3min: change3m,
        };
      });

      const losersFromEndpoint = mapRows(losersRes).map((item, idx) => {
        const symbol = sanitizeSymbol(item.symbol || item.pair || item.product_id || '');
        const change3m = Number(
          item.price_change_percentage_3min ?? item.change ?? item.change3m ?? item.gain ?? 0,
        );
        return {
          ...item,
          rank: item.rank || idx + 1,
          symbol,
          change3m,
          change: change3m,
        };
      });

      const losersFallback = threeMinRowsRaw
        .slice()
        .sort((a, b) => (a.change3m ?? 0) - (b.change3m ?? 0))
        .slice(0, 30);

      const losers = losersFromEndpoint.length ? losersFromEndpoint : losersFallback;
      const prices = buildPriceMap(oneMinRows, now);

      const topBanner = mapRows(topBannerRes);
      const bottomBanner = mapRows(bottomBannerRes);

      const next = {
        crypto: oneMinRows,
        gainers3m: threeMinRowsRaw,
        losers3m: losers,
        topBanner,
        bottomBanner,
        prices,
        updatedAt: now,
      };

      setLatestData(next);
      setIsConnected(true);
      setConnectionStatus('rest');
      setError(null);
      if (debugEnabled) vLog('[WebSocketProvider] Poll success at', new Date(now).toISOString());
      return true;
    } catch (err) {
      console.error('WebSocketProvider poll error', err);
      setIsConnected(false);
      setConnectionStatus('error');
      setError(err);
      return false;
    } finally {
      fetchingRef.current = false;
      if (mountedRef.current) {
        setIsPolling(false);
      }
    }
  }, [debugEnabled, vLog]);

  useEffect(() => {
    mountedRef.current = true;
    const loop = async () => {
      await pollOnce();
      if (!mountedRef.current) return;
      timerRef.current = setTimeout(loop, pollIntervalMs);
    };
    loop();
    return () => {
      mountedRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [pollOnce, pollIntervalMs]);

  const refreshNow = useCallback(async () => {
    return pollOnce();
  }, [pollOnce]);

  const fetchPricesForSymbols = useCallback(
    async (symbols = []) => {
      const priceMap = latestData.prices || {};
      const result = {};
      symbols.forEach((sym) => {
        const key = String(sym || '').toUpperCase();
        if (priceMap[key]) {
          result[key] = priceMap[key];
          return;
        }
        const alt = sanitizeSymbol(key);
        if (priceMap[alt]) {
          result[key] = priceMap[alt];
        }
      });
      return result;
    },
    [latestData.prices],
  );

  const gainersTop20 = useMemo(() => (latestData.crypto || []).slice(0, 20), [latestData.crypto]);
  const gainers3mTop = useMemo(() => (latestData.gainers3m || []).slice(0, 30), [latestData.gainers3m]);
  const losers3mTop = useMemo(() => (latestData.losers3m || []).slice(0, 30), [latestData.losers3m]);

  const getStatus = useCallback(() => ({
    connected: isConnected,
    reconnectAttempts: 0,
    socketId: null,
  }), [isConnected]);

  const contextValue = useMemo(
    () => ({
      isConnected,
      connectionStatus,
      isPolling,
      networkStatus,
      latestData,
      gainersTop20,
      gainers3mTop,
      losers3mTop,
      refreshNow,
      fetchPricesForSymbols,
      startPolling: pollOnce,
      stopPolling: () => {},
      wsManager: null,
      debugEnabled,
      vLog,
      send: () => {},
      getStatus,
      error,
    }),
    [
      connectionStatus,
      debugEnabled,
      error,
      fetchPricesForSymbols,
      gainers3mTop,
      gainersTop20,
      getStatus,
      isConnected,
      isPolling,
      latestData,
      losers3mTop,
      networkStatus,
      pollOnce,
      refreshNow,
      vLog,
    ],
  );

  return (
    <WebSocketContext.Provider value={contextValue}>
      {children}
    </WebSocketContext.Provider>
  );
};

WebSocketProvider.propTypes = {
  children: PropTypes.node,
  pollIntervalMs: PropTypes.number,
};

export default WebSocketContext;
