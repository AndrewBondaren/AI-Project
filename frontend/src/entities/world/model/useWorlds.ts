import type { WorldSummary } from '@/shared/types/records'
import { errorMessage } from '@/shared/lib/errorMessage'
import { useCallback, useEffect, useState } from 'react'
import { listWorlds } from '../api/worldApi'

export function useWorlds() {
  const [worlds,  setWorlds]  = useState<WorldSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setWorlds(await listWorlds())
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [])
  useEffect(() => { refresh() }, [refresh])

  return { worlds, loading, error, refresh }
}
