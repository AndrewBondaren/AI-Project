import type { ReactNode } from 'react'
import type { SessionSummary } from '@/shared/types/records'
import { errorMessage } from '@/shared/lib/errorMessage'
import { createContext, useCallback, useEffect, useMemo, useState } from 'react'
import { listSessions, deleteSession as removeSession } from '@/shared/api/sessionApi'

interface SessionState {
  sessions: SessionSummary[]
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
  deleteSession: (id: string) => Promise<void>
}

export const SessionContext = createContext<SessionState | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try { setSessions(await listSessions()) }
    catch (e) { setError(errorMessage(e)) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { refresh() }, [refresh])
  const deleteSession = useCallback(async (id: string) => {
    await removeSession(id)
    setSessions(prev => prev.filter(s => s.id !== id))
  }, [])
  const value = useMemo(() => ({ sessions, loading, error, refresh, deleteSession }), [sessions, loading, error, refresh, deleteSession])
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
