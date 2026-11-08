import type { ChatMessage } from '@/shared/types/chat'
import type { CharacterSummary, SessionSummary, WorldSummary } from '@/shared/types/records'

export const demoWorlds: WorldSummary[] = [
  { id: 'demo-forest', name: 'Сумеречный лес' },
  { id: 'demo-city', name: 'Северная гавань' },
]

export const demoCharacters: CharacterSummary[] = [
  { id: 'demo-ranger', name: 'Аэлин', characterClass: 'Следопыт' },
  { id: 'demo-mage', name: 'Мира', characterClass: 'Маг' },
]

export const demoSession: SessionSummary = {
  id: 'demo-session',
  worldId: 'demo-forest',
  worldName: 'Сумеречный лес',
  characterId: 'demo-ranger',
  characterName: 'Аэлин',
  lastActiveAt: new Date().toISOString(),
}

export const demoHistory: ChatMessage[] = [
  { role: 'user', text: 'Я осматриваю опушку.' },
  { role: 'bot', text: 'На опушке тропа раздваивается. Слева слышен ручей, справа видна старая башня.' },
  {
    role: 'bot',
    data: {
      type: 'selectLocation',
      children: [
        { id: 'demo-stream', name: 'Ручей' },
        { id: 'demo-tower', name: 'Старая башня' },
      ],
    },
  },
]
