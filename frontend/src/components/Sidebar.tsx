import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Database, FileCode2,
  ShieldCheck, Activity, HardDrive, Settings,
  Network, User, Shield, Building2, Siren, FileCheck2,
  LogOut, ChevronRight, Layers,
  ClipboardList, Share2, Route as RouteIcon, Crosshair,
  AlertOctagon, Menu, X,
} from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { clearToken } from '../auth/authStore'

const SIDEBAR_WIDTH_KEY = 'ulpf_sidebar_width'
const MIN_WIDTH = 200
const MAX_WIDTH = 420

const MAIN_NAV = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/sources', label: 'Data Sources', icon: Database },
  { path: '/parsers', label: 'Parser Lab', icon: FileCode2 },
  { path: '/replay', label: 'Integrity & Replay', icon: ShieldCheck },
  { path: '/alerts', label: 'Analytics & Alerts', icon: Activity },
  { path: '/cases', label: 'Incident Cases', icon: ClipboardList },
  { path: '/graph', label: 'Entity Behavior & Graph', icon: Share2 },
  { path: '/attack-path', label: 'Attack Path', icon: RouteIcon },
  { path: '/hunt', label: 'Threat Hunting', icon: Crosshair },
  { path: '/dlq', label: 'Failed Events / DLQ', icon: AlertOctagon },
  { path: '/raw', label: 'Storage', icon: HardDrive },
]
const GENERAL_NAV = [
  { path: '/users', label: 'Administration', icon: User },
  { path: '/integrations', label: 'SIEM / Data Lake', icon: Network },
  { path: '/evidence', label: 'Threat Intelligence', icon: Shield },
  { path: '/supervisory', label: 'Multi-CSE Supervisory', icon: Building2 },
  { path: '/settings', label: 'Settings', icon: Settings },
]

export default function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const [hoveredPath, setHoveredPath] = useState<string | null>(null)
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: api.getCurrentUser, retry: false, staleTime: 5 * 60 * 1000 })

  // Mobile off-canvas nav -- below the CSS breakpoint (see .app-sidebar in
  // index.css), the sidebar is fixed + translated off-screen by default;
  // this just toggles the class that slides it in, plus a backdrop. Above
  // the breakpoint this state is simply never read (the CSS media query
  // itself does nothing without it).
  const [mobileOpen, setMobileOpen] = useState(false)
  useEffect(() => { setMobileOpen(false) }, [location.pathname])

  // Resizable sidebar: no inline width until the user actually drags, so
  // the real CSS media queries on .app-sidebar (index.css) control the
  // default/min/max at each breakpoint. Once dragged, the chosen width is
  // set inline and persisted -- min-width/max-width from the CSS class
  // still clamp it at the current breakpoint even after that.
  const [width, setWidth] = useState<number | null>(() => {
    try {
      const saved = Number(localStorage.getItem(SIDEBAR_WIDTH_KEY))
      return saved >= MIN_WIDTH && saved <= MAX_WIDTH ? saved : null
    } catch {
      return null
    }
  })
  const [dragging, setDragging] = useState(false)
  const widthRef = useRef(width)
  widthRef.current = width

  useEffect(() => {
    if (!dragging) return
    const onMove = (e: PointerEvent) => {
      const next = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, e.clientX))
      widthRef.current = next
      setWidth(next)
    }
    const onUp = () => {
      setDragging(false)
      if (widthRef.current != null) {
        try { localStorage.setItem(SIDEBAR_WIDTH_KEY, String(widthRef.current)) } catch { /* ignore */ }
      }
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
  }, [dragging])

  const logout = () => {
    clearToken()
    navigate('/', { replace: true })
  }

  const NavLink = ({ path, label, Icon }: { path: string; label: string; Icon: any }) => {
    const isActive = location.pathname === path || location.pathname.startsWith(path + '/')
    const isHovered = hoveredPath === path

    return (
      <Link
        to={path}
        onMouseEnter={() => setHoveredPath(path)}
        onMouseLeave={() => setHoveredPath(null)}
        style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 12px', borderRadius: 12, textDecoration: 'none',
          fontSize: 'clamp(16px, 1.2vw, 18px)', fontWeight: isActive ? 600 : 500,
          position: 'relative', overflow: 'hidden',
          transition: 'all 0.2s cubic-bezier(0.25,1,0.5,1)',
          background: isActive
            ? 'rgba(0,68,168,0.1)'
            : isHovered ? 'rgba(0,68,168,0.05)' : 'transparent',
          color: isActive ? '#0044A8' : isHovered ? '#0066CC' : '#5b6382',
          border: isActive ? '1px solid rgba(0,68,168,0.15)' : '1px solid transparent',
          backdropFilter: isActive ? 'blur(8px)' : 'none',
        }}
      >
        {/* Glass highlight on active */}
        {isActive && (
          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0, height: '50%',
            background: 'linear-gradient(180deg, rgba(255,255,255,0.3) 0%, transparent 100%)',
            borderRadius: 'inherit', pointerEvents: 'none',
          }} />
        )}
        <Icon
          size={20}
          style={{
            flexShrink: 0,
            transition: 'transform 0.2s ease',
            transform: isHovered && !isActive ? 'scale(1.1)' : 'scale(1)',
          }}
        />
        <span style={{ flex: 1 }}>{label}</span>
        {isActive && (
          <ChevronRight size={12} style={{ opacity: 0.5 }} />
        )}
        {/* Active left accent */}
        {isActive && (
          <div style={{
            position: 'absolute', left: 0, top: '20%', bottom: '20%',
            width: 3, borderRadius: '0 3px 3px 0',
            background: 'linear-gradient(180deg, #0044A8, #0088FF)',
          }} />
        )}
      </Link>
    )
  }

  return (
    <>
      {/* Mobile hamburger -- fixed, only shown under the CSS breakpoint
          (see .mobile-menu-toggle in index.css); on desktop it's display:none
          so this renders but is invisible/inert there. */}
      <button
        className="mobile-menu-toggle"
        onClick={() => setMobileOpen(o => !o)}
        aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
        style={{
          position: 'fixed', top: 14, left: 14, zIndex: 300,
          width: 40, height: 40, borderRadius: 10, border: '1px solid rgba(0,68,168,0.15)',
          background: 'rgba(248,252,255,0.95)', backdropFilter: 'blur(12px)',
          display: 'none', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 2px 12px rgba(0,68,168,0.12)', cursor: 'pointer', color: '#0044A8',
        }}
      >
        {mobileOpen ? <X size={20} /> : <Menu size={20} />}
      </button>
      {/* Backdrop, mobile-only, closes the drawer on tap-outside */}
      {mobileOpen && (
        <div
          className="sidebar-mobile-backdrop"
          onClick={() => setMobileOpen(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,15,46,0.4)', zIndex: 99 }}
        />
      )}
      <aside
        className={`app-sidebar${mobileOpen ? ' mobile-open' : ''}`}
        style={{
          ...(width != null ? { width } : {}),
          display: 'flex',
          flexDirection: 'column',
          background: 'rgba(248,252,255,0.85)',
          backdropFilter: 'blur(32px) saturate(1.8)',
          WebkitBackdropFilter: 'blur(32px) saturate(1.8)',
          borderRight: '1px solid rgba(0,68,168,0.1)',
          boxShadow: '4px 0 24px rgba(0,68,168,0.04), 1px 0 0 rgba(255,255,255,0.8) inset',
          overflow: 'hidden',
          flexShrink: 0,
        }}
      >
      {/* Top gloss */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: '40%',
        background: 'linear-gradient(180deg, rgba(255,255,255,0.4) 0%, transparent 100%)',
        pointerEvents: 'none',
      }} />

      {/* Drag-to-resize handle, vertically centered on the right edge */}
      <div
        className={`sidebar-resize-handle${dragging ? ' dragging' : ''}`}
        onPointerDown={(e) => { e.preventDefault(); setDragging(true) }}
        title="Drag to resize"
      />

      {/* Logo */}
      <div style={{
        padding: 'clamp(16px, 1.5vw, 22px) clamp(14px, 1.2vw, 20px)',
        borderBottom: '1px solid rgba(0,68,168,0.08)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, alignItems: 'flex-start' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <img src="/sanket-icon.png" alt="" style={{ height: 26, width: 'auto', objectFit: 'contain', display: 'block', flexShrink: 0, filter: 'saturate(1.5) contrast(1.25)' }} />
            <span style={{ fontSize: 20, fontWeight: 800, color: '#0044A8', letterSpacing: '-0.02em' }}>Sanket</span>
          </div>
          <div style={{ fontSize: 11, color: '#8999b0', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', marginLeft: 2 }}>
            ULPF Platform
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: 'clamp(8px, 0.8vh, 12px) clamp(8px, 0.8vw, 12px)' }}>
        <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#8999b0', padding: '8px 12px 4px' }}>
          MENU
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {MAIN_NAV.map(({ path, label, icon: Icon }) => (
            <NavLink key={path} path={path} label={label} Icon={Icon} />
          ))}
        </div>

        <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#8999b0', padding: '16px 12px 4px' }}>
          GENERAL
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {GENERAL_NAV.map(({ path, label, icon: Icon }) => (
            <NavLink key={path} path={path} label={label} Icon={Icon} />
          ))}
        </div>
      </nav>

      {/* Bottom User */}
      <div style={{
        padding: 'clamp(10px, 1vh, 14px) clamp(8px, 0.8vw, 12px)',
        borderTop: '1px solid rgba(0,68,168,0.08)',
        flexShrink: 0,
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '8px 10px', borderRadius: 12,
          background: 'rgba(0,68,168,0.04)',
          border: '1px solid rgba(0,68,168,0.06)',
        }}>
          <div style={{
            width: 30, height: 30, borderRadius: 8, flexShrink: 0,
            background: 'linear-gradient(135deg, #0044A8, #0088FF)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 12, fontWeight: 700, color: '#fff',
            boxShadow: '0 2px 8px rgba(0,68,168,0.25)',
          }}>
            {(me?.name || '?')[0].toUpperCase()}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#0a0e27', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {me?.name || 'Loading…'}
            </div>
            <div style={{ fontSize: 10, color: '#8999b0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {me?.email || ''}
            </div>
          </div>
          <LogOut size={14} onClick={logout} style={{ color: '#8999b0', flexShrink: 0, cursor: 'pointer' }} />
        </div>
      </div>
      </aside>
    </>
  )
}
