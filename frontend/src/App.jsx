import { BrowserRouter, Routes, Route } from 'react-router-dom'
import AppLayout from '@/layouts/AppLayout'
import SessionPage from '@/features/session/ui/SessionPage'
import WorldSelectPage from '@/features/session/ui/WorldSelectPage'
import CharacterSelectPage from '@/features/session/ui/CharacterSelectPage'
import ChatPage from '@/features/chat/ui/ChatPage'
import BackendSettingsPage from '@/features/settings/backend/ui/BackendSettingsPage'
import WorldSettingsPage from '@/features/settings/world/ui/WorldSettingsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<SessionPage />} />
          <Route path="new" element={<WorldSelectPage />} />
          <Route path="new/:worldId" element={<CharacterSelectPage />} />
          <Route path="chat/:sessionId" element={<ChatPage />} />
          <Route path="settings/backend" element={<BackendSettingsPage />} />
          <Route path="settings/world"   element={<WorldSettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
