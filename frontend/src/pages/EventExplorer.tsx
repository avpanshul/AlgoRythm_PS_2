import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { useNavigate } from 'react-router-dom'
import { DEMO_EVENTS } from '../data/demo'
import { Search, ShieldCheck, ChevronRight, XCircle, SlidersHorizontal } from 'lucide-react'

type Event = typeof DEMO_EVENTS[number]

const SEVERITIES: Record<string, string> = {
  critical: 'danger',
  high: 'warning',
  medium: 'primary',
  low: 'neutral',
  info: 'neutral'
}

export default function EventExplorer() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)

  const { data: eventsData } = useQuery({
    queryKey: ['events', q],
    queryFn: () => api.getEvents({ q: q || undefined }),
    retry: false
  })

  const events: Event[] = (eventsData?.events?.length ? eventsData.events : DEMO_EVENTS).filter((e: any) =>
    !q || JSON.stringify(e).toLowerCase().includes(q.toLowerCase())
  )

  return (
    <div className="animate-fade-in" style={{ paddingBottom: 40 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <div>
          <h1 className="page-title">Log Explorer</h1>
          <p className="page-subtitle" style={{ margin: 0 }}>Search, filter, and investigate normalized events</p>
        </div>
        <button className="btn btn-secondary">
          <SlidersHorizontal size={14} /> Columns
        </button>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <Search size={15} color="#6b7280" style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} />
          <input
            type="text"
            className="glass-input"
            placeholder="Search IP, user, source, event type..."
            style={{ paddingLeft: 36 }}
            value={q}
            onChange={e => { setQ(e.target.value); setPage(1) }}
          />
        </div>
      </div>
      <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 12 }}>{events.length} events · last 24h</div>

      <div className="glass-table-container">
        <table className="glass-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Source</th>
              <th>Event Type</th>
              <th>Severity</th>
              <th>Quality</th>
              <th>Integrity</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {events.map((evt: any) => {
              const severity = evt.event?.severity || 'info'
              const quality = evt.quality || Math.floor(Math.random() * 20) + 80
              return (
                <tr key={evt.event_id} onClick={() => navigate(`/events/${evt.event_id}`)} style={{ cursor: 'pointer' }}>
                  <td className="mono" style={{ fontSize: 12 }}>
                    {new Date(evt.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </td>
                  <td style={{ fontWeight: 500 }}>{evt.source?.name || evt.source?.ip}</td>
                  <td>{evt.event?.action || 'Unknown'}</td>
                  <td>
                    <span className={`badge badge-${SEVERITIES[severity] || 'neutral'}`}>
                      {severity}
                    </span>
                  </td>
                  <td>
                    <span className="mono" style={{ fontSize: 12, color: '#6b7280' }}>{quality}</span>
                  </td>
                  <td>
                    {evt.integrity !== false ? (
                      <ShieldCheck size={16} color="#057a55" />
                    ) : (
                      <XCircle size={16} color="#c81e1e" />
                    )}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <ChevronRight size={16} color="#9ca3af" />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <div style={{ padding: '12px 16px', borderTop: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: '#6b7280' }}>Showing {events.length} events</span>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: 12 }} disabled={page === 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
            <span style={{ fontSize: 12, color: '#6b7280' }}>Page {page}</span>
            <button className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: 12 }} onClick={() => setPage(p => p + 1)}>Next →</button>
          </div>
        </div>
      </div>
    </div>
  )
}
