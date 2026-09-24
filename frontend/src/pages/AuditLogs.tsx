import { useState } from 'react'
import { Search, Download } from 'lucide-react'

const MOCK_AUDIT = [
  { id: 'aud-1', time: '2026-09-23T12:15:33Z', user: 'SOC Analyst (John Doe)', action: 'Viewed Event', resource: 'Event: evt-001', ip: '10.0.50.12' },
  { id: 'aud-2', time: '2026-09-23T12:05:10Z', user: 'System (Analytics Engine)', action: 'Incident Created', resource: 'Incident: INC-092-A', ip: 'internal' },
  { id: 'aud-3', time: '2026-09-23T11:45:00Z', user: 'Security Admin (Jane Smith)', action: 'Updated Policy', resource: 'Privacy Policy: Default Analytics', ip: '10.0.50.5' },
  { id: 'aud-4', time: '2026-09-23T10:30:15Z', user: 'Parser Developer (Alice)', action: 'Published Parser', resource: 'Parser: nginx-access-parser v2.0.1', ip: '10.0.50.22' },
  { id: 'aud-5', time: '2026-09-22T09:00:00Z', user: 'System (Replay Engine)', action: 'Replay Job Started', resource: 'Job: job-9012', ip: 'internal' },
]

export default function AuditLogs() {
  const [q, setQ] = useState('')

  const filtered = MOCK_AUDIT.filter(a =>
    a.user.toLowerCase().includes(q.toLowerCase()) ||
    a.action.toLowerCase().includes(q.toLowerCase()) ||
    a.resource.toLowerCase().includes(q.toLowerCase())
  )

  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <div>
          <h1 className="page-title">System audit logs <span className="badge badge-neutral" style={{ marginLeft: 8, verticalAlign: 'middle' }}>Compliance active</span></h1>
          <p className="page-subtitle" style={{ margin: 0 }}>Immutable record of user and system actions (NTRO auditing standards).</p>
        </div>
        <button className="btn btn-secondary">
          <Download size={14} /> Export CSV
        </button>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 400 }}>
          <Search size={15} color="#6b7280" style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)' }} />
          <input
            className="glass-input"
            placeholder="Search by user, action, or resource..."
            value={q}
            onChange={e => setQ(e.target.value)}
            style={{ paddingLeft: 36 }}
          />
        </div>
        <select className="glass-input" style={{ width: 150 }}>
          <option>Last 24 Hours</option>
          <option>Last 7 Days</option>
          <option>Last 30 Days</option>
        </select>
        <select className="glass-input" style={{ width: 160 }}>
          <option>All Action Types</option>
          <option>Viewed</option>
          <option>Updated</option>
          <option>Created</option>
        </select>
      </div>

      <div className="glass-table-container">
        <table className="glass-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>User / System Actor</th>
              <th>Action</th>
              <th>Resource</th>
              <th>IP Address</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(a => (
              <tr key={a.id}>
                <td className="mono" style={{ fontSize: 12 }}>{new Date(a.time).toLocaleString()}</td>
                <td style={{ fontWeight: 500 }}>{a.user}</td>
                <td><span className="badge badge-primary">{a.action}</span></td>
                <td style={{ fontSize: 12 }}>{a.resource}</td>
                <td className="mono" style={{ fontSize: 11, color: '#6b7280' }}>{a.ip}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={5} style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>No audit logs match your search.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
