import { useState } from 'react'
import { Save, UploadCloud, Play, Code, Check } from 'lucide-react'

const MOCK_RAW = `Sep 23 12:00:00 gateway-01 sshd[14512]: Failed password for admin from 203.0.113.15 port 48125 ssh2`
const MOCK_CONF = `name: linux-auth-syslog-parser
version: 1.0.6
format: regex
pattern: '^(?P<timestamp>\\w{3}\\s+\\d+\\s+\\d+:\\d+:\\d+)\\s+(?P<host>[\\w-]+)\\s+(?P<process>[\\w]+)\\[(?P<pid>\\d+)\\]:\\s+(?P<message>.*)$'
mappings:
  - raw: host
    canonical: host.name
  - raw: process
    canonical: event.provider
  - custom_eval:
      if: message contains "Failed password"
      set:
        event.action: "login_failed"
        event.outcome: "failure"
`
const MOCK_PREVIEW = {
  "host.name": "gateway-01",
  "event.provider": "sshd",
  "event.action": "login_failed",
  "event.outcome": "failure",
  "timestamp": "Sep 23 12:00:00"
}

export default function MappingReview() {
  const [config, setConfig] = useState(MOCK_CONF)
  const [tested, setTested] = useState(false)

  const paneHead: React.CSSProperties = { padding: '10px 16px', borderBottom: '1px solid #e5e7eb', background: '#f7f8fa', fontSize: 12, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }

  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <div>
          <h1 className="page-title">Parser studio <span className="badge badge-warning" style={{ marginLeft: 8, verticalAlign: 'middle' }}>Draft</span></h1>
          <p className="page-subtitle" style={{ margin: 0 }}>Human-in-the-loop parser development. Review AI-suggested mappings and publish plugins.</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary">
            <Save size={14} /> Save draft
          </button>
          <button className="btn btn-primary">
            <UploadCloud size={14} /> Publish v1.0.6
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
        <div style={{ flex: 1, border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' }}>
          <div style={paneHead}>
            <span>1. Raw sample</span>
            <button className="btn btn-ghost" style={{ fontSize: 11, padding: '2px 8px' }}>Load new sample</button>
          </div>
          <textarea
            className="glass-input mono"
            style={{ border: 'none', borderRadius: 0, resize: 'vertical', fontSize: 12, padding: 16, minHeight: 320 }}
            defaultValue={MOCK_RAW}
          />
        </div>

        <div style={{ flex: 1.5, border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' }}>
          <div style={paneHead}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Code size={14} /> 2. Parser configuration (YAML)
            </span>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', textTransform: 'none' }}>
              <span style={{ fontSize: 11, color: '#057a55', display: 'flex', alignItems: 'center', gap: 4 }}><Check size={12} /> AI suggestions applied</span>
              <button className="btn btn-primary" onClick={() => setTested(true)} style={{ fontSize: 11, padding: '4px 10px' }}>
                <Play size={12} /> Test parser
              </button>
            </div>
          </div>
          <textarea
            className="glass-input mono"
            style={{ border: 'none', borderRadius: 0, resize: 'vertical', fontSize: 12, padding: 16, minHeight: 320 }}
            value={config}
            onChange={e => setConfig(e.target.value)}
          />
        </div>

        <div style={{ flex: 1, border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' }}>
          <div style={paneHead}>
            <span>3. Normalized preview</span>
          </div>
          {tested ? (
            <div>
              <div style={{ padding: 12, borderBottom: '1px solid #e5e7eb', display: 'flex', gap: 16 }}>
                <div>
                  <div style={{ fontSize: 10, color: '#057a55', textTransform: 'uppercase' }}>Schema validation</div>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>Passed</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: '#6b7280', textTransform: 'uppercase' }}>Data quality</div>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>98/100</div>
                </div>
              </div>
              <pre className="code-block" style={{ border: 'none', borderRadius: 0, fontSize: 12 }}>
                {JSON.stringify(MOCK_PREVIEW, null, 2)}
              </pre>
            </div>
          ) : (
            <div style={{ padding: 40, textAlign: 'center', color: '#6b7280', fontSize: 13 }}>
              Click "Test parser" to generate preview.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
