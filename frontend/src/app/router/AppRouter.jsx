import { Routes, Route } from 'react-router-dom'
import AppLayout from '@/app/AppLayout'
import HomePage from '@/pages/home/ui/HomePage'
import SessionPage from '@/pages/session/ui/SessionPage'
import WorldSelectStep from '@/features/create-session/ui/WorldSelectStep'
import CharacterSelectPage from '@/pages/session/ui/CharacterSelectPage'
import CreateSessionDialog from '@/features/create-session/ui/CreateSessionDialog'
import BackendSettingsPage from '@/pages/settings/ui/BackendSettingsPage'
import WorldSettingsPage from '@/pages/settings/ui/WorldSettingsPage'

export default function AppRouter() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<HomePage />} />
        <Route element={<CreateSessionDialog />}>
          <Route path="new" element={<WorldSelectStep />} />
          <Route path="new/:worldId" element={<CharacterSelectPage />} />
        </Route>
        <Route path="chat/:sessionId" element={<SessionPage />} />
        <Route path="settings/backend" element={<BackendSettingsPage />} />
        <Route path="settings/world" element={<WorldSettingsPage />} />
      </Route>
    </Routes>
  )
}
