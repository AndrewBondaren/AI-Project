import { useWorlds } from '@/entities/world/model/useWorlds'
import WorldSelectStep from '@/features/create-session/ui/WorldSelectStep'
import { pickAndImportWorld } from '@/features/import-world/api/importWorld'
import { useFileImport } from '@/shared/lib/useFileImport'

export default function WorldSelectPage() {
  const { worlds, loading, error, refresh } = useWorlds()
  const { importing, error: importError, run } = useFileImport(pickAndImportWorld, refresh)
  return <WorldSelectStep worlds={worlds} loading={loading} error={error} actionError={importError} importing={importing} onImport={run} onRetry={refresh} />
}
