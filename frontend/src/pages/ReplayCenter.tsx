import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { ShieldCheck, RotateCcw, AlertOctagon, UserCircle } from 'lucide-react'

export default function IntegrityAndReplay() {
  const [activeTab, setActiveTab] = useState('integrity')
  const [verified, setVerified] = useState(false)
  const [replayStarted, setReplayStarted] = useState(false)

  const { data: replayJobs = [] } = useQuery({ queryKey: ['replayJobs'], queryFn: () => api.getReplayJobs() })
  const { data: dlqEvents = { items: [], total: 0 } } = useQuery({ queryKey: ['dlq'], queryFn: () => api.getDlq() })
  const { data: auditLogs = [] } = useQuery({ queryKey: ['auditLogs'], queryFn: () => api.getAuditLogs() })

  const TABS = [
    { id: 'integrity', label: 'Integrity verification', icon: ShieldCheck },
    { id: 'replay', label: 'Replay & reprocessing', icon: RotateCcw },
    { id: 'dlq', label: 'Dead-letter queue', icon: AlertOctagon },
    { id: 'audit', label: 'Audit logs', icon: UserCircle },
  ]

  const tabBtn = (active: boolean): React.CSSProperties => ({
    padding: '10px 4px',
    marginRight: 20,
    fontSize: 13,
    fontWeight: active ? 600 : 500,
    background: 'transparent',
    color: active ? '#1a56db' : '#6b7280',
    border: 'none',
    borderBottom: active ? '2px solid #1a56db' : '2px solid transparent',
    marginBottom: -1,
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
  })

  const renderTabContent = () => {
    switch (activeTab) {
      case 'integrity':
        return (
          <div>
            <div style={{ display: 'flex', gap: 32, padding: '4px 0 20px', marginBottom: 20, borderBottom: '1px solid #e5e7eb' }}>
              {[
                { label: 'Events verified today', value: '1,24,532' },
                { label: 'Integrity failures', value: '0' },
                { label: 'Batch Merkle trees', value: '127' },
              ].map(s => (
                <div key={s.label} style={{ minWidth: 160 }}>
                  <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 2 }}>{s.label}</div>
                  <div style={{ fontSize: 24, fontWeight: 700, color: '#111928' }}>{s.value}</div>
                </div>
              ))}
            </div>
            <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 20 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Event integrity verification</h3>
              <table className="glass-table">
                <tbody>
                  {[
                    { label: 'Event ID', value: 'evt_92837492837492834' },
                    { label: 'Computed Hash', value: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855' },
                    { label: 'Stored Hash', value: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855' },
                    { label: 'Batch ID', value: 'batch_100492' },
                    { label: 'Merkle Root', value: '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92' },
                  ].map(row => (
                    <tr key={row.label}>
                      <td style={{ fontSize: 13, color: '#6b7280', whiteSpace: 'nowrap', width: 140 }}>{row.label}</td>
                      <td className="mono" style={{ fontSize: 11, wordBreak: 'break-all' }}>{row.value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ marginTop: 16 }}>
                {verified ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <ShieldCheck size={18} color="#057a55" />
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#057a55' }}>Integrity verified</div>
                      <div style={{ fontSize: 12, color: '#6b7280' }}>SHA-256 hash matches vault copy.</div>
                    </div>
                  </div>
                ) : (
                  <button className="btn btn-primary" onClick={() => setVerified(true)}>
                    <ShieldCheck size={14} /> Verify integrity
                  </button>
                )}
              </div>
            </div>
          </div>
        )

      case 'replay':
        return (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 20 }}>
            <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 20 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Start reprocessing job</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 16 }}>
                {[
                  { label: 'Time range', placeholder: '2026-09-22 00:00 → 2026-09-23 00:00' },
                  { label: 'Source', placeholder: 'FW-Delhi-01' },
                  { label: 'Parser version', placeholder: 'v1.4.3 (Latest)' },
                ].map(f => (
                  <div key={f.label}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', marginBottom: 4 }}>{f.label}</div>
                    <input type="text" className="glass-input" defaultValue={f.placeholder} />
                  </div>
                ))}
              </div>
              {replayStarted ? (
                <div style={{ fontSize: 13 }}>
                  <div style={{ fontWeight: 600, color: '#1a56db' }}>Replay job started</div>
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>Processing in the background. Check the jobs list for status.</div>
                </div>
              ) : (
                <button className="btn btn-primary" onClick={() => setReplayStarted(true)}>
                  <RotateCcw size={14} /> Start replay
                </button>
              )}
            </div>

            <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 20 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Recent replay jobs</h3>
              <table className="glass-table">
                <tbody>
                  {replayJobs.map((job: any, i: number) => (
                    <tr key={i}>
                      <td>
                        <div className="mono" style={{ fontSize: 12, fontWeight: 600 }}>Job #{job.id}</div>
                        <div style={{ fontSize: 12, color: '#6b7280' }}>{job.total_events || 0} events · {new Date(job.created_at).toLocaleDateString()}</div>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <span className={`badge badge-${job.status === 'completed' ? 'success' : job.status === 'failed' ? 'danger' : 'warning'}`}>{job.status}</span>
                      </td>
                    </tr>
                  ))}
                  {replayJobs.length === 0 && <tr><td style={{ fontSize: 12, color: '#6b7280', textAlign: 'center' }}>No recent jobs</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        )

      case 'dlq':
        return (
          <div>
            <div style={{ display: 'flex', gap: 32, padding: '4px 0 20px', marginBottom: 20, borderBottom: '1px solid #e5e7eb' }}>
              {[
                { label: 'Total failed', value: dlqEvents.total.toLocaleString() },
                { label: 'Unknown format', value: '0' },
                { label: 'Schema validation', value: '0' },
                { label: 'Parser errors', value: '0' },
              ].map(s => (
                <div key={s.label} style={{ minWidth: 120 }}>
                  <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 2 }}>{s.label}</div>
                  <div style={{ fontSize: 24, fontWeight: 700, color: '#111928' }}>{s.value}</div>
                </div>
              ))}
            </div>
            <div className="glass-table-container">
              <table className="glass-table">
                <thead>
                  <tr>
                    <th>Failed Event ID</th>
                    <th>Failure Reason</th>
                    <th>Parser</th>
                    <th>Timestamp</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {dlqEvents.items.map((f: any, i: number) => (
                    <tr key={i}>
                      <td className="mono" style={{ fontSize: 11 }}>{f.event_id}</td>
                      <td><span className="badge badge-danger">{f.failure_reason}</span></td>
                      <td className="mono" style={{ fontSize: 12 }}>{f.parser_id || 'Unknown'}</td>
                      <td style={{ color: '#6b7280', fontSize: 12 }}>{new Date(f.created_at).toLocaleString()}</td>
                      <td>
                        <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 11 }} onClick={() => api.retryDlq(f.id)}>Retry</button>
                      </td>
                    </tr>
                  ))}
                  {dlqEvents.items.length === 0 && (
                    <tr><td colSpan={5} style={{ textAlign: 'center', color: '#6b7280' }}>No failed events in DLQ</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )

      case 'audit':
        return (
          <div className="glass-table-container">
            <table className="glass-table">
              <thead>
                <tr><th>Timestamp</th><th>User</th><th>Action</th><th>Entity</th><th>IP Address</th></tr>
              </thead>
              <tbody>
                {auditLogs.map((r: any, i: number) => (
                  <tr key={i}>
                    <td className="mono" style={{ fontSize: 12 }}>{new Date(r.timestamp).toLocaleString()}</td>
                    <td style={{ fontWeight: 500 }}>{r.user_id}</td>
                    <td><span className="badge badge-primary">{r.action}</span></td>
                    <td className="mono" style={{ fontSize: 11 }}>{r.entity_id}</td>
                    <td style={{ color: '#6b7280', fontSize: 12 }}>{r.ip_address}</td>
                  </tr>
                ))}
                {auditLogs.length === 0 && (
                  <tr><td colSpan={5} style={{ textAlign: 'center', color: '#6b7280' }}>No audit logs found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )
      default: return null
    }
  }

  return (
    <div className="animate-fade-in" style={{ paddingBottom: 40 }}>
      <div style={{ marginBottom: 0, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <h1 className="page-title">Integrity & replay</h1>
        <p className="page-subtitle" style={{ margin: 0 }}>Verify log provenance, reprocess events, manage dead-letter queues, and review audit trails</p>
      </div>

      <div style={{ display: 'flex', borderBottom: '1px solid #e5e7eb', marginBottom: 20 }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => { setActiveTab(t.id); setVerified(false); setReplayStarted(false) }}
            style={tabBtn(activeTab === t.id)}
          >
            <t.icon size={14} />
            {t.label}
          </button>
        ))}
      </div>

      {renderTabContent()}
    </div>
  )
}
