
import React from 'react'
import { render, waitFor } from '@testing-library/react'
import { vi, test, expect, beforeEach, afterEach } from 'vitest'

function createMockSocket() {
  const handlers = {}
  return {
    __handlers: handlers,
    on: (ev, cb) => { handlers[ev] = cb },
    removeAllListeners: vi.fn(() => { Object.keys(handlers).forEach(k => delete handlers[k]) }),
    close: vi.fn(),
  }
}

beforeEach(() => {
  vi.resetModules()
  sessionStorage.clear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

test('handles tables:update and persists + notifies', async () => {
  const mockSocket = createMockSocket()

  const shareTables = vi.fn()
  const shareAlerts = vi.fn()
  const busEmit = vi.fn()

  // mock socket.io-client to return our mock socket (use doMock so mockSocket exists)
  vi.doMock('socket.io-client', () => ({ io: () => mockSocket }))
  vi.doMock('../lib/api', () => ({
    getApiBaseUrl: () => 'http://localhost:5000',
    bus: { emit: busEmit },
    shareTables,
    shareAlerts,
  }))

  const { WebSocketProvider, useWebSocketData } = await import('./websocketcontext.jsx')

  function Consumer() {
    const ctx = useWebSocketData()
    return <div data-testid="tables">{JSON.stringify(ctx.tables)}</div>
  }

  const { getByTestId } = render(
    <WebSocketProvider>
      <Consumer />
    </WebSocketProvider>
  )

  // initial render: empty object or cached value
  const el = getByTestId('tables')
  expect(el).toBeTruthy()

  // trigger a tables:update from the mock socket
  const payload = { t3m: [{ symbol: 'BTC', price: 100, delta_3m: 0.05 }] }
  // simulate server sending event
  mockSocket.__handlers['tables:update']?.(payload)

  // wait for provider to process update and re-render
  await waitFor(() => {
    const stored = JSON.parse(sessionStorage.getItem('tables:last') || '{}')
    expect(stored).toEqual(payload)
    expect(shareTables).toHaveBeenCalledWith(payload)
    expect(busEmit).toHaveBeenCalledWith('tables:update', payload)

    const parsed = JSON.parse(getByTestId('tables').textContent || '{}')
    expect(parsed).toEqual(payload)
  })
})

test('closes socket on unmount', async () => {
  const mockSocket = createMockSocket()
  vi.doMock('socket.io-client', () => ({ io: () => mockSocket }))
  vi.doMock('../lib/api', () => ({
    getApiBaseUrl: () => 'http://localhost:5000',
    bus: { emit: () => {} },
    shareTables: () => {},
    shareAlerts: () => {},
  }))

  const { WebSocketProvider, useWebSocketData } = await import('./websocketcontext.jsx')
  function Consumer() { const ctx = useWebSocketData(); return <div /> }

  const { unmount } = render(
    <WebSocketProvider>
      <Consumer />
    </WebSocketProvider>
  )

  unmount()
  expect(mockSocket.close).toHaveBeenCalled()
})

