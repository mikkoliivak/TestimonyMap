import { useState, useEffect, useCallback } from 'react'

/**
 * Light-weight hook: fetches /api/centers/summary — name + coords + counts only.
 * Used by the map and the facility dropdown so the initial page load is small.
 */
export function useCenters() {
  const [centers, setCenters] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadCenters = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/centers/summary')
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

/**
 * Heavy hook: fetches /api/centers (full data, including every testimony body).
 * Only used by the Testimonies list page where we actually need the bodies.
 */
export function useCentersFull() {
  const [centers, setCenters] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch('/api/centers')
        if (!res.ok) throw new Error('Failed to load testimonies')
        const data = await res.json()
        if (!cancelled) setCenters(data)
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  return { centers, loading, error }
}
