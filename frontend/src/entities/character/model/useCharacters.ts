import type { CharacterSummary } from '@/shared/types/records'
import { errorMessage } from '@/shared/lib/errorMessage'
import { useCallback, useEffect, useState } from 'react'
import { listCharacters } from '../api/characterApi'

export function useCharacters() {
  const [characters, setCharacters] = useState<CharacterSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try { setCharacters(await listCharacters()) }
    catch (e) { setError(errorMessage(e)) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { refresh() }, [refresh])
  return { characters, loading, error, refresh }
}
