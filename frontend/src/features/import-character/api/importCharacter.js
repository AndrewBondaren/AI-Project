import { importCharacter } from '@/shared/api/worldApi'
import { openFile } from '@/shared/lib/fileSystem'

export async function pickAndImportCharacter() {
  const source = await openFile({ filters: [{ name: 'JSON', extensions: ['json'] }] })
  return source ? importCharacter(source) : null
}
