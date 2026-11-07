// Preserve the import contract, including validation-only previews and decisions.
import { importWorld } from '@/shared/api/worldApi'
import { openFile } from '@/shared/lib/fileSystem'

export { importWorld } from '@/shared/api/worldApi'

export async function pickAndImportWorld() {
  const source = await openFile({ filters: [{ name: 'Мир', extensions: ['json', 'wpack', 'zip'] }] })
  return source ? importWorld(source) : null
}
