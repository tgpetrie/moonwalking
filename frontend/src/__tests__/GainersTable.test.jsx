import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'

// Mock the API helper used by the component (inline payload to avoid hoisting issues)
vi.mock('../lib/api', () => ({
  API_ENDPOINTS: { t3m: '/api/t3m' },
  fetchWithSWR: vi.fn().mockResolvedValue([
    { symbol: 'btc-usd', price: 100, change: 2 },
    { ticker: 'BTC-USD', price: 101, change: 6 },
    { symbol: 'ETH-USD', price: 2, change: 3 },
    { symbol: 'eth-usd', price: 2.1, change: 1 }
  ]),
}))

// Use the canonical 3-min gainers TSX implementation for tests
import GainersTable from '../components/Gainers3Min.tsx'

describe('GainersTable (http path)', () => {
  it('normalizes shapes and dedupes by largest absolute change (http-driven)', async () => {
    render(<GainersTable />)

    await waitFor(() => {
      expect(screen.getByText('BTC-USD')).toBeTruthy()
      expect(screen.getByText('ETH-USD')).toBeTruthy()
    })

    expect(screen.getByText('+6.00%') || screen.queryByText('+6.00%')).toBeTruthy()
    expect(screen.getByText('+3.00%') || screen.queryByText('+3.00%')).toBeTruthy()
  })
})