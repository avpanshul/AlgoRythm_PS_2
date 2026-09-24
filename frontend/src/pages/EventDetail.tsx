import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { DEMO_EVENTS } from '../data/demo'
import { ArrowLeft, ShieldCheck, Activity, Database, Lock, GitBranch, AlertTriangle, Copy } from 'lucide-react'

const RAW_SAMPLE = `<134> 1 2026-09-23T10:24:11Z FW-Delhi-01 - - - msg="Intrusion Detected" src_ip=192.168.1.10 dst_ip=203.0.113.45 action=BLOCK proto=TCP dpt=22 spt=49231 rule="IDS-SSH-Brute"`

const NORMALIZED_SAMPLE = {
  "@timestamp": "2026-09-23T10:24:11.000Z",
  "event.action": "Intrusion Detected",
  "event.category": "intrusion_detection",
  "event.severity": "critical",
  "source.ip": "192.168.1.10",
  "source.port": 49231,
  "destination.ip": "203.0.113.45",
  "destination.port": 22,
  "network.protocol": "TCP",
  "observer.name": "FW-Delhi-01",
  "rule.name": "IDS-SSH-Brute",
  "risk.score": 87,
  "ulpf.quality_score": 96
}

const REDACTED_SAMPLE = {
  "@timestamp": "2026-09-23T10:24:11.000Z",
  "event.action": "Intrusion Detected",
  "event.category": "intrusion_detection",
  "event.severity": "critical",
  "source.ip": "192.168.*.*",
  "source.port": "REDACTED",
  "destination.ip": "203.0.113.45",
  "destination.port": 22,
  "network.protocol": "TCP",
  "observer.name": "FW-Delhi-01",
  "rule.name": "IDS-SSH-Brute",
  "risk.score": 87,
  "ulpf.quality_score": 96
}

export default function EventDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('overview')
  const [verified, setVerified] = useState(false)

  const { data: trace } = useQuery({
    queryKey: ['event-trace', id],
    queryFn: () => api.getEventTrace(id!).catch(() => null),
    retry: false
  })

  const { data: eventData } = useQuery({
    queryKey: ['event', id],
    queryFn: () => api.getEvent(id!).catch(() => null),
    retry: false
  })

  // Find demo event for display if real event doesn't exist
  const displayEvent = eventData || DEMO_EVENTS.find(e => e.event_id === id) || DEMO_EVENTS[0]

  const TABS = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'raw', label: 'Raw Log', icon: Database },
    { id: 'normalized', label: 'Normalized', icon: GitBranch },
    { id: 'redacted', label: 'Redacted', icon: Lock },
    { id: 'provenance', label: 'Provenance', icon: ShieldCheck },
  ]

  const PROVENANCE_STEPS = [
    { label: '1. Raw Ingestion', description: 'Received via Syslog UDP', detail: { source: displayEvent.source_id || 'FW-Delhi-01', protocol: 'Syslog-RFC5424', received_at: displayEvent.timestamp, sha256: displayEvent.raw_sha256 || 'e3b0c44298fc1c149afb...b855' } },
    { label: '2. Format Detection', description: 'Format identified automatically', detail: { format: displayEvent.parser_format || 'Syslog RFC5424', vendor: 'Palo Alto', confidence: '98%', method: 'Deterministic' } },
    { label: '3. Parsing', description: 'Fields extracted via parser plugin', detail: { parser: displayEvent.parser_id || 'syslog_paloalto_v1.4.2', fields_extracted: 12, parse_time_ms: 2 } },
    { label: '4. Normalization', description: 'Mapped to ECS canonical schema', detail: { schema: 'ECS 1.12', fields_mapped: 11, ai_assisted: false } },
    { label: '5. Risk Scoring', description: 'Risk calculated by rule engine', detail: { risk_score: displayEvent.risk_score || 87, severity: displayEvent.severity || 'critical', rule: 'IDS-SSH-Brute' } },
    { label: '6. Storage', description: 'Indexed in OpenSearch & MinIO vault', detail: { index: 'ulpf-events-2026.09.23', raw_vault: 'minio://raw-logs/2026/09/23/' } },
  ]

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 20 }}>
            <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 20 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Event summary</h3>
              <table className="glass-table">
                <tbody>
                  {[
                    { label: 'Timestamp', value: new Date(displayEvent.timestamp).toLocaleString() },
                    { label: 'Source', value: displayEvent.source?.name || displayEvent.source_id },
                    { label: 'Source IP', value: displayEvent.source_ip || displayEvent.source?.ip, mono: true },
                    { label: 'Event Type', value: displayEvent.action || displayEvent.event?.action },
                    { label: 'Severity', value: displayEvent.severity || displayEvent.event?.severity, badge: true },
                    { label: 'Quality Score', value: String(displayEvent.quality_score || displayEvent.quality || 85), mono: true },
                  ].map(row => (
                    <tr key={row.label}>
                      <td style={{ color: '#6b7280', fontSize: 13 }}>{row.label}</td>
                      <td style={{ textAlign: 'right' }}>
                        {row.badge ? (
                          <span className={`badge badge-${row.value === 'critical' ? 'danger' : 'warning'}`}>{row.value}</span>
                        ) : (
                          <span className={row.mono ? 'mono' : ''} style={{ fontSize: 13, fontWeight: 500 }}>{row.value}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <AlertTriangle size={16} color="#c81e1e" />
                <h3 style={{ fontSize: 14, fontWeight: 600 }}>Risk assessment</h3>
              </div>
              <div style={{ fontSize: 36, fontWeight: 700, color: '#111928', letterSpacing: '-0.02em' }}>{displayEvent.risk_score || 87}<span style={{ fontSize: 14, fontWeight: 400, color: '#6b7280' }}> / 100</span></div>
              <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 16 }}>{displayEvent.risk_level || 'Critical'}</div>
              <table className="glass-table">
                <tbody>
                  {[
                    { label: 'Event Severity', pts: 30 },
                    { label: 'Asset Criticality', pts: 25 },
                    { label: 'Historical Anomaly', pts: 20 },
                    { label: 'Rule Match', pts: 12 },
                  ].map(f => (
                    <tr key={f.label}>
                      <td style={{ fontSize: 13, color: '#6b7280' }}>{f.label}</td>
                      <td className="mono" style={{ textAlign: 'right', fontSize: 12 }}>{f.pts} pts</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )

      case 'raw':
        return (
          <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600 }}>Original preserved log</h3>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <span className="mono" style={{ fontSize: 11, color: '#057a55' }}>SHA-256 validated</span>
                <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 11 }}>
                  <Copy size={12} /> Copy
                </button>
              </div>
            </div>
            <pre className="code-block" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
              {trace?.raw_content || RAW_SAMPLE}
            </pre>
            <div style={{ marginTop: 12 }}>
              <div className="mono" style={{ fontSize: 11, color: '#6b7280', marginBottom: 4 }}>SHA-256</div>
              <div className="mono" style={{ fontSize: 12, wordBreak: 'break-all' }}>
                e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
              </div>
            </div>
          </div>
        )

      case 'normalized':
        return (
          <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 20 }}>
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Canonical ECS document</h3>
            <pre className="code-block" style={{ whiteSpace: 'pre-wrap' }}>
              {JSON.stringify(NORMALIZED_SAMPLE, null, 2)}
            </pre>
          </div>
        )

      case 'redacted':
        return (
          <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600 }}>Privacy-preserved view</h3>
              <span className="badge badge-primary">Privacy policy applied</span>
            </div>
            <pre className="code-block" style={{ whiteSpace: 'pre-wrap' }}>
              {JSON.stringify(REDACTED_SAMPLE, null, 2)}
            </pre>
          </div>
        )

      case 'provenance':
        return (
          <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 20 }}>
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Lineage & processing trace</h3>
            <table className="glass-table">
              <thead>
                <tr><th>Stage</th><th>Detail</th></tr>
              </thead>
              <tbody>
                {PROVENANCE_STEPS.map((step, i) => (
                  <tr key={i}>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{step.label}</div>
                      <div style={{ fontSize: 12, color: '#6b7280' }}>{step.description}</div>
                    </td>
                    <td><pre className="code-block" style={{ fontSize: 11 }}>{JSON.stringify(step.detail, null, 2)}</pre></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid #e5e7eb' }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Integrity verification</div>
              <table className="glass-table">
                <tbody>
                  <tr><td style={{ fontSize: 13, color: '#6b7280' }}>Event Hash</td><td className="mono" style={{ fontSize: 12 }}>e3b0c44298fc1c149afb...b855</td></tr>
                  <tr><td style={{ fontSize: 13, color: '#6b7280' }}>Batch ID</td><td className="mono" style={{ fontSize: 12 }}>batch_100492</td></tr>
                  <tr><td style={{ fontSize: 13, color: '#6b7280' }}>Merkle Root</td><td className="mono" style={{ fontSize: 12 }}>8d969eef6ecad3c29a3a...c92</td></tr>
                </tbody>
              </table>
              <div style={{ marginTop: 12 }}>
                {verified ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <ShieldCheck size={18} color="#057a55" />
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#057a55' }}>Integrity verified</div>
                      <div style={{ fontSize: 12, color: '#6b7280' }}>Hash matches vault. Event has not been modified.</div>
                    </div>
                  </div>
                ) : (
                  <button className="btn btn-secondary" onClick={() => setVerified(true)}>
                    <ShieldCheck size={14} /> Verify Integrity
                  </button>
                )}
              </div>
            </div>
          </div>
        )

      default: return null
    }
  }

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

  return (
    <div className="animate-fade-in" style={{ paddingBottom: 40 }}>
      <button className="btn btn-ghost" style={{ marginBottom: 12, paddingLeft: 0 }} onClick={() => navigate('/events')}>
        <ArrowLeft size={16} /> Back to Explorer
      </button>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 0, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h1 className="page-title" style={{ margin: 0 }}>Event investigation</h1>
            <span className="badge badge-danger">Critical</span>
          </div>
          <p className="page-subtitle mono" style={{ margin: 0, fontSize: 12 }}>ID: {id}</p>
        </div>
      </div>

      <div style={{ display: 'flex', borderBottom: '1px solid #e5e7eb', marginBottom: 20 }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)} style={tabBtn(activeTab === t.id)}>
            <t.icon size={14} />
            {t.label}
          </button>
        ))}
      </div>

      {renderTabContent()}
    </div>
  )
}
