import { useRef, useState } from 'react'

export function useFileImport(importFile, onImported) {
  const busy = useRef(false)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState(null)

  async function run() {
    if (busy.current) return
    busy.current = true
    setImporting(true)
    setError(null)
    try {
      if (await importFile()) await onImported()
    } catch (e) {
      setError(e.message)
    } finally {
      busy.current = false
      setImporting(false)
    }
  }

  return { run, importing, error }
}
