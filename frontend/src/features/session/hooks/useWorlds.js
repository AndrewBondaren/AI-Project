import { useEffect, useState } from 'react'
import { listWorlds } from '../service'

export function useWorlds() {
  const [worlds,  setWorlds]  = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    listWorlds()
      .then(setWorlds)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return { worlds, loading, error }
}
