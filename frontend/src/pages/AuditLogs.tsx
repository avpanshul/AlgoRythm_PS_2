import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, Download } from 'lucide-react'
import { api } from '../api/client'

export default function AuditLogs() {
  const [q, setQ] = useState('')

  const { data, isLoading, isError } = useQuery({
    queryKey: ['audit-logs', q],
    queryFn: () => api.getAuditLogs({ q: q || undefined, size: 100 }),
    retry: false,
  })

  const logs = data?.items || []

  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <div>
          <h1 className="page-title">System audit logs</h1>
          <p className="page-subtitle" style={{ margin: 0 }}>Record of user and system actions across the platform.</p>
        </div>
        <a className="btn btn-secondary" href={api.getExportUrl('csv')}>
          <Download size={14} /> Export CSV
        </a>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 400 }}>
          <Search size={15} color="#6b7280" style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)' }} />
          <input
            className="glass-input"
            placeholder="Search by user, action, or entity..."
            value={q}
            onChange={e => setQ(e.target.value)}
            style={{ paddingLeft: 36 }}
          />
        </div>
      </div>

      <div className="glass-table-container">
        <table className="glass-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>User / System Actor</th>
              <th>Action</th>
              <th>Entity</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((a: any) => (
              <tr key={a.id}>
                <td className="mono" style={{ fontSize: 12 }}>{a.timestamp ? new Date(a.timestamp).toLocaleString() : '—'}</td>
                <td style={{ fontWeight: 500 }}>{a.user}</td>
                <td><span className="badge badge-primary">{a.action}</span></td>
                <td style={{ fontSize: 12 }}>{a.entity_type}{a.entity_id ? `: ${a.entity_id}` : ''}</td>
                <td style={{ fontSize: 12, color: '#6b7280' }}>{a.reason || '—'}</td>
              </tr>
            ))}
            {isLoading && (
              <tr><td colSpan={5} style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>Loading…</td></tr>
            )}
            {isError && (
              <tr><td colSpan={5} style={{ textAlign: 'center', padding: 40, color: '#c81e1e' }}>This endpoint requires an authenticated session (no login UI is wired up yet).</td></tr>
            )}
            {!isLoading && !isError && logs.length === 0 && (
              <tr><td colSpan={5} style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>No audit log entries yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
