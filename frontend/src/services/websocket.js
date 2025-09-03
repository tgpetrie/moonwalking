import { addVisibilityChangeListener, addNetworkChangeListener } from '../utils/mobileDetection.js';

// Helpers
const now = () => Date.now();
const withJitter = (ms) => {
  const delta = ms * 0.2; // +/-20%
  return Math.max(0, ms - delta + Math.random() * (2 * delta));
};

// Finite states
const STATES = Object.freeze({
  IDLE: 'IDLE',
  CONNECTING: 'CONNECTING',
  OPEN: 'OPEN',
  CLOSING: 'CLOSING',
  BACKOFF: 'BACKOFF',
  DESTROYED: 'DESTROYED',
});

class WebSocketManager {
  constructor(opts = {}) {
    // Core
    this.socket = null;
    this.state = STATES.IDLE;
    this.subscribers = new Map(); // event -> Set<fn>
    this.pendingQueue = []; // messages queued while not OPEN

    // Config / env
    const originWs = (typeof location !== 'undefined')
      ? ((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host)
      : 'ws://127.0.0.1:8787';
    const wsHost = (import.meta?.env?.VITE_WS_URL || originWs).replace(/\/$/, '');
    this.baseUrl = wsHost; // host only; endpoint is /ws
    this.disabled = String(import.meta?.env?.VITE_DISABLE_WS || 'false').toLowerCase() === 'true';

    // Backoff/heartbeat
    this.reconnectAttempts = 0;
    this.config = {
      baseDelayMs: opts.baseDelayMs ?? 800,
      maxDelayMs: 30000,
      maxReconnectAttempts: opts.maxReconnectAttempts ?? 12,
      heartbeatIntervalMs: opts.heartbeatIntervalMs ?? 25000,
      heartbeatTimeoutMs: opts.heartbeatTimeoutMs ?? 8000,
    };
    this.timers = { reconnect: null, heartbeat: null, heartbeatTimeout: null };

    // Visibility / network gating
    this.isVisible = (typeof document !== 'undefined' && typeof document.hidden !== 'undefined') ? !document.hidden : true;
    this._visibilityCleanup = this._installVisibilityHandler();
    this._onlineCleanup = this._installOnlineHandlers();

    // Mobile network-change assist (optional, safe on desktop)
    this.networkInfo = null;
    this.networkCleanup = addNetworkChangeListener?.((info) => {
      this.networkInfo = info;
      // A network change can stale existing TCP; force a fresh socket if app is visible
      if (this.isVisible && !this.disabled) {
        this.disconnect(4000, 'network_change');
        setTimeout(() => this.connect(), 1000);
      }
    });
  }

  /* ========== Public API ========== */
  connect() {
    if (this.disabled || this.state === STATES.DESTROYED) return;
    if (this.state === STATES.CONNECTING || this.state === STATES.OPEN) return; // single-flight
    if (!this.isVisible || (typeof navigator !== 'undefined' && !navigator.onLine)) return; // wait for gates

    this._clearTimer('reconnect');
    this._transition(STATES.CONNECTING);

    const endpoint = this.baseUrl + '/ws';
    let ws;
    try {
      ws = new WebSocket(endpoint);
    } catch (e) {
      console.error('[WS] construct failed:', e);
      this._scheduleReconnect('construct_error');
      return;
    }

    this.socket = ws;

    ws.addEventListener('open', () => this._onOpen(endpoint));
    ws.addEventListener('close', (ev) => this._onClose(ev));
    ws.addEventListener('error', (ev) => this._onError(ev));
    ws.addEventListener('message', (ev) => this._onMessage(ev));
  }

  disconnect(code = 1000, reason = 'client_close') {
    this._clearHeartbeat();
    this._clearTimer('reconnect');
    if (this.socket) {
      this._transition(STATES.CLOSING);
      try { this.socket.close(code, reason); } catch (_) {}
      this.socket = null;
    }
    this._transition(STATES.IDLE);
  }

  destroy() {
    this.disabled = true;
    this.disconnect(1000, 'destroy');
    this._visibilityCleanup?.();
    this._onlineCleanup?.();
    this.networkCleanup?.();
    this._transition(STATES.DESTROYED);
  }

  // Publish/subscribe within app
  subscribe(event, callback) {
    if (!this.subscribers.has(event)) this.subscribers.set(event, new Set());
    this.subscribers.get(event).add(callback);
    return () => this.unsubscribe(event, callback);
  }

  unsubscribe(event, callback) {
    const set = this.subscribers.get(event);
    if (!set) return;
    set.delete(callback);
    if (set.size === 0) this.subscribers.delete(event);
  }

  emit(event, data) {
    const set = this.subscribers.get(event);
    if (!set) return;
    for (const fn of set) {
      try { fn(data); } catch (e) { console.error(`[WS] subscriber error (${event})`, e); }
    }
  }

  send(event, data) {
    const payload = JSON.stringify({ event, data });
    if (this.state === STATES.OPEN && this.socket?.readyState === WebSocket.OPEN) {
      try { this.socket.send(payload); } catch (_) {}
      return true;
    }
    this.pendingQueue.push(payload);
    return false;
  }

  getStatus() {
    return {
      connected: this.state === STATES.OPEN,
      reconnectAttempts: this.reconnectAttempts,
      state: this.state,
    };
  }

  /* ========== Internals ========== */
  _transition(next) {
    this.state = next;
    this.emit('connection', { status: next });
  }

  _onOpen(endpoint) {
    this.reconnectAttempts = 0;
    this._transition(STATES.OPEN);
    this.emit('connection', { status: 'connected', url: endpoint });

    // Flush queued messages
    if (this.pendingQueue.length) {
      for (const m of this.pendingQueue.splice(0)) {
        try { this.socket?.send(m); } catch (_) {}
      }
    }

    // Start heartbeat
    this._startHeartbeat();
  }

  _onClose(ev) {
    this._clearHeartbeat();
    if (this.state === STATES.DESTROYED) return;
    this._transition(STATES.IDLE);
    this._scheduleReconnect(ev.reason || 'close', ev.code);
  }

  _onError(_ev) {
    // Close usually follows; do not double-schedule here.
    this.emit('connection', { status: 'error', error: 'ws_error' });
  }

  _onMessage(ev) {
    let msg = ev.data;
    try { msg = typeof msg === 'string' ? JSON.parse(msg) : msg; } catch (_) {}

    // Heartbeat pong
    if (msg && (msg.type === 'pong' || msg.event === 'pong')) {
      this._clearTimer('heartbeatTimeout');
      return;
    }

    // Existing app messages
    try {
      if (msg?.type === 'hello' || msg?.type === 'snapshots') {
        const snap = msg.snapshots || {};
        if (Array.isArray(snap.t1m) && snap.t1m.length) {
          this.emit('crypto_update', snap.t1m);
          const prices = {};
          snap.t1m.forEach((c) => {
            if (c?.symbol) {
              prices[c.symbol] = {
                price: c.current_price ?? c.price ?? 0,
                changePercent: c.price_change_percentage_1min ?? c.change ?? 0,
                timestamp: now(),
              };
            }
          });
          if (Object.keys(prices).length) this.emit('price_update', prices);
        }
      }
    } catch (e) {
      console.debug('WS message handler error', e);
    }
  }

  _scheduleReconnect(reason = 'unknown', code) {
    if (this.disabled || this.state === STATES.DESTROYED) return;
    if (typeof navigator !== 'undefined' && !navigator.onLine) return; // wait for gates
    if (!this.isVisible) return;

    if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
      this.emit('connection', { status: 'failed', attempts: this.reconnectAttempts, reason, code });
      return;
    }

    this._clearTimer('reconnect');
    this.reconnectAttempts += 1;
    const backoff = Math.min(
      this.config.baseDelayMs * Math.pow(2, this.reconnectAttempts - 1),
      this.config.maxDelayMs
    );
    const delay = withJitter(backoff);
    this._transition(STATES.BACKOFF);
    this.timers.reconnect = setTimeout(() => this.connect(), delay);
    this.emit('connection', { status: 'reconnecting', inMs: Math.round(delay), attempts: this.reconnectAttempts, reason, code });
  }

  _startHeartbeat() {
    this._clearHeartbeat();
    this.timers.heartbeat = setInterval(() => {
      if (this.state !== STATES.OPEN || !this.socket) return;
      try { this.socket.send(JSON.stringify({ type: 'ping', ts: now() })); } catch (_) {}
      this._clearTimer('heartbeatTimeout');
      this.timers.heartbeatTimeout = setTimeout(() => {
        try { this.socket?.close(4000, 'heartbeat_timeout'); } catch (_) {}
      }, this.config.heartbeatTimeoutMs);
    }, this.config.heartbeatIntervalMs);
  }

  _clearHeartbeat() {
    this._clearTimer('heartbeat');
    this._clearTimer('heartbeatTimeout');
  }

  _clearTimer(key) {
    const t = this.timers[key];
    if (!t) return;
    clearTimeout(t);
    clearInterval(t);
    this.timers[key] = null;
  }

  _installVisibilityHandler() {
    const handler = () => {
      this.isVisible = (typeof document !== 'undefined' && typeof document.hidden !== 'undefined') ? !document.hidden : true;
      if (this.isVisible) {
        if ((this.state === STATES.IDLE || this.state === STATES.BACKOFF) && (typeof navigator === 'undefined' || navigator.onLine)) {
          this.reconnectAttempts = 0;
          this.connect();
        }
      } else {
        this._clearTimer('reconnect');
      }
    };
    const cleanup = addVisibilityChangeListener ? addVisibilityChangeListener((v) => { this.isVisible = v; handler(); }) : null;
    if (!cleanup && typeof document !== 'undefined') document.addEventListener('visibilitychange', handler);
    return () => {
      if (cleanup) cleanup(); else if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', handler);
    };
  }

  _installOnlineHandlers() {
    const online = () => {
      if (this.state !== STATES.OPEN) {
        this.reconnectAttempts = 0;
        this.connect();
      }
    };
    const offline = () => { this._clearTimer('reconnect'); };
    if (typeof window !== 'undefined') {
      window.addEventListener('online', online);
      window.addEventListener('offline', offline);
    }
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('online', online);
        window.removeEventListener('offline', offline);
      }
    };
  }
}

// Singleton
const wsManager = new WebSocketManager();
export default wsManager;

// Convenience exports (API preserved)
export const connectWebSocket = () => wsManager.connect();
export const disconnectWebSocket = () => wsManager.disconnect();
export const subscribeToWebSocket = (event, callback) => wsManager.subscribe(event, callback);
export const sendWebSocketMessage = (event, data) => wsManager.send(event, data);
export const getWebSocketStatus = () => wsManager.getStatus();
