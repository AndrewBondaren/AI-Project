import { API_URL } from '@/shared/config/api'

export async function getWorlds() {
  const res = await fetch(`${API_URL}/worlds`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// The caller (editor preview or ordinary import) owns the user context.
// Preview returns diagnostics only; apply always sends a fresh ordinary import.
export async function importWorld({ file, path, level = 'skeleton', validateOnly = false, decisions, previewToken }) {
  const form = new FormData()
  if (file) form.append('file', file)
  if (path) form.append('path', path)
  if (decisions) form.append('decisions', JSON.stringify(decisions))
  if (previewToken) form.append('preview_token', previewToken)
  const query = new URLSearchParams({ level })
  if (validateOnly) query.set('validate_only', 'true')
  const res = await fetch(`${API_URL}/worlds/import?${query}`, { method: 'POST', body: form })
  const data = await res.json()
  if (!res.ok || data.rolled_back) {
    const error = new Error(data.rolled_back
      ? `Импорт мира отменён: ${data.rollback_reason ?? 'ошибка записи'}`
      : describeError(data, res.status))
    error.issues = data.detail
    error.status = res.status
    error.outcome = data
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

function describeError(data, status) {
  if (typeof data.detail === 'string') return data.detail
  if (Array.isArray(data.detail)) {
    const messages = data.detail.map(issue => issue.message ?? issue.msg).filter(Boolean)
    if (messages.length) return messages.join('; ')
  }
  return `HTTP ${status}`
}

export async function importCharacter({ file, path }) {
  const form = new FormData()
  if (file) form.append('file', file)
  if (path) form.append('path', path)
  const res = await fetch(`${API_URL}/characters/import`, { method: 'POST', body: form })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(describeError(data, res.status))
  }
  return res.json()
}

export async function deleteCharacter(characterUid) {
  const res = await fetch(`${API_URL}/characters/${encodeURIComponent(characterUid)}`, { method: 'DELETE' })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(describeError(data, res.status))
  }
}
