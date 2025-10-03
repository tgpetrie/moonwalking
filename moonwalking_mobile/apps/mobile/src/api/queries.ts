import { useQuery } from '@tanstack/react-query'
import client from './client'

export function useBundle() {
  return useQuery({
    queryKey: ['bundle'],
    queryFn: async () => (await client.get('/api/mobile/bundle')).data,
    refetchInterval: 15_000,
    staleTime: 10_000,
  })
}

export function useSignals(enabled: boolean) {
  return useQuery({
    enabled,
    queryKey: ['signals'],
    // Backend path is namespaced under /api; a Cloudflare function may also expose this.
    queryFn: async () => (await client.get('/api/signals/pumpdump')).data,
    refetchInterval: 10_000,
    staleTime: 8_000,
  })
}

export function useSentiment(symbols: string[], enabled: boolean) {
  return useQuery({
    enabled,
    queryKey: ['sentiment', symbols.sort().join(',')],
    queryFn: async () =>
      (await client.get('/api/sentiment', { params: { symbols: symbols.join(',') } })).data,
    refetchInterval: 60_000,
    staleTime: 30_000,
  })
}

export async function addWatch(symbol: string) {
  // Backend add is POST /api/watchlist with { symbol }
  return (await client.post('/api/watchlist', { symbol })).data
}
export async function removeWatch(symbol: string) {
  // Backend remove is DELETE /api/watchlist/:symbol
  return (await client.delete(`/api/watchlist/${symbol}`)).data
}
export async function getWatch() {
  // Backend returns a JSON array of symbols
  return (await client.get('/api/watchlist')).data
}
