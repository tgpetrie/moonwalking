// WebSocket (socket.io if available) context provider.
// Safe in dev/tests even if no backend socket is running.
// ensure createContext is available and export a named context for consumers
import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'
import * as api from '../lib/api'
import * as socketio from 'socket.io-client'
export const WebSocketContext = createContext(null)

function createFallbackBus() {
  const target = new EventTarget()
  return {
    on: (evt, cb) => target.addEventListener(evt, cb),
    off: (evt, cb) => target.removeEventListener(evt, cb),
    emit: (evt, payload) => target.dispatchEvent(new CustomEvent(evt, { detail: payload })),
    close: () => {},
  }
}

export function WebSocketProvider({ children }) {
  const [connected, setConnected] = useState(false)
  const socketRef = useRef(null)
  const busRef = useRef(null)
  // store the last tables snapshot in state so updates re-render consumers
  const [lastTables, setLastTables] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem('tables:last') || '{}') } catch { return {} }
  })
  const lastTablesRef = useRef(lastTables)

  useEffect(() => {
    let mounted = true
    let cleanup = () => {}

    // Attempt to obtain socket.io synchronously first so tests that mock
    // socket.io-client at the top-level see handler registration immediately.
    const getIoSync = () => {
      return socketio?.io || socketio?.default?.io || socketio?.default || socketio || (typeof window !== 'undefined' ? window.io : null)
    }

    const setupWithIo = (ioFn) => {
      try {
        // Be defensive: tests sometimes partially mock ../lib/api. Prefer calling getApiBaseUrl() when available.
        let baseRaw = ''
        try { if (typeof api.getApiBaseUrl === 'function') baseRaw = api.getApiBaseUrl() } catch (e) { baseRaw = '' }
        const base = (baseRaw || '').replace(/^http/, 'ws')

        const s = ioFn(base || undefined, { transports: ['websocket'], path: '/socket.io' })
        socketRef.current = s
        busRef.current = {
          on: (evt, cb) => s.on(evt, cb),
          off: (evt, cb) => (typeof s.off === 'function' ? s.off(evt, cb) : s.removeListener?.(evt, cb)),
          emit: (evt, payload) => s.emit(evt, payload),
          close: () => s.close(),
        }

        const onConnect = () => setConnected(true)
        const onDisconnect = () => setConnected(false)
        const onTables = (payload) => {
          try { sessionStorage.setItem('tables:last', JSON.stringify(payload)) } catch {}
          lastTablesRef.current = payload
          setLastTables(payload)
          try { api.shareTables?.(payload) } catch {}
          try { api.bus?.emit?.('tables:update', payload) } catch {}
          try { busRef.current.emit('tables:update', payload) } catch {}
        }
        const onCrypto = (payload) => {
          try { sessionStorage.setItem('crypto:last', JSON.stringify(payload)) } catch {}
          try { api.shareAlerts?.(payload) } catch {}
          try { api.bus?.emit?.('crypto', payload) } catch {}
        }
        const onCryptoUpdate = (payload) => {
          try { sessionStorage.setItem('crypto_update:last', JSON.stringify(payload)) } catch {}
          try { api.bus?.emit?.('crypto_update', payload) } catch {}
        }

        s.on('connect', onConnect)
        s.on('disconnect', onDisconnect)
        s.on('tables:update', onTables)
        s.on('crypto', onCrypto)
        s.on('crypto_update', onCryptoUpdate)

        cleanup = () => {
          try {
            if (typeof s.off === 'function') {
              s.off('connect', onConnect)
              s.off('disconnect', onDisconnect)
              s.off('tables:update', onTables)
              s.off('crypto', onCrypto)
              s.off('crypto_update', onCryptoUpdate)
            } else {
              s.removeListener?.('connect', onConnect)
              s.removeListener?.('disconnect', onDisconnect)
              s.removeListener?.('tables:update', onTables)
              s.removeListener?.('crypto', onCrypto)
              s.removeListener?.('crypto_update', onCryptoUpdate)
            }
          } catch (_) {}
          try { s.close() } catch {}
        }
      } catch (e) {
        // swallow and fall back to in-page bus
      }
    }

    const ioSync = getIoSync()
    if (ioSync) {
      setupWithIo(ioSync)
    } else {
      // async fallback: dynamic import socket.io-client if available, otherwise fallback bus
      ;(async () => {
        let ioFn = null
        try {
          const mod = await import('socket.io-client')
          ioFn = mod?.io || mod?.default?.io || mod?.default || mod
        } catch (e) {
          ioFn = (typeof window !== 'undefined' ? window.io : null)
        }

        if (!mounted) return

        if (ioFn) setupWithIo(ioFn)
        else {
          const bus = createFallbackBus()
          busRef.current = bus
          socketRef.current = bus
          setConnected(false)
          cleanup = () => {}
        }
      })()
    }

    return () => { mounted = false; try { cleanup() } catch {} }
  }, [])

  const value = useMemo(() => ({
    connected,
    socket: socketRef.current,
    on: (...args) => busRef.current?.on?.(...args),
    off: (...args) => busRef.current?.off?.(...args),
    emit: (...args) => busRef.current?.emit?.(...args),
    lastTables: lastTables || lastTablesRef.current || {},
    tables: lastTables || lastTablesRef.current || {},
    latestData: lastTables || lastTablesRef.current || {}, // Add latestData alias for component compatibility
  }), [connected, lastTables])

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  )
}

export function useWebSocket() {
  const ctx = useContext(WebSocketContext)
  if (!ctx) {
    // Soft fallback so components don't crash if the provider is omitted in some routes/tests.
    if (typeof window !== 'undefined' && window.console) {
      try { console.warn('useWebSocket: no <WebSocketProvider> found; using no-op fallback') } catch {}
    }
    return {
      connected: false,
      socket: null,
      on: () => {},
      off: () => {},
      emit: () => {},
      lastTables: {},
      latestData: {}, // Add latestData to fallback as well
    }
  }
  return ctx
}

// compatibility alias expected by older tests/consumers
export const useWebSocketData = useWebSocket

export default WebSocketProvider