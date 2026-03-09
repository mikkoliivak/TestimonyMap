import { useState, useEffect, useCallback } from 'react'

export function useCenters() {
  const [centers, setCenters] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadCenters = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/centers')
      if (!res.ok) throw new Error('Failed to load data')
      const data = await res.json()
      setCenters(data)
      return data
    } catch (err) {
      setError(err.message)
      setCenters([])
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadCenters()
  }, [loadCenters])

  return { centers, loading, error, reload: loadCenters }
}
