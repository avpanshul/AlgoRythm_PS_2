import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { GlassCard } from '../components/glass/GlassCard'
import { Search, ShieldAlert, Globe, Plus, X } from 'lucide-react'

export default function Evidence() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [checkResult, setCheckResult] = useState<any>(null)
  const [checkError, setCheckError] = useState<string | null>(null)
  const [showAdd, setShowAdd] = useState(false)

  // Real, no-fabricated-threat-intel backend: this project deliberately
  // ships zero seeded indicators (inventing IOCs would itself be exactly
  // the kind of fabricated security data this project refuses to do), so
  // an honestly-empty list here is the correct, expected state until a
  // real indicator is added (via the form below, or the API).
  const { data: indicators } = useQuery({ queryKey: ['threat-indicators'], queryFn: () => api.getThreatIndicators(), retry: false })
  const indicatorList = Array.isArray(indicators) ? indicators : []

  const runCheck = async () => {
    if (!search.trim()) return
    setCheckError(null)
    try {
      const result = await api.checkThreatIntel(search.trim())
      setCheckResult(result)
    } catch (e: any) {
      setCheckError(e?.response?.data?.detail || e?.message || 'Lookup failed.')
    }
  }

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <header style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 'clamp(40px, 4vw, 52px)', fontWeight: 800, color: '#0044A8', letterSpacing: '-0.03em', lineHeight: 1.1 }}>
            Threat Intelligence
          </h1>
          <p style={{ fontSize: 'clamp(12px, 0.85vw, 13px)', color: '#8999b0', marginTop: 3 }}>
            Real indicator lookups against this deployment's own indicator list -- no seeded/fabricated indicators, by design.
          </p>
        </div>
        <button onClick={() => setShowAdd(true)} style={{
          display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', borderRadius: 10,
          background: 'linear-gradient(135deg, #0044A8, #0088FF)', border: 'none',
          color: '#fff', fontWeight: 600, fontSize: 13, cursor: 'pointer', boxShadow: '0 4px 12px rgba(0,68,168,0.2)'
        }}>
          <Plus size={14} /> Add Indicator
        </button>
      </header>

      <GlassCard style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <Search size={18} color="#0044A8" />
        <input
          type="text"
          placeholder="Look up an IP, domain, or hash against real stored indicators..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && runCheck()}
          style={{ border: 'none', background: 'transparent', outline: 'none', fontSize: 15, flex: 1, color: '#0a0e27' }}
        />
        <button onClick={runCheck} style={{ padding: '8px 24px', borderRadius: 8, background: '#0044A8', color: '#fff', border: 'none', fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>Search IOC</button>
      </GlassCard>

      {checkError && (
        <div style={{ padding: '10px 16px', borderRadius: 10, background: 'rgba(200,30,30,0.08)', color: '#c81e1e', fontSize: 13 }}>
          {checkError}
        </div>
      )}

      {checkResult && (
        <GlassCard style={{ padding: 20 }}>
          <div style={{ fontSize: 13, color: checkResult.matched ? '#c81e1e' : '#057a55', fontWeight: 700 }}>
            {checkResult.matched ? 'Match found' : 'No match in stored indicators'}
          </div>
          {checkResult.matched && <pre style={{ fontSize: 11, marginTop: 8, color: '#5b6382' }}>{JSON.stringify(checkResult, null, 2)}</pre>}
        </GlassCard>
      )}

      <GlassCard style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid rgba(0,68,168,0.1)' }}>
          <h3 className="section-heading">Stored Indicators ({indicatorList.length})</h3>
        </div>
        {indicatorList.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <Globe size={28} color="#c0cde3" style={{ marginBottom: 8 }} />
            <p style={{ fontSize: 13, color: '#8999b0', fontWeight: 500 }}>No indicators stored yet.</p>
            <p style={{ fontSize: 11, color: '#b0bace', marginTop: 4 }}>This project ships with no seeded threat-intel data -- add real indicators via the API to populate this list.</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
            <thead>
              <tr style={{ background: 'rgba(0,68,168,0.03)', borderBottom: '1px solid rgba(0,68,168,0.1)', color: '#5b6382' }}>
                <th style={{ padding: '16px', fontWeight: 600 }}>Indicator</th>
                <th style={{ padding: '16px', fontWeight: 600 }}>Type</th>
                <th style={{ padding: '16px', fontWeight: 600 }}>Source</th>
                <th style={{ padding: '16px', fontWeight: 600 }}>Added</th>
              </tr>
            </thead>
            <tbody>
              {indicatorList.map((row: any) => (
                <tr key={row.id} style={{ borderBottom: '1px solid rgba(0,68,168,0.05)' }}>
                  <td style={{ padding: '16px', fontWeight: 600, color: '#0a0e27', fontFamily: 'monospace' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <ShieldAlert size={16} color="#c81e1e" /> {row.value}
                    </div>
                  </td>
                  <td style={{ padding: '16px', color: '#5b6382' }}>{row.type}</td>
                  <td style={{ padding: '16px', color: '#5b6382' }}>{row.source || '—'}</td>
                  <td style={{ padding: '16px', color: '#5b6382' }}>{row.created_at ? new Date(row.created_at).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </GlassCard>

      {showAdd && (
        <AddIndicatorModal
          onClose={() => setShowAdd(false)}
          onCreated={() => { setShowAdd(false); qc.invalidateQueries({ queryKey: ['threat-indicators'] }) }}
        />
      )}
    </div>
  )
}

function AddIndicatorModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [type, setType] = useState('ip')
  const [value, setValue] = useState('')
  const [threatType, setThreatType] = useState('')
  const [severity, setSeverity] = useState('medium')
  const [source, setSource] = useState('manual')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const submit = () => {
    if (!value.trim()) {
      setError('Indicator value is required.')
      return
    }
    setSubmitting(true)
    setError(null)
    api.createThreatIndicator({
      type, value: value.trim(), threat_type: threatType.trim() || undefined,
      severity, source: source.trim() || 'manual', description: description.trim() || undefined,
    })
      .then(onCreated)
      .catch((e: any) => setError(e?.response?.data?.detail || e?.message || 'Could not add this indicator.'))
      .finally(() => setSubmitting(false))
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,15,46,0.4)', backdropFilter: 'blur(8px)' }}>
      <div style={{ width: '90%', maxWidth: 460, background: '#fff', borderRadius: 16, padding: 28, position: 'relative', boxShadow: '0 16px 48px rgba(0,15,92,0.2)' }}>
        <button onClick={onClose} style={{ position: 'absolute', top: 16, right: 16, background: 'none', border: 'none', cursor: 'pointer' }}><X size={18} color="#8999b0" /></button>
        <h2 style={{ fontSize: 18, fontWeight: 800, color: '#0a0e27', marginBottom: 20 }}>Add Threat Indicator</h2>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', gap: 10 }}>
            <select className="glass-input" value={type} onChange={e => setType(e.target.value)} style={{ width: 120 }}>
              <option value="ip">IP</option>
              <option value="domain">Domain</option>
              <option value="hash">Hash</option>
              <option value="url">URL</option>
            </select>
            <input className="glass-input" value={value} onChange={e => setValue(e.target.value)} placeholder="Indicator value" style={{ flex: 1 }} />
          </div>
          <input className="glass-input" value={threatType} onChange={e => setThreatType(e.target.value)} placeholder="Threat type (e.g. malware, c2, phishing, scanner)" />
          <div style={{ display: 'flex', gap: 10 }}>
            <select className="glass-input" value={severity} onChange={e => setSeverity(e.target.value)} style={{ flex: 1 }}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
            <input className="glass-input" value={source} onChange={e => setSource(e.target.value)} placeholder="Source (e.g. manual, feed name)" style={{ flex: 1 }} />
          </div>
          <input className="glass-input" value={description} onChange={e => setDescription(e.target.value)} placeholder="Description (optional)" />

          {error && <div style={{ color: '#c81e1e', fontSize: 12 }}>{error}</div>}

          <button onClick={submit} disabled={submitting} className="btn-primary" style={{ justifyContent: 'center', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Plus size={14} /> {submitting ? 'Adding…' : 'Add Indicator'}
          </button>
        </div>
      </div>
    </div>
  )
}
