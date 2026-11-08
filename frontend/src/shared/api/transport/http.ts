import { API_URL } from '@/shared/config/api'

export class NetworkError extends Error {
  constructor(cause?: unknown) {
    super('Ошибка сети. Проверьте подключение и попробуйте снова.', { cause })
    this.name = 'NetworkError'
  }
}

export async function request(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`${API_URL.replace(/\/$/, '')}${path}`, init)
  } catch (error) {
    if (init?.signal?.aborted) throw error
    throw new NetworkError(error)
  }
}
