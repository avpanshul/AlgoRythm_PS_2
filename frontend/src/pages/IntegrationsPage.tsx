import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Server, Globe, Shield, Activity, Trash2, X, Plus } from 'lucide-react'
import { api } from '../api/client'
import { GlassCard } from '../components/glass/GlassCard'

const STATUS_COLOR: Record<string, string> = { connected: '#057a55', configured: '#0044A8', error: '#c81e1e', disabled: '#8999b0' }

export default function IntegrationsPage() {
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [testingId, setTestingId] = useState<number | null>(null)
  const [testResult, setTestResult] = useState<{ id: number; result: any } | null>(null)

  const { data, isLoading } = useQuery({ queryKey: ['integrations'], queryFn: api.getIntegrations })
  const items: any[] = Array.isArray(data) ? data : []
  const connected = items.filter(i => i.status === 'connected').length

  const runTest = (id: number) => {
    setTestingId(id)
    setTestResult(null)
    api.testIntegration(id)
      .then((res: any) => setTestResult({ id, result: res.result }))
      .catch((e: any) => setTestResult({ id, result: { status: 'error', message: e?.response?.data?.detail || e?.message || 'Test request failed.' } }))
      .finally(() => {
        setTestingId(null)
        qc.invalidateQueries({ queryKey: ['integrations'] })
      })
  }

  const removeIntegration = (id: number) => {
    api.deleteIntegration(id).then(() => qc.invalidateQueries({ queryKey: ['integrations'] }))
  }

  return (
    <div className="page-container">
      <header style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 56, fontWeight: 700, color: '#0044A8', marginBottom: 8 }}>SIEM / Data Lake Integrations</h1>
        <p style={{ color: '#5b6382', fontSize: 15 }}>Configure outbound event routing and data lake connections.</p>
      </header>

      <GlassCard style={{ display: 'flex', alignItems: 'center', padding: '24px 40px', marginBottom: 24, borderRadius: 32 }}>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(0,68,168,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Globe size={24} color="#0044A8" />
          </div>
          <div>
            <div style={{ fontSize: 13, color: '#8999b0', fontWeight: 500, marginBottom: 4 }}>Configured Destinations</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: '#0a0e27', lineHeight: 1 }}>{items.length}</div>
          </div>
        </div>

        <div style={{ width: 1, height: 64, background: 'rgba(0,68,168,0.1)', margin: '0 24px' }} />

        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(5,122,85,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Shield size={24} color="#057a55" />
          </div>
          <div>
            <div style={{ fontSize: 13, color: '#8999b0', fontWeight: 500, marginBottom: 4 }}>Verified Connected</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: '#0a0e27', lineHeight: 1 }}>{connected} / {items.length}</div>
            <div style={{ fontSize: 12, color: '#8999b0', fontWeight: 600, marginTop: 6 }}>From real connectivity tests, not assumed</div>
          </div>
        </div>
      </GlassCard>

      <GlassCard>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
          <h2 className="section-heading">Configured Destinations</h2>
          <button onClick={() => setShowAdd(true)} style={{
            background: 'linear-gradient(135deg, #0044A8, #0088FF)', color: '#fff', border: 'none',
            padding: '8px 16px', borderRadius: 8, fontWeight: 600, fontSize: 13, cursor: 'pointer',
            boxShadow: '0 4px 12px rgba(0,68,168,0.2)'
          }}>+ Add Integration</button>
        </div>

        {isLoading ? (
          <div style={{ padding: 32, textAlign: 'center', color: '#8999b0' }}>Loading…</div>
        ) : items.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <Server size={28} color="#c0cde3" style={{ marginBottom: 8 }} />
            <p style={{ fontSize: 13, color: '#8999b0', fontWeight: 500 }}>No integrations configured yet.</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(0,68,168,0.1)', color: '#5b6382', textAlign: 'left' }}>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Destination</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Type</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Status</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Last Test</th>
                <th style={{ padding: '12px 16px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((d: any) => (
                <tr key={d.id} style={{ borderBottom: '1px solid rgba(0,68,168,0.05)' }}>
                  <td style={{ padding: '16px', fontWeight: 500, color: '#0a0e27' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(0,68,168,0.05)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Server size={16} color="#0044A8" />
                      </div>
                      {d.name}
                    </div>
                  </td>
                  <td style={{ padding: '16px', color: '#5b6382' }}>{d.type}</td>
                  <td style={{ padding: '16px' }}>
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      padding: '4px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600,
                      background: `${STATUS_COLOR[d.status] || '#8999b0'}15`, color: STATUS_COLOR[d.status] || '#8999b0'
                    }}>
                      <div style={{ width: 6, height: 6, borderRadius: '50%', background: STATUS_COLOR[d.status] || '#8999b0' }} />
                      {d.status}
                    </span>
                  </td>
                  <td style={{ padding: '16px', color: '#5b6382', fontSize: 12 }}>
                    {testResult && testResult.id === d.id
                      ? testResult.result.message
                      : d.last_test_at ? new Date(d.last_test_at).toLocaleString() : 'Never tested'}
                  </td>
                  <td style={{ padding: '16px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                      <button onClick={() => runTest(d.id)} disabled={testingId === d.id} title="Test connectivity" style={{ padding: 6, background: 'transparent', border: 'none', cursor: 'pointer', color: testingId === d.id ? '#c0cde3' : '#8999b0' }}>
                        <Activity size={16} className={testingId === d.id ? 'animate-spin' : ''} />
                      </button>
                      <button onClick={() => removeIntegration(d.id)} title="Delete" style={{ padding: 6, background: 'transparent', border: 'none', cursor: 'pointer', color: '#8999b0' }}>
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </GlassCard>

      {showAdd && (
        <AddIntegrationModal
          onClose={() => setShowAdd(false)}
          onCreated={() => { setShowAdd(false); qc.invalidateQueries({ queryKey: ['integrations'] }) }}
        />
      )}
    </div>
  )
}

function AddIntegrationModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState('')
  const [type, setType] = useState('rest_api')
  const [url, setUrl] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const submit = () => {
    if (!name.trim()) {
      setError('Destination name is required.')
      return
    }
    setSubmitting(true)
    setError(null)
    api.createIntegration({
      name: name.trim(),
      type,
      description: description.trim() || undefined,
      config: url.trim() ? { url: url.trim() } : {},
      enabled: true,
    })
      .then(onCreated)
      .catch((e: any) => setError(e?.response?.data?.detail || e?.message || 'Could not create this integration.'))
      .finally(() => setSubmitting(false))
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,15,46,0.4)', backdropFilter: 'blur(8px)' }}>
      <div style={{ width: '90%', maxWidth: 460, background: '#fff', borderRadius: 16, padding: 28, position: 'relative', boxShadow: '0 16px 48px rgba(0,15,92,0.2)' }}>
        <button onClick={onClose} style={{ position: 'absolute', top: 16, right: 16, background: 'none', border: 'none', cursor: 'pointer' }}><X size={18} color="#8999b0" /></button>
        <h2 style={{ fontSize: 18, fontWeight: 800, color: '#0a0e27', marginBottom: 20 }}>Add Integration</h2>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <input className="glass-input" value={name} onChange={e => setName(e.target.value)} placeholder="Destination name (e.g. Splunk Cloud)" />
          <select className="glass-input" value={type} onChange={e => setType(e.target.value)}>
            <option value="rest_api">REST API</option>
            <option value="webhook">Webhook</option>
            <option value="syslog">Syslog</option>
            <option value="s3">S3</option>
            <option value="opensearch">OpenSearch</option>
          </select>
          <input className="glass-input" value={url} onChange={e => setUrl(e.target.value)} placeholder="Endpoint URL (used for the real connectivity test)" />
          <input className="glass-input" value={description} onChange={e => setDescription(e.target.value)} placeholder="Description (optional)" />
          {error && <div style={{ color: '#c81e1e', fontSize: 12 }}>{error}</div>}
          <button onClick={submit} disabled={submitting} className="btn-primary" style={{ justifyContent: 'center', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Plus size={14} /> {submitting ? 'Adding…' : 'Add Integration'}
          </button>
        </div>
      </div>
    </div>
  )
}
