import { API_URL } from '@/config'

export async function getWorlds() {
  const res = await fetch(`${API_URL}/worlds`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getCharacters(worldUid) {
  const params = new URLSearchParams({ world_uid: worldUid })
  const res = await fetch(`${API_URL}/characters?${params}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function importCharacterFromPath(filePath) {
  const form = new FormData()
  form.append('path', filePath)
  const res = await fetch(`${API_URL}/characters/import`, { method: 'POST', body: form })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}
