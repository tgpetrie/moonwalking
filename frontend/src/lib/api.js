import { useEffect, useState } from 'react'

export const API_ENDPOINTS = {
  t1m: '/api/component/gainers-table-1min',
  t3m: '/api/component/gainers-table',
  losers1m: '/api/component/losers-table-1min',
  losers3m: '/api/component/losers-table',
  topBanner: '/api/component/top-banner-scroll',
  bottomBanner: '/api/component/bottom-banner-scroll',
  watchlist: '/api/component/watchlist',
}

export async function fetchJSON(url, opts) {
  const res = await fetch(url, opts)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export function getApiBaseUrl() {
  if (typeof window === 'undefined') return ''
  return window.location.origin || ''
}

let _bc = null
if (typeof window !== 'undefined' && 'BroadcastChannel' in window) {
  try { _bc = new BroadcastChannel('ws-bus') } catch (e) { _bc = null }
}

export const bus = (() => {
  // internal list of "message" listeners for BroadcastChannel-like API
  const listeners = new Set()
  // helper to dispatch raw message objects to listeners
  function dispatchRaw(msg) {
    try {
      for (const h of Array.from(listeners)) {
        try { h({ data: msg }) } catch (e) { /* swallow handler errors */ }
      }
    } catch (e) {}
  }

  // emit: high-level helper that broadcasts {type,payload}
  function emit(type, payload) {
    try {
      const msg = { type, payload }
      if (_bc) _bc.postMessage(msg)
      if (typeof window !== 'undefined' && window.dispatchEvent) {
        const ev = new CustomEvent('ws-bus', { detail: msg })
        window.dispatchEvent(ev)
      }
      // also dispatch to in-process listeners in the same shape as BroadcastChannel
      dispatchRaw(msg)
    } catch (e) {}
  }

  // on: convenience listener for the high-level emit API — receives the message object
  function on(cb) {
    if (typeof window === 'undefined') return () => {}
    const handler = (ev) => cb(ev.detail)
    window.addEventListener('ws-bus', handler)
    // also subscribe to in-memory listeners so bus.on works even without BroadcastChannel
    listeners.add((raw) => cb(raw.data))
    return () => {
      try { window.removeEventListener('ws-bus', handler) } catch (_) {}
      // remove the in-memory listener we added (best-effort)
      for (const h of Array.from(listeners)) {
        try {
          // compare by function string as proxy; remove first matching
          if (h.toString() === ((m)=>cb(m)).toString()) { listeners.delete(h); break }
        } catch (_) {}
      }
    }
  }

  // postMessage / addEventListener / removeEventListener / onmessage: BroadcastChannel-compatible surface
  function postMessage(msg) {
    try {
      if (_bc) _bc.postMessage(msg)
      if (typeof window !== 'undefined' && window.dispatchEvent) {
        const ev = new CustomEvent('ws-bus', { detail: msg })
        window.dispatchEvent(ev)
      }
      dispatchRaw(msg)
    } catch (e) {}
  }

  function addEventListener(type, handler) {
    if (type !== 'message') return
    listeners.add(handler)
  }

  function removeEventListener(type, handler) {
    if (type !== 'message') return
    listeners.delete(handler)
  }

  // onmessage setter/getter backed by a single handler
  let _onmessage = null
  function setOnMessage(fn) {
    if (typeof _onmessage === 'function') listeners.delete(_onmessage)
    _onmessage = fn
    if (typeof fn === 'function') listeners.add(fn)
  }

  return {
    emit,
    on,
    postMessage,
    addEventListener,
    removeEventListener,
    get onmessage() { return _onmessage },
    set onmessage(fn) { setOnMessage(fn) },
  }
})()

export function shareTables(tables) {
  try { bus.emit('tables:update', tables ?? {}) } catch {}
}

export function shareAlerts(alerts) {
  try { bus.emit('alerts:update', alerts ?? { items: [] }) } catch {}
}

export function useTablesFromSocket() {
  const [tables, setTables] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem('tables:last') || '{}') } catch { return {} }
  })

  useEffect(() => {
    if (!bus) return () => {}
    const unsub = bus.on((msg) => {
      if (!msg) return
      if (msg.type === 'tables:update') setTables(msg.payload ?? {})
    })
    return unsub
  }, [])

  return tables
}

export default {
  API_ENDPOINTS,
  fetchJSON,
  getApiBaseUrl,
  bus,
  shareTables,
  shareAlerts,
}