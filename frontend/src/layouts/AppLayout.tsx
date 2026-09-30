import type { ReactNode } from 'react'
import Sidebar from '../components/Sidebar'
import HelpButton from '../components/HelpButton'

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div style={{
      display: 'flex', height: '100vh', width: '100%', overflow: 'hidden',
      background: 'linear-gradient(135deg, #eef4ff 0%, #f5f9ff 40%, #f0f6ff 70%, #eaf3ff 100%)',
      position: 'relative',
    }}>
      {/* Ambient orbs */}
      <div style={{
        position: 'fixed', top: '-15vh', right: '-10vw',
        width: '50vw', height: '50vw', borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(0,136,255,0.08) 0%, transparent 70%)',
        pointerEvents: 'none', zIndex: 0,
      }} />
      <div style={{
        position: 'fixed', bottom: '-10vh', left: '10vw',
        width: '35vw', height: '35vw', borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(0,68,168,0.06) 0%, transparent 70%)',
        pointerEvents: 'none', zIndex: 0,
      }} />

      <Sidebar />
      <main className="app-main" style={{
        flex: 1, minHeight: 0, overflowY: 'auto', minWidth: 0, position: 'relative', zIndex: 1,
        padding: 'clamp(20px, 2.5vh, 32px) clamp(20px, 2.5vw, 36px)',
      }}>
        <div style={{ maxWidth: 1440, margin: '0 auto', width: '100%' }}>
          {children}
        </div>
      </main>
      <HelpButton />
    </div>
  )
}
