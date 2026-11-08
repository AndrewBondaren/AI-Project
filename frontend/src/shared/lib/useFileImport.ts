import { errorMessage } from '@/shared/lib/errorMessage'
import { useRef, useState } from 'react'

export function useFileImport(importFile: () => Promise<unknown>, onImported: () => Promise<void>) {
  const busy = useRef(false)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    if (busy.current) return
    busy.current = true
    setImporting(true)
    setError(null)
    try {
      if (await importFile()) await onImported()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      busy.current = false
      setImporting(false)
    }
  }

  return { run, importing, error }
}
