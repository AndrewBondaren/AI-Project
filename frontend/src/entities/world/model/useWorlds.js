import { useCallback, useEffect, useState } from 'react'
import { listWorlds } from '../api/worldApi'

export function useWorlds() {
  const [worlds,  setWorlds]  = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setWorlds(await listWorlds())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])
  useEffect(() => { refresh() }, [refresh])

  return { worlds, loading, error, refresh }
}
