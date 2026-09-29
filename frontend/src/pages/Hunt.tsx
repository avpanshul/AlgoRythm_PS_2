import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Plus, Trash2, Play, Crosshair } from 'lucide-react'
import { api } from '../api/client'
import { GlassCard } from '../components/glass/GlassCard'

export default function Hunt() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [showNew, setShowNew] = useState(false)
  const [name, setName] = useState('')
  const [q, setQ] = useState('')
  const [severity, setSeverity] = useState('')
  const [riskLevel, setRiskLevel] = useState('')
  const [results, setResults] = useState<{ id: string; events: any[]; total: number } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data: hunts, isError } = useQuery({ queryKey: ['hunts'], queryFn: () => api.getHunts(), retry: false })
  const list = Array.isArray(hunts) ? hunts : []

  const handleError = (e: any) => setError(e?.response?.data?.detail || e?.message || 'Request failed.')

  const saveQuery = () => {
    setError(null)
    const filter: Record<string, string> = {}
    if (q) filter.q = q
    if (severity) filter.severity = severity
    if (riskLevel) filter.risk_level = riskLevel
    api.createHunt({ name, filter }).then(() => {
      qc.invalidateQueries({ queryKey: ['hunts'] })
      setShowNew(false); setName(''); setQ(''); setSeverity(''); setRiskLevel('')
    }).catch(handleError)
  }

  const run = (id: string) => {
    setError(null)
    api.runHunt(id).then((res: any) => setResults({ id, events: res.events || [], total: res.total })).catch(handleError)
  }

  const remove = (id: string) => {
    api.deleteHunt(id).then(() => qc.invalidateQueries({ queryKey: ['hunts'] })).catch(handleError)
  }

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 'clamp(40px, 4vw, 52px)', fontWeight: 800, color: '#0044A8', letterSpacing: '-0.03em', lineHeight: 1.1 }}>Threat Hunting</h1>
          <p style={{ fontSize: 13, color: '#8999b0', marginTop: 3 }}>Saved queries you can re-run any time; every run is recorded in the tamper-evident audit log.</p>
        </div>
        <button onClick={() => setShowNew(v => !v)} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', borderRadius: 10, background: 'linear-gradient(135deg, #0044A8, #0088FF)', border: 'none', color: '#fff', fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>
          <Plus size={14} /> Save Query
        </button>
      </header>

      {error && <div style={{ fontSize: 12, color: '#c81e1e' }}>{error}</div>}

      {showNew && (
        <GlassCard style={{ padding: 20 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 12 }}>
            <input placeholder="Query name" value={name} onChange={e => setName(e.target.value)} style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid rgba(0,68,168,0.15)', fontSize: 13 }} />
            <input placeholder="Text search (IP, message)" value={q} onChange={e => setQ(e.target.value)} style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid rgba(0,68,168,0.15)', fontSize: 13 }} />
            <select value={severity} onChange={e => setSeverity(e.target.value)} style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid rgba(0,68,168,0.15)', fontSize: 13 }}>
              <option value="">Any severity</option>
              {['info', 'low', 'medium', 'high', 'critical'].map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <select value={riskLevel} onChange={e => setRiskLevel(e.target.value)} style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid rgba(0,68,168,0.15)', fontSize: 13 }}>
              <option value="">Any risk level</option>
              {['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <button onClick={saveQuery} disabled={!name} style={{ padding: '8px 20px', borderRadius: 8, background: '#0044A8', color: '#fff', border: 'none', fontWeight: 600, fontSize: 13, cursor: 'pointer', opacity: name ? 1 : 0.5 }}>Save</button>
        </GlassCard>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: results ? '1fr 1fr' : '1fr', gap: 20 }}>
        <GlassCard style={{ padding: 0, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
            <thead>
              <tr style={{ background: 'rgba(0,68,168,0.03)', borderBottom: '1px solid rgba(0,68,168,0.1)', color: '#5b6382' }}>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Name</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Filter</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Owner</th>
                <th style={{ padding: '12px 16px' }}></th>
              </tr>
            </thead>
            <tbody>
              {list.map((hq: any) => (
                <tr key={hq.id} style={{ borderBottom: '1px solid rgba(0,68,168,0.05)' }}>
                  <td style={{ padding: '14px 16px', fontWeight: 600, color: '#0a0e27' }}>{hq.name}</td>
                  <td className="mono" style={{ padding: '14px 16px', fontSize: 11, color: '#5b6382' }}>{JSON.stringify(hq.filter)}</td>
                  <td className="mono" style={{ padding: '14px 16px', fontSize: 12, color: '#5b6382' }}>{hq.owner || '—'}</td>
                  <td style={{ padding: '14px 16px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <button onClick={() => run(hq.id)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 4, color: '#0044A8' }}><Play size={14} /></button>
                    <button onClick={() => remove(hq.id)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 4, color: '#c81e1e' }}><Trash2 size={14} /></button>
                  </td>
                </tr>
              ))}
              {isError && <tr><td colSpan={4} style={{ textAlign: 'center', padding: 24, color: '#c81e1e' }}>Could not load saved queries.</td></tr>}
              {!isError && list.length === 0 && (
                <tr><td colSpan={4} style={{ textAlign: 'center', padding: 40 }}>
                  <Crosshair size={24} color="#c0cde3" style={{ marginBottom: 8 }} />
                  <div style={{ color: '#8999b0', fontSize: 13 }}>No saved queries yet.</div>
                </td></tr>
              )}
            </tbody>
          </table>
        </GlassCard>

        {results && (
          <GlassCard style={{ padding: 0, overflow: 'hidden' }}>
            <div className="section-heading" style={{ padding: '14px 16px', borderBottom: '1px solid rgba(0,68,168,0.1)' }}>
              Results ({results.total} total, showing up to 100)
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
              <thead>
                <tr style={{ background: 'rgba(0,68,168,0.03)', color: '#5b6382' }}>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>Time</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>Source</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>Risk</th>
                </tr>
              </thead>
              <tbody>
                {results.events.map((e: any) => (
                  <tr key={e.event_id} onClick={() => navigate(`/events/${e.event_id}`)} style={{ cursor: 'pointer', borderBottom: '1px solid rgba(0,68,168,0.05)' }}>
                    <td className="mono" style={{ padding: '12px 16px', fontSize: 11 }}>{e.timestamp ? new Date(e.timestamp).toLocaleString() : '—'}</td>
                    <td className="mono" style={{ padding: '12px 16px', fontSize: 11 }}>{e.source?.ip || '—'}</td>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: (e.risk?.level === 'CRITICAL' || e.risk?.level === 'HIGH') ? 'rgba(200,30,30,0.1)' : 'rgba(0,68,168,0.08)', color: (e.risk?.level === 'CRITICAL' || e.risk?.level === 'HIGH') ? '#c81e1e' : '#0044A8' }}>{e.risk?.score ?? '—'}</span>
                    </td>
                  </tr>
                ))}
                {results.events.length === 0 && <tr><td colSpan={3} style={{ textAlign: 'center', padding: 24, color: '#8999b0' }}>No matching events.</td></tr>}
              </tbody>
            </table>
          </GlassCard>
        )}
      </div>
    </div>
  )
}
