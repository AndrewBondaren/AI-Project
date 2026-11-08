import { useParams } from 'react-router-dom'
import ChatPanel from '@/widgets/chat-panel/ui/ChatPanel'

export default function SessionPage() {
  const { sessionId } = useParams()
  return sessionId ? <ChatPanel key={sessionId} sessionId={sessionId} /> : null
}
