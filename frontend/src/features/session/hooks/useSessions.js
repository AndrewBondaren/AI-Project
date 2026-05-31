import { useCallback, useEffect, useState } from 'react'
import { listSessions, deleteSession as deleteSessionService } from '../service'

export function useSessions() {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    listSessions()
      .then(setSessions)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const deleteSession = useCallback(async (id) => {
    await deleteSessionService(id)
    setSessions(prev => prev.filter(s => s.id !== id))
  }, [])

  return { sessions, loading, error, deleteSession }
}
