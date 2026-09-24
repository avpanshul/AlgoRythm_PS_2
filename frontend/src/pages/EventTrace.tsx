import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { EventTrace } from '../types'
import { Loader2 } from 'lucide-react'

export default function EventTrace() {
  const [eventId, setEventId] = useState('')
  const [searchId, setSearchId] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['trace', searchId],
    queryFn: () => api.getEventTrace(searchId!) as Promise<EventTrace>,
    enabled: !!searchId,
  })

  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <h1 className="page-title">Event trace / provenance</h1>
        <p className="page-subtitle" style={{ margin: 0 }}>
          Trace any canonical event back to its original raw log with SHA-256 verification.
        </p>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        <input
          className="glass-input"
          placeholder="Enter Event ID (e.g. evt_abc123)"
          value={eventId}
          onChange={e => setEventId(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && setSearchId(eventId)}
        />
        <button className="btn-primary" onClick={() => setSearchId(eventId)} style={{ whiteSpace: 'nowrap' }}>
          Trace event
        </button>
      </div>

      {isLoading && (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Loader2 size={24} color="#6b7280" style={{ animation: 'spin 1s linear infinite', margin: '0 auto 12px' }} />
          <div style={{ color: '#6b7280', fontSize: 13 }}>Tracing event through pipeline stages…</div>
        </div>
      )}

      {error && (
        <div style={{ border: '1px solid #f8b4b4', borderLeft: '3px solid #c81e1e', borderRadius: 6, padding: 16, fontSize: 13, color: '#c81e1e' }}>
          Event not found or not yet processed.
        </div>
      )}

      {data && (
        <div>
          <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 12 }}>
            Tracing: <code className="mono" style={{ fontSize: 12 }}>{data.event_id}</code>
          </div>
          <div className="glass-table-container">
            <table className="glass-table">
              <thead>
                <tr><th style={{ width: 60 }}>Stage</th><th>Step</th><th>Detail</th></tr>
              </thead>
              <tbody>
                {data.trace.map((stage, i) => (
                  <tr key={stage.stage}>
                    <td className="mono" style={{ fontSize: 12, color: '#6b7280' }}>{i + 1}</td>
                    <td style={{ fontWeight: 600, fontSize: 13 }}>{stage.label}</td>
                    <td>
                      {stage.data ? (
                        <pre className="code-block" style={{ fontSize: 11 }}>{JSON.stringify(stage.data, null, 2)}</pre>
                      ) : (
                        <span style={{ fontSize: 12, color: '#9ca3af' }}>—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
