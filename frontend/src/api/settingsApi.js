import { API_URL } from '@/config'

export async function getSettings() {
  const res = await fetch(`${API_URL}/chat/settings`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function updateSettings(settings) {
  const res = await fetch(`${API_URL}/chat/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
