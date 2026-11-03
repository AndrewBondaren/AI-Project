import { createContext, useCallback, useEffect, useMemo, useState } from 'react'
import { listSessions, deleteSession as removeSession } from '@/shared/api/sessionApi'

export const SessionContext = createContext(null)

export function SessionProvider({ children }) {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try { setSessions(await listSessions()) }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { refresh() }, [refresh])
  const deleteSession = useCallback(async id => {
    await removeSession(id)
    setSessions(prev => prev.filter(s => s.id !== id))
  }, [])
  const value = useMemo(() => ({ sessions, loading, error, refresh, deleteSession }), [sessions, loading, error, refresh, deleteSession])
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
