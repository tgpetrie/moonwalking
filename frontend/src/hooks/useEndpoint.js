import { useEffect, useState } from 'react'
import { fetchJSON } from '../lib/api'

export default function useEndpoint(url, opts = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let aborted = false
    let timer
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const json = await fetchJSON(url)
        if (!aborted) setData(json)
      } catch (e) {
        if (!aborted) setError(e)
      } finally {
        if (!aborted) setLoading(false)
      }
    }
    load()
    if (opts.pollMs) {
      timer = setInterval(load, opts.pollMs)
    }
    return () => {
      aborted = true
      if (timer) clearInterval(timer)
    }
  }, [url])

  return { data, loading, error }
}
