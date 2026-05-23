import { useCallback, useEffect, useState } from 'react'
import { listCharacters, importCharacter } from '../service'

export function useCharacters(worldId) {
  const [characters, setCharacters] = useState([])
  const [loading,    setLoading]    = useState(true)
  const [importing,  setImporting]  = useState(false)
  const [error,      setError]      = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setCharacters(await listCharacters(worldId))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [worldId])

  useEffect(() => { load() }, [load])

  const doImport = useCallback(async () => {
    setImporting(true)
    setError(null)
    try {
      const result = await importCharacter()
      if (result) await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setImporting(false)
    }
  }, [load])

  return { characters, loading, importing, error, importCharacter: doImport }
}
