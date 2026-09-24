import { useState } from 'react'
import { Search, MoreHorizontal, PlusCircle } from 'lucide-react'

const MOCK_USERS = [
  { id: 'usr-001', name: 'Jane Smith', email: 'jane.smith@gov.in', role: 'Security Admin', lastActive: '10 mins ago', status: 'Active' },
  { id: 'usr-002', name: 'John Doe', email: 'john.doe@gov.in', role: 'SOC Analyst', lastActive: '2 hours ago', status: 'Active' },
  { id: 'usr-003', name: 'Alice Developer', email: 'alice.dev@gov.in', role: 'Parser Developer', lastActive: '1 day ago', status: 'Active' },
  { id: 'usr-004', name: 'Bob Forensics', email: 'bob.forensics@gov.in', role: 'Forensics Officer', lastActive: '3 days ago', status: 'Active' },
  { id: 'usr-005', name: 'Contractor 01', email: 'cont-01@external.com', role: 'SOC Analyst', lastActive: '2 months ago', status: 'Suspended' },
]

const ROLES = [
  { name: 'Security Admin', desc: 'Full platform access. Can modify parsers, policies, and users.' },
  { name: 'SOC Analyst', desc: 'View incidents, events, and dashboards. Sees redacted PII by default.' },
  { name: 'Parser Developer', desc: 'Can use Parser Studio to create and test parsing plugins.' },
  { name: 'Forensics Officer', desc: 'Can view unredacted Vault logs and override Privacy Policies for investigations.' },
]

export default function UserManagement() {
  const [q, setQ] = useState('')

  const filtered = MOCK_USERS.filter(u =>
    u.name.toLowerCase().includes(q.toLowerCase()) ||
    u.email.toLowerCase().includes(q.toLowerCase())
  )

  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <div>
          <h1 className="page-title">User management & RBAC</h1>
          <p className="page-subtitle" style={{ margin: 0 }}>Roles determine data visibility (e.g. Forensics Officers can see unredacted PII).</p>
        </div>
        <button className="btn btn-primary">
          <PlusCircle size={14} /> Add user
        </button>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 400 }}>
          <Search size={15} color="#6b7280" style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)' }} />
          <input
            className="glass-input"
            placeholder="Search users by name or email..."
            value={q}
            onChange={e => setQ(e.target.value)}
            style={{ paddingLeft: 36 }}
          />
        </div>
        <select className="glass-input" style={{ width: 180 }}>
          <option>All Roles</option>
          <option>Security Admin</option>
          <option>SOC Analyst</option>
          <option>Parser Developer</option>
          <option>Forensics Officer</option>
        </select>
        <select className="glass-input" style={{ width: 150 }}>
          <option>All Statuses</option>
          <option>Active</option>
          <option>Suspended</option>
        </select>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 20, alignItems: 'flex-start' }}>
        <div className="glass-table-container">
          <table className="glass-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Status</th>
                <th>Last Active</th>
                <th style={{ width: 40 }}></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(u => (
                <tr key={u.id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{u.name}</div>
                    <div style={{ fontSize: 12, color: '#6b7280' }}>{u.email}</div>
                  </td>
                  <td><span className="badge badge-primary">{u.role}</span></td>
                  <td>
                    <span className={`badge badge-${u.status === 'Active' ? 'success' : 'danger'}`}>
                      {u.status}
                    </span>
                  </td>
                  <td style={{ fontSize: 12, color: '#6b7280' }}>{u.lastActive}</td>
                  <td>
                    <button className="btn btn-ghost" style={{ padding: 4 }}><MoreHorizontal size={16} /></button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>No users found matching your search.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Role capabilities</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {ROLES.map(r => (
              <div key={r.name}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{r.name}</div>
                <div style={{ fontSize: 12, color: '#6b7280' }}>{r.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
