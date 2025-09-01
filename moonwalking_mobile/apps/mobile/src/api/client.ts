import axios from 'axios'
import Constants from 'expo-constants'
import * as Crypto from 'expo-crypto'

let deviceIdCache: string | null = null
async function getDeviceId() {
  if (deviceIdCache) return deviceIdCache
  const rnd = Math.random().toString(36).slice(2)
  deviceIdCache = await Crypto.digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    rnd + Date.now()
  )
  return deviceIdCache
}

const baseURL = Constants?.expoConfig?.extra?.API_BASE || 'http://127.0.0.1:8787'
const client = axios.create({ baseURL })

client.interceptors.request.use(async (cfg) => {
  const id = await getDeviceId()
  cfg.headers = { ...(cfg.headers || {}), 'X-Device-Id': id }
  return cfg
})

export default client
