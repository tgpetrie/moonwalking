import { describe, it, expect, beforeEach, vi } from 'vitest'
import { fetchWithSWR, API_ENDPOINTS, getApiBaseUrl } from '../src/lib/api'

// Basic mocking of fetch
beforeEach(() => {
  global.fetch = vi.fn()
  sessionStorage.clear()
})

describe('api layer', () => {
  it('returns base url and fetches data', async () => {
    // mock fetch response
    const dummy = { items: [1,2,3] }
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => dummy })

    const url = API_ENDPOINTS.t3m
    const data = await fetchWithSWR(url)
    expect(data).toEqual(dummy)
    // Should be cached now
    const cached = sessionStorage.getItem(`cache:${url}`)
    expect(cached).toBeTruthy()
  })

  it('exposes API base', () => {
    const base = getApiBaseUrl()
    expect(typeof base).toBe('string')
  })
})
