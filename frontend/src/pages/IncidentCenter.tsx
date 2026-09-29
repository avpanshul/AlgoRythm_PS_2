import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
import { api } from '../api/client'

const sevBadge = (s: string) => s === 'CRITICAL' ? 'danger' : s === 'HIGH' ? 'warning' : 'neutral'

/** There is no incident-management model in the backend (no status/assignee
 * workflow exists) -- incidents here are computed live by grouping high/critical
 * risk events by (source, action), which is the same real data Alerts.tsx uses.
 * No status or assignee is shown because neither is tracked anywhere; showing
 * one would mean fabricating it. */
function groupIntoIncidents(events: any[]) {
  const groups = new Map<string, any>()
  for (const e of events) {
    const key = `${e.source_id || e.source?.name || 'unknown'}::${e.event?.action || e.action || 'unknown'}`
    const existing = groups.get(key)
    if (existing) {
      existing.eventCount += 1
      existing.maxScore = Math.max(existing.maxScore, e.risk?.score ?? e.risk_score ?? 0)
      if (e.timestamp > existing.latest) existing.latest = e.timestamp
    } else {
      groups.set(key, {
        id: key,
        title: e.event?.action || e.action || 'Unknown activity',
        source: e.source_id || e.source?.name || 'unknown',
        severity: e.risk?.level || e.risk_level || 'MEDIUM',
        eventCount: 1,
        maxScore: e.risk?.score ?? e.risk_score ?? 0,
        latest: e.timestamp,
      })
    }
  }
  return Array.from(groups.values()).sort((a, b) => b.maxScore - a.maxScore)
}

export default function IncidentCenter() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')

  const { data: criticalEvents, isLoading: cLoading, isError: cError } = useQuery({
    queryKey: ['events', 'critical'],
    queryFn: () => api.getEvents({ risk_level: 'CRITICAL', size: 100 }),
  })
  const { data: highEvents, isLoading: hLoading } = useQuery({
    queryKey: ['events', 'high'],
    queryFn: () => api.getEvents({ risk_level: 'HIGH', size: 100 }),
  })

  const allEvents = [...(criticalEvents?.events || []), ...(highEvents?.events || [])]
  const incidents = groupIntoIncidents(allEvents)
  const filtered = incidents.filter(i => (i.title + i.source).toLowerCase().includes(q.toLowerCase()))

  const counts = {
    critical: incidents.filter(i => i.severity === 'CRITICAL').length,
    high: incidents.filter(i => i.severity === 'HIGH').length,
    other: incidents.filter(i => i.severity !== 'CRITICAL' && i.severity !== 'HIGH').length,
  }

  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <h1 className="page-title">Incident center</h1>
        <p className="page-subtitle" style={{ margin: 0 }}>
          High/critical-risk events grouped by source + action -- computed live, not a tracked incident
          workflow (no status/assignment exists yet, so none is shown here).
        </p>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 400 }}>
          <Search size={15} color="#6b7280" style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)' }} />
          <input className="glass-input" placeholder="Search incidents..." value={q} onChange={e => setQ(e.target.value)} style={{ paddingLeft: 36 }} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 220px', gap: 20, alignItems: 'flex-start' }}>
        <div className="glass-table-container">
          <table className="glass-table">
            <thead>
              <tr><th>Incident</th><th>Source</th><th>Severity</th><th>Events</th><th>Max score</th></tr>
            </thead>
            <tbody>
              {filtered.map(inc => (
                <tr key={inc.id} style={{ cursor: 'pointer' }} onClick={() => navigate(inc.source && inc.source !== 'unknown' ? `/sources/${encodeURIComponent(inc.source)}` : '/sources')}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{inc.title}</div>
                    <div className="mono" style={{ fontSize: 11, color: '#6b7280' }}>{inc.latest ? new Date(inc.latest).toLocaleString() : '—'}</div>
                  </td>
                  <td style={{ fontSize: 12 }}>{inc.source}</td>
                  <td><span className={`badge badge-${sevBadge(inc.severity)}`}>{inc.severity}</span></td>
                  <td className="mono" style={{ fontSize: 12 }}>{inc.eventCount}</td>
                  <td className="mono" style={{ fontSize: 13, fontWeight: 700 }}>{inc.maxScore}</td>
                </tr>
              ))}
              {(cLoading || hLoading) && <tr><td colSpan={5} style={{ textAlign: 'center', padding: 24, color: '#6b7280' }}>Loading…</td></tr>}
              {cError && <tr><td colSpan={5} style={{ textAlign: 'center', padding: 24, color: '#c81e1e' }}>Could not reach the backend.</td></tr>}
              {!cLoading && !hLoading && !cError && filtered.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', padding: 24, color: '#6b7280' }}>No high/critical-risk incidents.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
          <h3 className="section-heading" style={{ marginBottom: 12 }}>Summary</h3>
          <table className="glass-table">
            <tbody>
              <tr><td style={{ fontSize: 13, color: '#6b7280' }}>Critical</td><td className="mono" style={{ textAlign: 'right', fontWeight: 700 }}>{counts.critical}</td></tr>
              <tr><td style={{ fontSize: 13, color: '#6b7280' }}>High</td><td className="mono" style={{ textAlign: 'right', fontWeight: 700 }}>{counts.high}</td></tr>
              <tr><td style={{ fontSize: 13, color: '#6b7280' }}>Other</td><td className="mono" style={{ textAlign: 'right', fontWeight: 700 }}>{counts.other}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
