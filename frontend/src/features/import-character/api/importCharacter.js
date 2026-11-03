import { importCharacterFromPath } from '@/shared/api/worldApi'
import { openFile } from '@/shared/lib/fileSystem'

export async function importCharacter() {
  const path = await openFile({ filters: [{ name: 'JSON', extensions: ['json'] }] })
  if (!path) return null
  return importCharacterFromPath(path)
}
