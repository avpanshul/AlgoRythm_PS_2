import { useState } from 'react'
import { Search } from 'lucide-react'

const MOCK_INCIDENTS = [
  { id: 'INC-092-A', title: 'Suspicious Lateral Movement / SSH Brute Force', severity: 'CRITICAL', status: 'Open', created: '15 mins ago', eventCount: 18, assignee: 'Unassigned', score: 95 },
  { id: 'INC-091-B', title: 'Multiple Failed API Auth Tokens', severity: 'HIGH', status: 'Investigating', created: '2 hours ago', eventCount: 45, assignee: 'John Doe', score: 78 },
  { id: 'INC-090-C', title: 'Unusual Outbound Data Transfer', severity: 'MEDIUM', status: 'Resolved', created: '1 day ago', eventCount: 3, assignee: 'Jane Smith', score: 45 },
]

const sevBadge = (s: string) => s === 'CRITICAL' ? 'danger' : s === 'HIGH' ? 'warning' : 'neutral'
const statusBadge = (s: string) => s === 'Open' ? 'danger' : s === 'Investigating' ? 'warning' : 'success'

export default function IncidentCenter() {
  const [q, setQ] = useState('')

  const filtered = MOCK_INCIDENTS.filter(i =>
    (i.title + i.id + i.assignee).toLowerCase().includes(q.toLowerCase())
  )

  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <div>
          <h1 className="page-title">Incident center</h1>
          <p className="page-subtitle" style={{ margin: 0 }}>High-risk correlated events grouped into actionable incidents.</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary">My incidents</button>
          <button className="btn btn-primary">Create incident</button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 400 }}>
          <Search size={15} color="#6b7280" style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)' }} />
          <input className="glass-input" placeholder="Search incidents..." value={q} onChange={e => setQ(e.target.value)} style={{ paddingLeft: 36 }} />
        </div>
        <select className="glass-input" style={{ width: 150 }}>
          <option>All Statuses</option>
          <option>Open</option>
          <option>Investigating</option>
          <option>Resolved</option>
        </select>
        <select className="glass-input" style={{ width: 150 }}>
          <option>All Severities</option>
          <option>Critical</option>
          <option>High</option>
          <option>Medium</option>
          <option>Low</option>
        </select>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 260px', gap: 20, alignItems: 'flex-start' }}>
        <div className="glass-table-container">
          <table className="glass-table">
            <thead>
              <tr><th>Incident</th><th>Severity</th><th>Status</th><th>Events</th><th>Assignee</th><th>Score</th></tr>
            </thead>
            <tbody>
              {filtered.map(inc => (
                <tr key={inc.id} style={{ cursor: 'pointer' }}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{inc.title}</div>
                    <div className="mono" style={{ fontSize: 11, color: '#6b7280' }}>{inc.id} · {inc.created}</div>
                  </td>
                  <td><span className={`badge badge-${sevBadge(inc.severity)}`}>{inc.severity}</span></td>
                  <td><span className={`badge badge-${statusBadge(inc.status)}`}>{inc.status}</span></td>
                  <td className="mono" style={{ fontSize: 12 }}>{inc.eventCount}</td>
                  <td style={{ fontSize: 13 }}>{inc.assignee}</td>
                  <td className="mono" style={{ fontSize: 13, fontWeight: 700 }}>{inc.score}</td>
                </tr>
              ))}
              {filtered.length === 0 && <tr><td colSpan={6} style={{ textAlign: 'center', color: '#6b7280' }}>No incidents match.</td></tr>}
            </tbody>
          </table>
        </div>

        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Summary</h3>
          <table className="glass-table">
            <tbody>
              <tr><td style={{ fontSize: 13, color: '#6b7280' }}>Critical</td><td className="mono" style={{ textAlign: 'right', fontWeight: 700 }}>1</td></tr>
              <tr><td style={{ fontSize: 13, color: '#6b7280' }}>High</td><td className="mono" style={{ textAlign: 'right', fontWeight: 700 }}>1</td></tr>
              <tr><td style={{ fontSize: 13, color: '#6b7280' }}>Medium / Low</td><td className="mono" style={{ textAlign: 'right', fontWeight: 700 }}>1</td></tr>
            </tbody>
          </table>
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid #e5e7eb', fontSize: 12, color: '#6b7280' }}>
            <div style={{ marginBottom: 4 }}>· IP auto-block (SOAR) active</div>
            <div>· Slack alerts active</div>
          </div>
        </div>
      </div>
    </div>
  )
}
