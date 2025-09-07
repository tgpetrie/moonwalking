import { isMobileDevice, getMobileOptimizedConfig, addVisibilityChangeListener, addNetworkChangeListener } from '../utils/mobileDetection.js';
import { flags } from '../config.js';

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
    // Prefer explicit WS url (VITE_WS_URL), else same-origin
    const originWs = (typeof location !== 'undefined')
      ? ((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host)
      : 'ws://127.0.0.1:8787';
    const wsHost = (import.meta.env?.VITE_WS_URL || originWs).replace(/\/$/, '');
    this.baseUrl = wsHost; // host only; endpoint is /ws
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
      const endpoint = this.baseUrl + '/ws';
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
            // Emit events consistent with existing context listeners
            if (Array.isArray(snap.t1m) && snap.t1m.length) {
              this.emit('crypto_update', snap.t1m);
              // Build prices map
              const prices = {};
              snap.t1m.forEach(c => { if (c?.symbol) prices[c.symbol] = { price: c.current_price ?? c.price ?? 0, changePercent: c.price_change_percentage_1min ?? c.change ?? 0, timestamp: Date.now() }; });
              if (Object.keys(prices).length) this.emit('price_update', prices);
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
