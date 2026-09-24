import type { ReactNode } from 'react'
import Sidebar from '../components/Sidebar'

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div style={{ display: 'flex', minHeight: '100vh', width: '100%', background: '#ffffff' }}>
      <Sidebar />
      <main style={{ flex: 1, overflowY: 'auto', padding: '28px 32px', background: '#ffffff', minWidth: 0 }}>
        <div style={{ maxWidth: 1280, margin: '0 auto' }}>
          {children}
        </div>
      </main>
    </div>
  )
}
