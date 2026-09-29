import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../api/client'
import { Zap, Send, Plus } from 'lucide-react'

export default function LiveEvents() {
  const [rawLog, setRawLog] = useState('')
  const [sourceId, setSourceId] = useState('FW-001')
  const [result, setResult] = useState<Record<string, unknown> | null>(null)

  const ingestMut = useMutation({
    mutationFn: () => api.ingestEvent({ source_id: sourceId, raw_log: rawLog }),
    onSuccess: (data) => { setResult(data.data); setRawLog('') }
  })

  const EXAMPLE_LOGS = [
    { label: 'Syslog Deny', log: '<134>Sep 22 16:45:32 FW-001 %ASA-3-106001: TCP denied from 10.0.0.1/4321 to 192.168.1.5/22' },
    { label: 'CEF Allow', log: 'CEF:0|Cisco|ASA|9.0|100000|Firewall Permit|3|src=10.0.0.1 dst=192.168.1.5 spt=4321 dpt=443 proto=TCP act=allow' },
    { label: 'JSON Auth', log: JSON.stringify({ timestamp: new Date().toISOString(), src: '10.0.0.1', action: 'login_failure', user: 'admin', severity: 'HIGH' }) },
    { label: 'Unknown Proprietary', log: 'FW-D|22-09-2026 16:45:32|10.0.0.1>192.168.1.5|TCP|4321>22|BLOCK' },
  ]

  return (
    <div>
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
          <Zap size={22} color="#f59e0b" />
          <h1 style={{ fontSize: 44, fontWeight: 700, color: 'var(--color-text-primary)' }}>Live Event Ingestion</h1>
        </div>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          Submit a raw log directly to the pipeline. The event will travel through format detection, parsing, normalization, and risk scoring.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Input */}
        <div className="glass-card" style={{ padding: 24 }}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 12, color: 'var(--color-text-muted)', display: 'block', marginBottom: 6 }}>Source ID</label>
            <input className="cyber-input" value={sourceId} onChange={e => setSourceId(e.target.value)} />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 12, color: 'var(--color-text-muted)', display: 'block', marginBottom: 6 }}>Raw Log (any format)</label>
            <textarea
              className="cyber-input"
              rows={8}
              style={{ resize: 'vertical', fontFamily: 'monospace', fontSize: 12 }}
              placeholder="Paste any raw log here — Syslog, CEF, LEEF, JSON, XML, or proprietary..."
              value={rawLog}
              onChange={e => setRawLog(e.target.value)}
            />
          </div>

          <button
            className="btn-primary"
            style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
            onClick={() => ingestMut.mutate()}
            disabled={!rawLog.trim() || ingestMut.isPending}
          >
            <Send size={15} />
            {ingestMut.isPending ? 'Ingesting…' : 'Ingest & Process'}
          </button>
        </div>

        {/* Quick examples + result */}
        <div>
          <div className="glass-card" style={{ padding: 20, marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Quick Examples</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {EXAMPLE_LOGS.map(ex => (
                <button
                  key={ex.label}
                  onClick={() => setRawLog(ex.log)}
                  style={{
                    background: 'var(--color-border)', border: '1px solid var(--color-border)', borderRadius: 6,
                    padding: '10px 14px', cursor: 'pointer', textAlign: 'left', color: 'var(--color-text-muted)',
                    fontSize: 12, display: 'flex', alignItems: 'center', gap: 8, transition: 'all 0.2s'
                  }}
                >
                  <Plus size={13} color="var(--color-text-primary)" />
                  {ex.label}
                </button>
              ))}
            </div>
          </div>

          {result && (
            <div className="glass-card" style={{ padding: 20, borderTop: '2px solid #10b981' }}>
              <div style={{ fontSize: 12, color: 'var(--color-success)', fontWeight: 600, marginBottom: 12 }}>✅ Event Ingested</div>
              <pre className="json-viewer" style={{ fontSize: 11 }}>{JSON.stringify(result, null, 2)}</pre>
              <div style={{ marginTop: 10, fontSize: 12, color: 'var(--color-text-muted)' }}>
                The worker is now processing this event through the pipeline asynchronously.
                Check Event Explorer or use the Trace ID above in the Provenance page.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
