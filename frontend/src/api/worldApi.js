import { API_URL } from '@/config'

export async function getWorlds() {
  const res = await fetch(`${API_URL}/worlds`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// The caller (editor preview or ordinary import) owns the user context.
// Preview returns diagnostics only; apply always sends a fresh ordinary import.
export async function importWorld({ file, path, level = 'skeleton', validateOnly = false }) {
  const form = new FormData()
  if (file) form.append('file', file)
  if (path) form.append('path', path)
  const query = new URLSearchParams({ level })
  if (validateOnly) query.set('validate_only', 'true')
  const res = await fetch(`${API_URL}/worlds/import?${query}`, { method: 'POST', body: form })
  const data = await res.json()
  if (!res.ok) {
    const error = new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${res.status}`)
    error.issues = data.detail
    throw error
  }
  return data
}

export async function getCharacters() {
  const res = await fetch(`${API_URL}/characters`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function copyCharacter(characterUid) {
  const res = await fetch(`${API_URL}/characters/${characterUid}/copy`, { method: 'POST' })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail ?? `HTTP ${res.status}`)
  }
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
