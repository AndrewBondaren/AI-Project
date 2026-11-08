import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import AppSidebar from '@/widgets/app-sidebar/ui/AppSidebar'
import SessionHeader from '@/widgets/session-header/ui/SessionHeader'

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth >= 768)
  return (
    <div className="flex h-dvh overflow-hidden">
      {sidebarOpen && <AppSidebar />}
      <main className="flex min-w-0 flex-1 flex-col">
        <SessionHeader sidebarOpen={sidebarOpen} onToggleSidebar={() => setSidebarOpen(v => !v)} />
        <div className="min-h-0 flex-1 overflow-auto"><Outlet /></div>
      </main>
    </div>
  )
}
