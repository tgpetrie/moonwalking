import React from 'react'
import { renderHook } from '@testing-library/react'
import { waitFor } from '@testing-library/react'
import { useEndpoint } from '../lib/api'

describe('useEndpoint', () => {
  it('reads snapshot from sessionStorage when present', async () => {
    const fake = { data: [1, 2, 3] }
    sessionStorage.setItem('cache:/api/test', JSON.stringify({ data: fake }))
    const { result } = renderHook(() => useEndpoint('/api/test'))
    // wait for hook to settle and return snapshot data
    await waitFor(() => expect(result.current[0]).toEqual(fake))
    expect(result.current[1]).toBe(false)
  })
})
