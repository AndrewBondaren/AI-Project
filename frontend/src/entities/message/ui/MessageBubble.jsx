import Icon from '@/shared/ui/Icon'

const labels = { user: 'Вы', bot: 'Мастер подземелья', system: 'Система', pending: 'Вы (прервано)' }

export default function MessageBubble({ role, children }) {
  const isUser = role === 'user' || role === 'pending'
  const isSystem = role === 'system'
  return (
    <li className={`relative flex max-w-full flex-col gap-1 md:max-w-3/4 ${isSystem ? 'self-center' : isUser ? 'self-end pr-14' : 'self-start pl-14'}`}>
      {!isSystem && <Icon name={isUser ? 'alien' : 'masterAvatar'} size={40} className={`absolute top-0 rounded-lg border border-line bg-accent/7 p-1.5 ${isUser ? 'right-0' : 'left-0'}`} />}
      <span className={`text-xs font-semibold tracking-wider text-muted uppercase ${isUser ? 'text-right' : ''}`}>{labels[role] ?? role}</span>
      <div className={`rounded-lg border border-white/8 border-l-2 border-l-accent/45 bg-raised px-4 py-3 leading-relaxed whitespace-pre-wrap break-words ${isSystem ? 'text-xs text-faint italic' : ''}`}>
        {children}
      </div>
    </li>
  )
}
