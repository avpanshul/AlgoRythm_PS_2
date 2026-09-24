import { Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Search, Database, FileCode2,
  ShieldCheck, Activity, HardDrive, Settings,
  Network, User, Shield
} from 'lucide-react'

const MAIN_NAV = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { path: '/events', label: 'Log Explorer', icon: Search },
  { path: '/sources', label: 'Data Sources', icon: Database },
  { path: '/parsers', label: 'Parser Lab', icon: FileCode2 },
  { path: '/replay', label: 'Integrity & Replay', icon: ShieldCheck },
  { path: '/data-quality', label: 'Analytics & Alerts', icon: Activity },
  { path: '/raw', label: 'Storage', icon: HardDrive },
  { path: '/users', label: 'Administration', icon: Settings },
]

const INTEGRATIONS = [
  { path: '/integrations', label: 'SIEM / Data Lake', icon: Network },
  { path: '/health', label: 'System Health', icon: Activity },
]

export default function Sidebar() {
  const loc = useLocation()
  const isActive = (path: string, exact?: boolean) =>
    exact ? loc.pathname === path : loc.pathname === path || loc.pathname.startsWith(path + '/')

  return (
    <aside style={{
      width: 240,
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      background: '#ffffff',
      borderRight: '1px solid #e5e7eb',
      minHeight: '100vh',
      position: 'sticky',
      top: 0,
      height: '100vh',
    }}>
      <div style={{ padding: '18px 16px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: '1px solid #f3f4f6' }}>
        <div style={{
          width: 32, height: 32, borderRadius: 6,
          background: '#111928',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Shield size={17} color="white" />
        </div>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#111928' }}>ULPF</div>
          <div style={{ fontSize: 11, color: '#6b7280' }}>Log Pre-processing</div>
        </div>
      </div>

      <nav style={{ flex: 1, overflowY: 'auto', padding: '12px 10px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {MAIN_NAV.map(({ path, label, icon: Icon, exact }) => {
          const active = isActive(path, exact)
          return (
            <Link key={path} to={path} className={`nav-item ${active ? 'active' : ''}`}>
              <Icon size={16} strokeWidth={active ? 2.5 : 2} />
              {label}
            </Link>
          )
        })}

        <div style={{ marginTop: 16, marginBottom: 6, padding: '0 10px', fontSize: 11, fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          System
        </div>

        {INTEGRATIONS.map(({ path, label, icon: Icon }) => {
          const active = isActive(path)
          return (
            <Link key={path} to={path} className={`nav-item ${active ? 'active' : ''}`}>
              <Icon size={16} strokeWidth={active ? 2.5 : 2} />
              {label}
            </Link>
          )
        })}
      </nav>

      <div style={{ padding: '14px 16px', borderTop: '1px solid #f3f4f6' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
          <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#f3f4f6', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <User size={14} color="#6b7280" />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#111928' }}>Admin User</div>
            <div style={{ fontSize: 11, color: '#6b7280' }}>SOC Analyst</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#057a55' }} />
            <span style={{ fontSize: 11, color: '#6b7280' }}>System Healthy</span>
          </div>
          <span style={{ fontSize: 11, color: '#9ca3af' }}>v1.0.0</span>
        </div>
      </div>
    </aside>
  )
}
