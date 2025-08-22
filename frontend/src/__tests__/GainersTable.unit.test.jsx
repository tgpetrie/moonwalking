import { describe, it, expect } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { vi } from 'vitest'

// Mock fetchWithSWR so the component receives controlled payloads
vi.mock('../lib/api.js', async () => {
  const actual = await vi.importActual('../lib/api.js')
  return {
    ...actual,
    fetchWithSWR: vi.fn()
  }
})

// Use the canonical 3-min gainers TSX implementation for tests
import GainersTable from '../components/Gainers3Min.tsx'
import { fetchWithSWR } from '../lib/api.js'

describe('Gainers normalization + dedupe', () => {
  it('reads varied backend shapes and dedupes by largest absolute change', async () => {
    // craft payload with duplicate symbols in different casings and different change fields
    const payload = [
      { symbol: 'BTC-USD', price: 100, change: 2 },
      { ticker: 'btc-usd', price: 101, change: 6 },
      { symbol: 'ETH-USD', price: 2, change: 3 },
      { symbol: 'eth-usd', price: 2.1, change: 1 }
    ]

    fetchWithSWR.mockResolvedValueOnce(payload)

    render(<GainersTable />)

    // expect rows to render using deduped results: BTC keeps change 6, ETH keeps change 3
    await waitFor(() => {
      expect(screen.getByText('BTC-USD')).toBeTruthy()
      expect(screen.getByText('ETH-USD')).toBeTruthy()
    })

    // percent cells contain +6.00% and +3.00% (component formats to 2 decimals)
    expect(screen.getByText('+6.00%') || screen.queryByText('+6.00%')).toBeTruthy()
    expect(screen.getByText('+3.00%') || screen.queryByText('+3.00%')).toBeTruthy()
  })
})
