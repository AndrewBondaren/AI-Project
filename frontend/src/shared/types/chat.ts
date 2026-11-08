export interface ChatMessage {
  role: string
  text?: string
  displayText?: string
  data?: StructuredMessage
}

export interface StructuredMessage {
  type: string
  [key: string]: unknown
}

export interface LocationChoice {
  id: string
  name: string
  typeLabel?: string
  stateName?: string
  isHome?: boolean
}

export interface LocationSelectData extends StructuredMessage {
  type: 'selectLocation'
  parent?: { name: string } | null
  children: LocationChoice[]
}

export interface SceneReadyData extends StructuredMessage {
  type: 'sceneReady'
  location: { name: string; description?: string | null }
}

export type LocationSelectHandler = (uid: string, name: string) => void

export function isStructuredMessage(value: unknown): value is StructuredMessage {
  return typeof value === 'object' && value !== null && 'type' in value && typeof value.type === 'string'
}

export function isLocationSelection(data: StructuredMessage): data is LocationSelectData {
  return data.type === 'selectLocation' && Array.isArray(data.children)
}

export function isSceneReady(data: StructuredMessage): data is SceneReadyData {
  return data.type === 'sceneReady' && typeof data.location === 'object' && data.location !== null
}

export interface StreamStatus {
  phase: string
  taskType?: string
}

export type ChatEvent =
  | ({ type: 'status' } & StreamStatus)
  | { type: 'thinking'; elapsedMs: number }
  | { type: 'result'; response: unknown }
  | { type: 'cancelled' }
  | { type: 'error'; message: string }

