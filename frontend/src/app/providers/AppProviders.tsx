import type { ReactNode } from 'react'
import { StrictMode } from 'react'
import { BrowserRouter } from 'react-router-dom'
import { SessionProvider } from '@/entities/session/model/SessionProvider'

export default function AppProviders({ children }: { children: ReactNode }) {
  return (
    <StrictMode>
      <BrowserRouter>
        <SessionProvider>{children}</SessionProvider>
      </BrowserRouter>
    </StrictMode>
  )
}
