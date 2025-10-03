import axios from 'axios'
import type { DataBundle, PumpDump, SentimentRow } from '@moonwalking/core'

export const createClient = (baseURL: string, deviceId: string) => {
  const client = axios.create({ baseURL })
  client.interceptors.request.use((cfg) => {
    cfg.headers = { ...(cfg.headers || {}), 'X-Device-Id': deviceId }
    return cfg
  })
  return {
    async getBundle(): Promise<DataBundle> {
      const { data } = await client.get('/data')
      return data
    },
    async getSignals(): Promise<PumpDump[]> {
      const { data } = await client.get('/signals/pumpdump')
      return data
    },
    async getSentiment(symbols: string[]): Promise<SentimentRow[]> {
      const { data } = await client.get('/sentiment', { params: { symbols: symbols.join(',') } })
      return data
    },
    async addWatch(symbol: string) {
      return (await client.post('/watchlist/add', { symbol })).data
    },
    async removeWatch(symbol: string) {
      return (await client.post('/watchlist/remove', { symbol })).data
    },
    async getWatch() {
      return (await client.get('/watchlist')).data
    },
  }
}
