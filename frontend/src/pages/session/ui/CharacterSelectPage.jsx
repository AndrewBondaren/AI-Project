import { useState } from 'react'
import { deleteCharacter } from '@/entities/character/api/characterApi'
import { useCharacters } from '@/entities/character/model/useCharacters'
import { useSessions } from '@/entities/session/model/useSessions'
import { useImportCharacter } from '@/features/import-character/model/useImportCharacter'
import CharacterSelectStep from '@/features/create-session/ui/CharacterSelectStep'

export default function CharacterSelectPage() {
  const { characters, loading, error: loadError, refresh } = useCharacters()
  const { importing, error: importError, importCharacter } = useImportCharacter(refresh)
  const { refresh: refreshSessions } = useSessions()
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState(null)

  async function handleDelete(character) {
    if (!window.confirm(`Удалить персонажа «${character.display_name}»? Это действие нельзя отменить.`)) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await deleteCharacter(character.character_uid)
      await Promise.all([refresh(), refreshSessions()])
    } catch (e) {
      setDeleteError(e.message)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <CharacterSelectStep
      characters={characters}
      loading={loading}
      error={deleteError ?? importError ?? loadError}
      importing={importing}
      deleting={deleting}
      onImport={() => {
        setDeleteError(null)
        return importCharacter()
      }}
      onDelete={handleDelete}
    />
  )
}
