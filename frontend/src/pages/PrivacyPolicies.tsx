import { PlusCircle, Edit2 } from 'lucide-react'

const MOCK_POLICIES = [
  { id: 'pol-001', name: 'Govt Critical Infrastructure', description: 'Strict masking of all IPs, usernames, and hostnames for National Security assets.', status: 'Active', targetFields: ['source.ip', 'destination.ip', 'user.name', 'host.name'], strategy: 'Mask (***)', unredactedRoles: ['Forensics Officer', 'Security Admin'] },
  { id: 'pol-002', name: 'Default Analytics Policy', description: 'Basic PII protection to comply with DPDP Act.', status: 'Active', targetFields: ['user.email', 'user.phone', 'user.pan', 'user.aadhaar'], strategy: 'Hash (SHA-256)', unredactedRoles: ['Security Admin'] },
  { id: 'pol-003', name: 'Internal QA Logging', description: 'Development environment masking for staging logs.', status: 'Inactive', targetFields: ['payload.credit_card', 'payload.password'], strategy: 'Redact ([REDACTED])', unredactedRoles: [] },
]

export default function PrivacyPolicies() {
  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <div>
          <h1 className="page-title">Privacy & redaction policies</h1>
          <p className="page-subtitle" style={{ margin: 0 }}>PII masking applied before indexing. Originals stay protected in the raw vault.</p>
        </div>
        <button className="btn btn-primary">
          <PlusCircle size={14} /> Create policy
        </button>
      </div>

      <div style={{ display: 'flex', gap: 32, padding: '4px 0 20px', marginBottom: 20, borderBottom: '1px solid #e5e7eb' }}>
        {[
          { label: 'Active policies', value: '2' },
          { label: 'Protected fields', value: '12' },
          { label: 'Fields redacted (24h)', value: '4.2M' },
        ].map(s => (
          <div key={s.label} style={{ minWidth: 160 }}>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 2 }}>{s.label}</div>
            <div style={{ fontSize: 24, fontWeight: 700, color: '#111928' }}>{s.value}</div>
          </div>
        ))}
      </div>

      <div className="glass-table-container">
        <table className="glass-table">
          <thead>
            <tr><th>Policy</th><th>Status</th><th>Target fields</th><th>Strategy</th><th>Unredacted access</th><th style={{ textAlign: 'right' }}>Actions</th></tr>
          </thead>
          <tbody>
            {MOCK_POLICIES.map(pol => (
              <tr key={pol.id}>
                <td>
                  <div style={{ fontWeight: 600 }}>{pol.name}</div>
                  <div style={{ fontSize: 12, color: '#6b7280' }}>{pol.description}</div>
                </td>
                <td><span className={`badge badge-${pol.status === 'Active' ? 'success' : 'neutral'}`}>{pol.status}</span></td>
                <td>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {pol.targetFields.map(f => (
                      <code key={f} className="mono" style={{ fontSize: 11, background: '#f3f4f6', padding: '2px 6px', borderRadius: 4 }}>{f}</code>
                    ))}
                  </div>
                </td>
                <td style={{ fontSize: 12, whiteSpace: 'nowrap' }}>{pol.strategy}</td>
                <td style={{ fontSize: 12 }}>
                  {pol.unredactedRoles.length > 0 ? pol.unredactedRoles.join(', ') : <span style={{ color: '#9ca3af' }}>None</span>}
                </td>
                <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                  <button className="btn btn-ghost" style={{ padding: '4px 8px', fontSize: 12 }}><Edit2 size={13} /> Edit</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
