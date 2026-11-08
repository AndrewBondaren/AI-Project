import { importWorld } from '@/shared/api/worldApi'
import { openFile } from '@/shared/lib/fileSystem'

export async function pickAndImportWorld() {
  const source = await openFile({ filters: [{ name: 'Мир', extensions: ['json', 'wpack', 'zip'] }] })
  if (!source) return false
  await importWorld(source)
  return true
}
