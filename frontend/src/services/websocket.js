import { io } from 'socket.io-client';

class WebSocketManager {
  constructor() {
    this.socket = null;
    this.isConnected = false;
    this.subscribers = new Map();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    // Prefer explicit WS url (VITE_WS_URL), else reuse API url (avoids port mismatch 404s)
    const apiUrl = (import.meta.env?.VITE_API_URL || 'http://localhost:5003').replace(/\/$/, '');
    const wsUrl = (import.meta.env?.VITE_WS_URL || apiUrl).replace(/\/$/, '');
    this.baseUrl = wsUrl;
    // Allow opting out by default unless explicitly enabled server-side
    this.disabled = String(import.meta.env?.VITE_DISABLE_WS || 'true').toLowerCase() === 'true';
  }

  connect() {
    if (this.disabled) {
      console.info('WebSocket disabled by VITE_DISABLE_WS');
      this.emit('connection', { status: 'failed', reason: 'disabled' });
      return;
    }
    if (this.socket && this.socket.connected) {
      return;
    }

    try {
  this.socket = io(this.baseUrl, {
        transports: ['websocket', 'polling'],
        upgrade: true,
        rememberUpgrade: true,
        timeout: 10000,
        forceNew: true
      });

      this.socket.on('connect', () => {
        console.log('WebSocket connected to', this.baseUrl);
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.emit('connection', { status: 'connected' });
      });

      this.socket.on('disconnect', (reason) => {
        console.log('WebSocket disconnected:', reason);
        this.isConnected = false;
        this.emit('connection', { status: 'disconnected', reason });
        
        if (reason === 'io server disconnect') {
          // Server disconnected, try to reconnect
          this.handleReconnect();
        }
      });

      this.socket.on('connect_error', (error) => {
        console.error('WebSocket connection error:', error);
        this.isConnected = false;
        this.emit('connection', { status: 'error', error: error.message });
        this.handleReconnect();
      });

      // Listen for real-time crypto data updates
      this.socket.on('crypto_update', (data) => {
        this.emit('crypto_update', data);
      });

      this.socket.on('price_update', (data) => {
        this.emit('price_update', data);
      });

      this.socket.on('watchlist_update', (data) => {
        this.emit('watchlist_update', data);
      });

    } catch (error) {
      console.error('Error creating WebSocket connection:', error);
    }
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
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
    if (this.socket && this.socket.connected) {
      this.socket.emit(event, data);
    } else {
      console.warn(`Cannot send ${event}: WebSocket not connected`);
    }
  }

  // Get connection status
  getStatus() {
    return {
      connected: this.isConnected,
      reconnectAttempts: this.reconnectAttempts,
      socketId: this.socket?.id || null
    };
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