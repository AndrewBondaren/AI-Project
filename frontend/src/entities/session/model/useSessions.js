import { useContext } from 'react'
import { SessionContext } from './SessionProvider'

export function useSessions() {
  const context = useContext(SessionContext)
  if (!context) throw new Error('useSessions requires SessionProvider')
  return context
}
