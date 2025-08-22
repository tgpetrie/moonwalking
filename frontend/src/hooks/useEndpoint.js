// Lightweight polling hook for REST endpoints.
// Usage: const { data, loading, error, refresh } = useEndpoint(API_ENDPOINTS.gainersTable, { pollMs: 15000 })
import { useEffect, useRef, useState } from 'react'
import { fetchJSON as fetchData } from '../lib/api'

export default function useEndpoint(endpoint, opts = {}) {
  const { pollMs = 0, fetchOptions = {} } = opts
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(Boolean(endpoint))
  const timerRef = useRef(null)
  const mounted = useRef(true)

  const load = async () => {
    if (!endpoint) return
    try {
      setLoading(true)
      const res = await fetchData(endpoint, fetchOptions)
      if (!mounted.current) return
      setData(res)
      setError(null)
    } catch (e) {
      if (!mounted.current) return
      setError(e)
    } finally {
      if (mounted.current) setLoading(false)
    }
  }

  useEffect(() => {
    mounted.current = true
    load()

    if (pollMs && pollMs > 0) {
      timerRef.current = setInterval(load, pollMs)
    }
    return () => {
      mounted.current = false
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint, pollMs])

  return { data, error, loading, refresh: load }
}