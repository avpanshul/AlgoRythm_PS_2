import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { GlassCard } from '../components/glass/GlassCard'
import { api } from '../api/client'
import { Settings, Shield, Eye, Check } from 'lucide-react'

const TIMEZONES = ['UTC', 'America/New_York', 'Europe/London', 'Asia/Kolkata', 'Asia/Tokyo']
const SESSION_OPTIONS = [
  { label: '15 Minutes', minutes: 15 },
  { label: '30 Minutes', minutes: 30 },
  { label: '1 Hour', minutes: 60 },
  { label: '4 Hours', minutes: 240 },
  { label: '8 Hours (default)', minutes: 480 },
]

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState('general')
  const { data: settings, refetch } = useQuery({ queryKey: ['settings'], queryFn: api.getSettings })

  const [platformName, setPlatformName] = useState('')
  const [timezone, setTimezone] = useState('UTC')
  const [sessionMinutes, setSessionMinutes] = useState(480)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (settings) {
      setPlatformName(settings.platform_name || '')
      setTimezone(settings.default_timezone || 'UTC')
      setSessionMinutes(settings.session_timeout_minutes || 480)
    }
  }, [settings])

  const inputStyle = {
    padding: '10px 14px', borderRadius: 8, border: '1px solid rgba(0,68,168,0.2)',
    background: 'rgba(255,255,255,0.8)', fontSize: 14, color: '#0a0e27', width: '100%', maxWidth: 400,
    outline: 'none', transition: 'border-color 0.2s'
  }

  const tabs = [
    { id: 'general', label: 'General', icon: Settings },
    { id: 'security', label: 'Security', icon: Shield },
    { id: 'privacy', label: 'Privacy & Retention', icon: Eye },
  ]

  const save = () => {
    setSaving(true)
    setError(null)
    setSaved(false)
    const values: Record<string, any> = activeTab === 'general'
      ? { platform_name: platformName, default_timezone: timezone }
      : activeTab === 'security'
        ? { session_timeout_minutes: sessionMinutes }
        : {}
    if (Object.keys(values).length === 0) return
    api.updateSettings(values)
      .then(() => {
        setSaved(true)
        refetch()
        setTimeout(() => setSaved(false), 2000)
      })
      .catch((e: any) => setError(e?.response?.data?.detail || e?.message || 'Could not save these settings.'))
      .finally(() => setSaving(false))
  }

  return (
    <div className="page-container">
      <header style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 56, fontWeight: 700, color: '#0044A8', marginBottom: 8 }}>Platform Settings</h1>
        <p style={{ color: '#5b6382', fontSize: 15 }}>Manage global preferences and system configuration.</p>
      </header>

      <div style={{ display: 'flex', gap: 32 }}>
        <div style={{ width: 240, flexShrink: 0 }}>
          <nav style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {tabs.map(t => (
              <button
                key={t.id}
                onClick={() => { setActiveTab(t.id); setSaved(false); setError(null) }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '12px 16px', borderRadius: 12, border: 'none',
                  background: activeTab === t.id ? 'rgba(0,68,168,0.1)' : 'transparent',
                  color: activeTab === t.id ? '#0044A8' : '#5b6382',
                  fontWeight: activeTab === t.id ? 600 : 500,
                  fontSize: 14, cursor: 'pointer', textAlign: 'left',
                  transition: 'all 0.2s',
                }}
              >
                <t.icon size={18} />
                {t.label}
              </button>
            ))}
          </nav>
        </div>

        <div style={{ flex: 1 }}>
          <GlassCard>
            <h2 style={{ fontSize: 20, fontWeight: 600, color: '#0a0e27', marginBottom: 24, borderBottom: '1px solid rgba(0,68,168,0.1)', paddingBottom: 16 }}>
              {tabs.find(t => t.id === activeTab)?.label} Configuration
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              {activeTab === 'general' && (
                <>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <label style={{ fontSize: 14, fontWeight: 600, color: '#0a0e27' }}>Platform Name</label>
                    <input type="text" value={platformName} onChange={e => setPlatformName(e.target.value)} style={inputStyle} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <label style={{ fontSize: 14, fontWeight: 600, color: '#0a0e27' }}>Default Timezone</label>
                    <select value={timezone} onChange={e => setTimezone(e.target.value)} style={inputStyle}>
                      {TIMEZONES.map(tz => <option key={tz} value={tz}>{tz}</option>)}
                    </select>
                  </div>
                </>
              )}

              {activeTab === 'security' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <label style={{ fontSize: 14, fontWeight: 600, color: '#0a0e27' }}>Session Timeout</label>
                  <select value={sessionMinutes} onChange={e => setSessionMinutes(Number(e.target.value))} style={inputStyle}>
                    {SESSION_OPTIONS.map(opt => <option key={opt.minutes} value={opt.minutes}>{opt.label}</option>)}
                  </select>
                  <p style={{ fontSize: 12, color: '#8999b0', marginTop: 4 }}>
                    Applies to tokens issued by future logins -- doesn't retroactively shorten an already-issued session.
                  </p>
                </div>
              )}

              {activeTab === 'privacy' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  <p style={{ fontSize: 14, color: '#5b6382' }}>
                    Redaction and retention are already real, per-source/per-policy features with their own dedicated pages --
                    not a single global toggle, since different sources legitimately need different rules.
                  </p>
                  <div style={{ display: 'flex', gap: 12 }}>
                    <Link to="/privacy" style={{ padding: '10px 20px', borderRadius: 8, background: 'rgba(0,68,168,0.08)', color: '#0044A8', fontWeight: 600, fontSize: 13, textDecoration: 'none' }}>
                      Privacy Policies →
                    </Link>
                    <Link to="/raw" style={{ padding: '10px 20px', borderRadius: 8, background: 'rgba(0,68,168,0.08)', color: '#0044A8', fontWeight: 600, fontSize: 13, textDecoration: 'none' }}>
                      Retention Policies →
                    </Link>
                  </div>
                </div>
              )}

              {activeTab !== 'privacy' && (
                <div style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
                  <button onClick={save} disabled={saving} style={{
                    background: 'linear-gradient(135deg, #0044A8, #0088FF)', color: '#fff', border: 'none',
                    padding: '10px 24px', borderRadius: 8, fontWeight: 600, fontSize: 14, cursor: saving ? 'default' : 'pointer',
                    opacity: saving ? 0.7 : 1, boxShadow: '0 4px 12px rgba(0,68,168,0.2)'
                  }}>{saving ? 'Saving…' : 'Save Changes'}</button>
                  {saved && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#057a55', fontSize: 13, fontWeight: 600 }}>
                      <Check size={14} /> Saved
                    </span>
                  )}
                  {error && <span style={{ color: '#c81e1e', fontSize: 13 }}>{error}</span>}
                </div>
              )}
            </div>
          </GlassCard>
        </div>
      </div>
    </div>
  )
}
