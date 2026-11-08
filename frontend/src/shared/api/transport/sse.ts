import { NetworkError } from './http'

export async function* readSse<T>(body: ReadableStream<Uint8Array>, decode: (value: unknown) => T | undefined): AsyncGenerator<T> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let ended = false
  try {
    while (!ended) {
      const { value, done } = await reader.read().catch(error => { throw new NetworkError(error) })
      ended = done
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = ended ? '' : (lines.pop() ?? '')
      for (const line of lines) {
        if (!line.startsWith('data:')) continue
        let payload: unknown
        try { payload = JSON.parse(line.slice(5)) }
        catch { continue }
        const event = decode(payload)
        if (event !== undefined) yield event
      }
    }
  } finally {
    try {
      if (!ended) await reader.cancel().catch(() => {})
    } finally {
      reader.releaseLock()
    }
  }
}
