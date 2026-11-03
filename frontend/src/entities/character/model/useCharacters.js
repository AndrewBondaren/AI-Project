import { useCallback, useEffect, useState } from 'react'
import { listCharacters } from '../api/characterApi'

export function useCharacters() {
  const [characters, setCharacters] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try { setCharacters(await listCharacters()) }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { refresh() }, [refresh])
  return { characters, loading, error, refresh }
}
