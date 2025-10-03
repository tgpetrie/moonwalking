import { isMobileDevice, getMobileOptimizedConfig, addVisibilityChangeListener, addNetworkChangeListener } from '../utils/mobileDetection.js';
import { flags } from '../config.js';
import { getApiBaseUrl } from '../api.js';

/**
 * SSE Manager - Replaces WebSocket with Server-Sent Events for free tier compatibility
 * Uses EventSource API for real-time updates from the Durable Object
 */
class SSEManager {
  constructor() {
    this.eventSource = null;
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

    // Build SSE URL
    this.sseUrl = this.buildSSEUrl();

    // Use shared flags
    this.disabled = flags.VITE_DISABLE_WS === true || flags.VITE_DISABLE_SSE === true;
  }

  buildSSEUrl() {
    // Prefer explicit SSE url
    const envSse = import.meta.env?.VITE_SSE_URL;
    if (envSse && typeof envSse === 'string' && envSse.trim()) {
      return envSse.trim();
    }

    // Fallback: derive from API base
    const apiBase = (getApiBaseUrl && typeof getApiBaseUrl === 'function') ? (getApiBaseUrl() || '') : '';

    let computed;
    if (/^https?:\/\//i.test(apiBase)) {
      computed = apiBase;
    } else if (apiBase.startsWith('/')) {
      // relative base: use same-origin
      const origin = (typeof location !== 'undefined') ? location.origin : '';
      computed = origin + apiBase;
    } else {
      const origin = (typeof location !== 'undefined') ? location.origin : '';
      computed = origin + (apiBase ? ('/' + apiBase.replace(/^\//, '')) : '');
    }

    const base = (computed || '').replace(/\/$/, '');
    // Use /sse endpoint instead of /ws
    return base + '/sse';
  }

  connect() {
    if (this.disabled) {
      console.info('SSE disabled by config');
      this.emit('connection', { status: 'failed', reason: 'disabled' });
      return;
    }

    if (this.eventSource && this.isConnected) {
      return;
    }

    try {
      const endpoint = this.sseUrl || '';
      console.log('📡 Connecting to SSE endpoint:', endpoint);

      const eventSource = new EventSource(endpoint);
      this.eventSource = eventSource;

      eventSource.addEventListener('open', () => {
        console.log('✅ SSE connected to', endpoint);
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.emit('connection', { status: 'connected' });
      });

      eventSource.addEventListener('error', (err) => {
        console.error('❌ SSE error:', err);
        this.isConnected = false;

        // EventSource automatically reconnects, but we track state
        if (eventSource.readyState === EventSource.CLOSED) {
          this.emit('connection', { status: 'error', error: 'sse closed' });
          this.handleReconnect();
        } else if (eventSource.readyState === EventSource.CONNECTING) {
          this.emit('connection', { status: 'reconnecting' });
        }
      });

      eventSource.addEventListener('message', (event) => {
        try {
          const msg = JSON.parse(event.data);
          this.handleMessage(msg);
        } catch (e) {
          console.error('Failed to parse SSE message:', e);
        }
      });

    } catch (error) {
      console.error('Error creating SSE connection:', error);
      this.handleReconnect();
    }
  }

  handleMessage(msg) {
    if (msg?.type === 'hello' || msg?.type === 'snapshots') {
      const snap = msg.snapshots || {};

      // Normalize incoming snapshots to the payload shape expected by context
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
        // Build prices map for t3m as well
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

        // losers3m: sort ascending by 3m change
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
  }

  disconnect() {
    if (this.eventSource) {
      try {
        this.eventSource.close();
      } catch (_) {}
      this.eventSource = null;
      this.isConnected = false;
    }
  }

  handleReconnect() {
    // Don't reconnect if app is backgrounded
    if (this.isMobile && !this.isVisible) {
      console.log('📱 Skipping SSE reconnect while app is backgrounded');
      return;
    }

    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const baseDelay = this.isMobile ? this.config.reconnectDelay : 1000;
      const delay = Math.min(baseDelay * Math.pow(2, this.reconnectAttempts), 30000);
      console.log(`🔄 Attempting SSE reconnect in ${delay}ms... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

      setTimeout(() => {
        if (!this.isMobile || this.isVisible) {
          this.disconnect(); // Clean up old connection
          this.connect();
        }
      }, delay);
    } else {
      console.error('❌ Max SSE reconnection attempts reached. Falling back to REST API polling.');
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
          console.error(`Error in SSE callback for ${event}:`, error);
        }
      });
    }
  }

  // Get connection status
  getStatus() {
    return {
      connected: this.isConnected,
      reconnectAttempts: this.reconnectAttempts,
      readyState: this.eventSource ? this.eventSource.readyState : null
    };
  }

  // Mobile-specific optimizations
  setupMobileOptimizations() {
    if (!this.isMobile) return;

    // Handle visibility changes (app backgrounding)
    this.visibilityCleanup = addVisibilityChangeListener((isVisible) => {
      this.isVisible = isVisible;
      if (isVisible && !this.isConnected && !this.disabled) {
        console.log('📱 App became visible, attempting SSE reconnect...');
        this.reconnectAttempts = 0;
        this.connect();
      } else if (!isVisible && this.isConnected) {
        console.log('📱 App backgrounded, closing SSE to save battery');
        this.disconnect();
      }
    });

    // Handle network changes
    this.networkCleanup = addNetworkChangeListener((networkInfo) => {
      this.networkInfo = networkInfo;
      console.log('📱 Network change detected:', networkInfo);

      if (networkInfo.effectiveType === 'slow-2g' || networkInfo.effectiveType === '2g') {
        this.emit('network_degraded', { networkInfo });
      } else if (this.isConnected && networkInfo.effectiveType === '4g') {
        this.emit('network_improved', { networkInfo });
      }

      // Reconnect SSE after network change if it was connected
      if (this.isConnected && this.isVisible) {
        setTimeout(() => {
          if (!this.isConnected) {
            console.log('📱 Reconnecting SSE after network change...');
            this.connect();
          }
        }, 1000);
      }
    });
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
const sseManager = new SSEManager();

export default sseManager;

// Export convenience functions (compatible with WebSocket API)
export const connectSSE = () => sseManager.connect();
export const disconnectSSE = () => sseManager.disconnect();
export const subscribeToSSE = (event, callback) => sseManager.subscribe(event, callback);
export const getSSEStatus = () => sseManager.getStatus();

// Export with WebSocket-compatible names for easy migration
export const connectWebSocket = connectSSE;
export const disconnectWebSocket = disconnectSSE;
export const subscribeToWebSocket = subscribeToSSE;
export const getWebSocketStatus = getSSEStatus;
