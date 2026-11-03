import { useState } from 'react'
import { importCharacter } from '../api/importCharacter'

export function useImportCharacter(onImported) {
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState(null)
  const run = async () => {
    setImporting(true)
    setError(null)
    try {
      const result = await importCharacter()
      if (result) await onImported()
    } catch (e) { setError(e.message) }
    finally { setImporting(false) }
  }
  return { importing, error, importCharacter: run }
}
