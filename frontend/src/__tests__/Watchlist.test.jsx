import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

// Mock the websocket context/hook so Watchlist can mount
vi.mock('../context/websocketcontext.jsx', () => {
  return {
    useWebSocket: () => ({ state: { connected: true, prices: { 'BTC-USD': { price: 50000 } } } }),
    WebSocketContext: { Provider: ({ children }) => children }
  }
})

import Watchlist from '../components/Watchlist.jsx'

describe('Watchlist component', () => {
  let originalSetItem
  let consoleSpy

  beforeEach(() => {
    // spy on localStorage.setItem and console.log
    originalSetItem = Storage.prototype.setItem
    Storage.prototype.setItem = vi.fn()
    consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {})
    // clear localStorage
    localStorage.clear()
  })

  afterEach(() => {
    Storage.prototype.setItem = originalSetItem
    consoleSpy.mockRestore()
    vi.restoreAllMocks()
  })

  it('persists symbols to localStorage and logs visible symbols', async () => {
    render(<Watchlist initialSymbols={[ 'BTC-USD' ]} />)

    // Wait for useEffect to run and for component to call setItem and console.log
    await waitFor(() => {
      expect(localStorage.setItem).toHaveBeenCalled()
      expect(consoleSpy).toHaveBeenCalled()
    })

    // Check that setItem was called for watchlist_symbols
    const calledWithWatchlist = Array.from(localStorage.setItem.mock.calls).some(
      c => c[0] === 'watchlist_symbols'
    )
    expect(calledWithWatchlist).toBe(true)

    // console log should include the visible symbols string
    const logCalls = consoleSpy.mock.calls.map(args => args.join(' '))
    const found = logCalls.some(s => s.includes('Watchlist visible symbols:') && s.includes('BTC-USD'))
    expect(found).toBe(true)
  })
})
