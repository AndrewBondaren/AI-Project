import { useCharacters } from '@/entities/character/model/useCharacters'
import { useImportCharacter } from '@/features/import-character/model/useImportCharacter'
import CharacterSelectStep from '@/features/create-session/ui/CharacterSelectStep'

export default function CharacterSelectPage() {
  const { characters, loading, error: loadError, refresh } = useCharacters()
  const { importing, error: importError, importCharacter } = useImportCharacter(refresh)
  return <CharacterSelectStep characters={characters} loading={loading} error={importError ?? loadError} importing={importing} onImport={importCharacter} />
}
