import { useFileImport } from '@/shared/lib/useFileImport'
import { pickAndImportCharacter } from '../api/importCharacter'

export function useImportCharacter(onImported: () => Promise<void>) {
  const { run, ...state } = useFileImport(pickAndImportCharacter, onImported)
  return { ...state, importCharacter: run }
}
