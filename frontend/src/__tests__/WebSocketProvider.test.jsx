import React from 'react'
import { render, screen, waitFor, act } from '@testing-library/react'
import { vi } from 'vitest'

// Mock ../lib/api to provide bus/share helpers and avoid network calls
vi.mock('../lib/api', () => {
  return {
    getApiBaseUrl: () => '',
    bus: { emit: vi.fn(), on: () => () => {} },
    shareTables: vi.fn(),
    shareAlerts: vi.fn(),
  }
})

// Create a fake socket and mock socket.io-client.io to return it
const handlers = {}
const fakeSocket = {
  on: (name, cb) => { handlers[name] = cb },
  close: vi.fn(),
}

vi.mock('socket.io-client', () => ({ io: () => fakeSocket }))

import { WebSocketProvider, useWebSocketData } from '../context/websocketcontext.jsx'

function ShowTables() {
  const { tables } = useWebSocketData()
  return <div data-testid="tables">{JSON.stringify(tables)}</div>
}

describe('WebSocketProvider', () => {
  beforeEach(() => {
    Object.keys(handlers).forEach(k => delete handlers[k])
    sessionStorage.clear()
    vi.resetAllMocks()
  })

  it('persists tables:last on tables:update and updates context', async () => {
    render(
      <WebSocketProvider>
        <ShowTables />
      </WebSocketProvider>
    )

    const payload = { t3m: [{ symbol: 'BTC-USD', price: 123, '3m': 5 }] }

    // wait for the provider to register socket handlers
    await waitFor(() => {
      if (typeof handlers['tables:update'] !== 'function') throw new Error('handler not registered yet')
    })

  // simulate socket emit (wrap in act to avoid React testing warning)
  act(() => { handlers['tables:update'](payload) })

    await waitFor(() => {
      const node = screen.getByTestId('tables')
      expect(node.textContent).toContain('BTC-USD')
    })

    // sessionStorage persisted
    expect(sessionStorage.getItem('tables:last')).toBe(JSON.stringify(payload))
  })

  it('persists crypto:last when crypto event received', async () => {
    render(
      <WebSocketProvider>
        <ShowTables />
      </WebSocketProvider>
    )

    const payload = { gainers: [{ symbol: 'ETH-USD', current: 2 }] }

    await waitFor(() => {
      if (typeof handlers['crypto'] !== 'function') throw new Error('crypto handler not ready')
    })

    act(() => { handlers['crypto'](payload) })

    await waitFor(() => {
      expect(sessionStorage.getItem('crypto:last')).toBe(JSON.stringify(payload))
    })
  })

  it('persists crypto_update:last when crypto_update event received', async () => {
    render(
      <WebSocketProvider>
        <ShowTables />
      </WebSocketProvider>
    )

    const payload = { gainers: [{ symbol: 'XRP-USD', current: 1.5 }] }

    await waitFor(() => {
      if (typeof handlers['crypto_update'] !== 'function') throw new Error('crypto_update handler not ready')
    })

    act(() => { handlers['crypto_update'](payload) })

    await waitFor(() => {
      expect(sessionStorage.getItem('crypto_update:last')).toBe(JSON.stringify(payload))
    })
  })

  it('closes socket on unmount', async () => {
    const { unmount } = render(
      <WebSocketProvider>
        <ShowTables />
      </WebSocketProvider>
    )

    // ensure handler registration
    await waitFor(() => {
      if (typeof handlers['tables:update'] !== 'function') throw new Error('handler not registered yet')
    })

    // unmount and expect the fake socket close() to be called
    unmount()
    expect(fakeSocket.close).toHaveBeenCalled()
  })
})
