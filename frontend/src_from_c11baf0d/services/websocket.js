import { isMobileDevice, getMobileOptimizedConfig, addVisibilityChangeListener, addNetworkChangeListener } from '../utils/mobileDetection.js';
import { flags } from '../config.js';
import { getApiBaseUrl } from '../api.js';

class WebSocketManager {
  constructor() {
    this.socket = null; // Native WebSocket
    this.isConnected = false;
    this.subscribers = new Map();
    this.reconnectAttempts = 0;
    this.isMobile = isMobileDevice();
    this.config = getMobileOptimizedConfig();
    this.maxReconnectAttempts = this.config.maxReconnectAttempts;
    this.isVisible = !document.hidden;
    this.networkInfo = null;
    
    // Setup mobile-specific listeners
    this.setupMobileOptimizations();
    // Prefer explicit WS url (VITE_WS_URL). If provided with ws:// or wss://, treat it as a FULL endpoint.
    // Otherwise, derive from API base (safer than location.host) and append '/ws' exactly once.
    const envWs = import.meta.env?.VITE_WS_URL;
    this.wsUrl = '';
    if (envWs && typeof envWs === 'string' && envWs.trim()) {
      const trimmed = envWs.trim();
      if (/^wss?:\/\//i.test(trimmed)) {
        // Full endpoint provided; normalize but do NOT append '/ws' later
        this.wsUrl = trimmed.replace(/\/$/, '');
      } else {
        // Non-scheme value: treat as base and convert
        const base = trimmed.replace(/\/$/, '');
        const maybe = /^https?:\/\//i.test(base) ? base.replace(/^http/i, 'ws') : base;
        this.wsUrl = maybe + (maybe.endsWith('/ws') ? '' : '/ws');
      }
    } else {
      const apiBase = (getApiBaseUrl && typeof getApiBaseUrl === 'function') ? (getApiBaseUrl() || '') : '';
      // If apiBase already contains protocol+host, convert http(s) -> ws(s); else fall back to same-origin
      let computed;
      if (/^https?:\/\//i.test(apiBase)) {
        computed = apiBase.replace(/^http/i, 'ws');
      } else if (apiBase.startsWith('/')) {
        // relative base: use same-origin
        const origin = (typeof location !== 'undefined') ? ((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host) : '';
        computed = origin + apiBase;
      } else {
        const origin = (typeof location !== 'undefined') ? ((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host) : '';
        computed = origin + (apiBase ? ('/' + apiBase.replace(/^\//, '')) : '');
      }
      const base = (computed || '').replace(/\/$/, '');
      this.wsUrl = base + (base.endsWith('/ws') ? '' : '/ws');
    }
    // Use shared flags (default: enabled unless explicitly disabled)
    this.disabled = flags.VITE_DISABLE_WS === true;
  }

  connect() {
    if (this.disabled) {
      console.info('WebSocket disabled by VITE_DISABLE_WS');
      this.emit('connection', { status: 'failed', reason: 'disabled' });
      return;
    }
    if (this.socket && this.isConnected) {
      return;
    }

    try {
  const endpoint = this.wsUrl || '';
  const ws = new WebSocket(endpoint);
      this.socket = ws;

      ws.addEventListener('open', () => {
        console.log('WebSocket connected to', endpoint);
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.emit('connection', { status: 'connected' });
      });
      ws.addEventListener('close', (ev) => {
        this.isConnected = false;
        this.emit('connection', { status: 'disconnected', reason: ev.reason || 'close' });
        this.handleReconnect();
      });
      ws.addEventListener('error', (err) => {
        this.isConnected = false;
        this.emit('connection', { status: 'error', error: 'ws error' });
        this.handleReconnect();
      });
      ws.addEventListener('message', (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg?.type === 'hello' || msg?.type === 'snapshots') {
            const snap = msg.snapshots || {};

            // Normalize incoming snapshots to the payload shape expected by context
            // snap.t1m => gainers1m; snap.t3m => gainers3m; losers3m derived from t3m sorted ascending
            const payload = {};

            if (Array.isArray(snap.t1m) && snap.t1m.length) {
              payload.gainers1m = snap.t1m;
              // Build prices map for quick symbol->price updates
              const prices = {};
              snap.t1m.forEach((c) => {
                if (c?.symbol) {
                  prices[c.symbol] = {
                    price: c.current_price ?? c.price ?? 0,
                    changePercent: c.price_change_percentage_1min ?? c.change ?? 0,
                    timestamp: Date.now(),
                  };
                }
              });
              if (Object.keys(prices).length) this.emit('price_update', prices);
            }

            if (Array.isArray(snap.t3m) && snap.t3m.length) {
              payload.gainers3m = snap.t3m;
              // Build prices map for t3m as well (so UI can show prices even if t1m hasn't arrived)
              const prices3 = {};
              snap.t3m.forEach((c) => {
                if (c?.symbol) {
                  prices3[c.symbol] = {
                    price: c.current_price ?? c.price ?? 0,
                    changePercent: c.price_change_percentage_3min ?? c.change ?? c.change3m ?? 0,
                    timestamp: Date.now(),
                  };
                }
              });
              if (Object.keys(prices3).length) this.emit('price_update', prices3);

              // losers3m: be permissive about which field holds the 3m pct (price_change_percentage_3min, change, change3m, gain)
              const losers = snap.t3m
                .filter((x) => {
                  const v = x?.price_change_percentage_3min ?? x?.change ?? x?.change3m ?? x?.gain;
                  return typeof v === 'number' || (!Number.isNaN(parseFloat(v)) && isFinite(parseFloat(v)));
                })
                .slice()
                .sort((a, b) => {
                  const va = Number(a?.price_change_percentage_3min ?? a?.change ?? a?.change3m ?? a?.gain ?? 0);
                  const vb = Number(b?.price_change_percentage_3min ?? b?.change ?? b?.change3m ?? b?.gain ?? 0);
                  return va - vb;
                })
                .slice(0, 30);
              if (losers.length) payload.losers3m = losers;
            }

            if (Object.keys(payload).length) {
              this.emit('crypto_update', { payload });
            }
          }
        } catch (_) {}
      });

    } catch (error) {
      console.error('Error creating WebSocket connection:', error);
    }
  }

  disconnect() {
    if (this.socket) {
      try { this.socket.close(); } catch (_) {}
      this.socket = null;
      this.isConnected = false;
    }
  }

  handleReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
      console.log(`Attempting to reconnect in ${delay}ms... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
      
      setTimeout(() => {
        this.connect();
      }, delay);
    } else {
      console.error('Max reconnection attempts reached. Falling back to REST API polling.');
      this.emit('connection', { status: 'failed', attempts: this.reconnectAttempts });
    }
  }

  subscribe(event, callback) {
    if (!this.subscribers.has(event)) {
      this.subscribers.set(event, new Set());
    }
    this.subscribers.get(event).add(callback);
    
    // Return unsubscribe function
    return () => {
      const callbacks = this.subscribers.get(event);
      if (callbacks) {
        callbacks.delete(callback);
        if (callbacks.size === 0) {
          this.subscribers.delete(event);
        }
      }
    };
  }

  emit(event, data) {
    const callbacks = this.subscribers.get(event);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in WebSocket callback for ${event}:`, error);
        }
      });
    }
  }

  // Send data to server if connected
  send(event, data) {
    // Native WS: send typed messages if needed later
    if (this.socket && this.isConnected) {
      try { this.socket.send(JSON.stringify({ event, data })); } catch (_) {}
    }
  }

  // Get connection status
  getStatus() {
    return {
      connected: this.isConnected,
      reconnectAttempts: this.reconnectAttempts,
      socketId: null
    };
  }

  // Mobile-specific optimizations
  setupMobileOptimizations() {
    if (!this.isMobile) return;

    // Handle visibility changes (app backgrounding)
    this.visibilityCleanup = addVisibilityChangeListener((isVisible) => {
      this.isVisible = isVisible;
      if (isVisible && !this.isConnected && !this.disabled) {
        // Reconnect when app becomes visible again
        console.log('📱 App became visible, attempting WebSocket reconnect...');
        this.reconnectAttempts = 0; // Reset attempts
        this.connect();
      } else if (!isVisible && this.isConnected) {
        // Optionally disconnect when backgrounded to save battery
        console.log('📱 App backgrounded, keeping WebSocket open but reducing activity');
      }
    });

    // Handle network changes (WiFi to cellular, etc.)
    this.networkCleanup = addNetworkChangeListener((networkInfo) => {
      this.networkInfo = networkInfo;
      console.log('📱 Network change detected:', networkInfo);
      
      // If connection is poor, fall back to polling faster
      if (networkInfo.effectiveType === 'slow-2g' || networkInfo.effectiveType === '2g') {
        this.emit('network_degraded', { networkInfo });
      } else if (this.isConnected && networkInfo.effectiveType === '4g') {
        this.emit('network_improved', { networkInfo });
      }
      
      // Reconnect WebSocket after network change if it was connected
      if (this.isConnected && this.isVisible) {
        setTimeout(() => {
          if (!this.isConnected) {
            console.log('📱 Reconnecting after network change...');
            this.connect();
          }
        }, 1000);
      }
    });
  }

  // Enhanced reconnect logic for mobile
  handleReconnect() {
    // Don't reconnect if app is backgrounded
    if (this.isMobile && !this.isVisible) {
      console.log('📱 Skipping reconnect while app is backgrounded');
      return;
    }

    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      // Use mobile-optimized shorter delay
      const baseDelay = this.isMobile ? this.config.reconnectDelay : 1000;
      const delay = Math.min(baseDelay * Math.pow(2, this.reconnectAttempts), 30000);
      console.log(`📱 Mobile reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms...`);
      
      setTimeout(() => {
        // Double-check visibility before reconnecting
        if (!this.isMobile || this.isVisible) {
          this.connect();
        }
      }, delay);
    } else {
      console.error('📱 Max mobile reconnection attempts reached. Falling back to REST API polling.');
      this.emit('connection', { status: 'failed', attempts: this.reconnectAttempts, isMobile: this.isMobile });
    }
  }

  // Cleanup mobile listeners
  destroy() {
    if (this.visibilityCleanup) {
      this.visibilityCleanup();
    }
    if (this.networkCleanup) {
      this.networkCleanup();
    }
    this.disconnect();
  }
}

// Create singleton instance
const wsManager = new WebSocketManager();

export default wsManager;

// Export convenience functions
export const connectWebSocket = () => wsManager.connect();
export const disconnectWebSocket = () => wsManager.disconnect();
export const subscribeToWebSocket = (event, callback) => wsManager.subscribe(event, callback);
export const sendWebSocketMessage = (event, data) => wsManager.send(event, data);
export const getWebSocketStatus = () => wsManager.getStatus();
