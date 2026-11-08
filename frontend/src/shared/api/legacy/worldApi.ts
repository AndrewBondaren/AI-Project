import type { CharacterSummary, WorldSummary } from './records'
import type { FileSource } from '@/shared/types/files'
import { request } from '../transport/http'

type WorldImportOptions = FileSource & {
  level?: 'registry' | 'skeleton'
  validateOnly?: boolean
  decisions?: unknown
  previewToken?: string
}

interface ApiErrorBody {
  detail?: string | { message?: string; msg?: string }[]
}

interface WorldImportOutcome extends ApiErrorBody {
  rolled_back?: boolean
  rollback_reason?: string
}

export async function getWorlds(): Promise<WorldSummary[]> {
  const res = await request(`/worlds`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// The caller (editor preview or ordinary import) owns the user context.
// Preview returns diagnostics only; apply always sends a fresh ordinary import.
export async function importWorld({ file, path, level = 'skeleton', validateOnly = false, decisions, previewToken }: WorldImportOptions): Promise<unknown> {
  const form = new FormData()
  if (file) form.append('file', file)
  if (path) form.append('path', path)
  if (decisions) form.append('decisions', JSON.stringify(decisions))
  if (previewToken) form.append('preview_token', previewToken)
  const query = new URLSearchParams({ level })
  if (validateOnly) query.set('validate_only', 'true')
  const res = await request(`/worlds/import?${query}`, { method: 'POST', body: form })
  const data: WorldImportOutcome = await res.json().catch(error => {
    if (res.ok) throw error
    return {}
  })
  if (!res.ok || data.rolled_back) {
    const error = Object.assign(new Error(data.rolled_back
      ? `Импорт мира отменён: ${data.rollback_reason ?? 'ошибка записи'}`
      : describeError(data, res.status)), {
      issues: data.detail,
      status: res.status,
      outcome: data,
    })
    throw error
  }
  return data
}

export async function getCharacters(): Promise<CharacterSummary[]> {
  const res = await request(`/characters`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function copyCharacter(characterUid: string): Promise<{ character_uid: string }> {
  const res = await request(`/characters/${characterUid}/copy`, { method: 'POST' })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

function describeError(data: ApiErrorBody, status: number) {
  if (typeof data.detail === 'string') return data.detail
  if (Array.isArray(data.detail)) {
    const messages = data.detail.map(issue => issue.message ?? issue.msg).filter(Boolean)
    if (messages.length) return messages.join('; ')
  }
  return `HTTP ${status}`
}

export async function importCharacter({ file, path }: FileSource): Promise<{ character_uid: string }> {
  const form = new FormData()
  if (file) form.append('file', file)
  if (path) form.append('path', path)
  const res = await request(`/characters/import`, { method: 'POST', body: form })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(describeError(data, res.status))
  }
  return res.json()
}

export async function deleteCharacter(characterUid: string) {
  const res = await request(`/characters/${encodeURIComponent(characterUid)}`, { method: 'DELETE' })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(describeError(data, res.status))
  }
}
