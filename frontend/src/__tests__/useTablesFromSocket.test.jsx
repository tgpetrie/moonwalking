import React from 'react'
import { act, render } from '@testing-library/react'
import { WebSocketProvider, useWebSocketData } from '../context/websocketcontext'
import { bus } from '../lib/api'

function Consumer() {
  const { tables } = useWebSocketData()
  return <div data-testid="count">{Array.isArray(tables?.t3m) ? tables.t3m.length : 0}</div>
}

describe('WebSocketProvider', () => {
  beforeEach(() => sessionStorage.clear())

  it('reads initial snapshot from sessionStorage and updates on bus', () => {
    sessionStorage.setItem('tables:last', JSON.stringify({ t3m: [{ symbol: 'BTC' }] }))
    const { getByTestId } = render(
      <WebSocketProvider>
        <Consumer />
      </WebSocketProvider>
    )

    expect(getByTestId('count').textContent).toBe('1')

    act(() => {
      bus.emit('tables:update', { t3m: [{ symbol: 'ETH' }, { symbol: 'BTC' }] })
    })

    expect(getByTestId('count').textContent).toBe('2')
  })
})
