import { useState } from 'react'
import { Save, Play, FileText } from 'lucide-react'

const RAW_SAMPLE = `<134> 1 2026-09-23T14:22:10Z FW-Delhi-01 - - - msg="Connection Denied" src_ip=192.168.1.50 dst_ip=10.0.0.2 action=DENY proto=TCP dpt=443 spt=48291 rule="Block-External"`

const YAML_CONFIG = `# Parser Plugin — syslog_paloalto_v1.4.2
parser_version: "1.4.2"
format: syslog_rfc5424
vendor: paloalto
device_type: firewall

fields:
  - source: src_ip
    target: source.ip
    type: ip
    required: true
  - source: dst_ip
    target: destination.ip
    type: ip
    required: true
  - source: action
    target: event.action
    type: string
  - source: proto
    target: network.protocol
    type: string
  - source: dpt
    target: destination.port
    type: integer
  - source: spt
    target: source.port
    type: integer
  - source: rule
    target: rule.name
    type: string
  - source: msg
    target: message
    type: string

schema_validation: strict
redact_fields:
  - source.port`

const MAPPINGS = [
  { src: 'src_ip', target: 'source.ip', type: 'ip', confidence: 99, method: 'Deterministic' },
  { src: 'dst_ip', target: 'destination.ip', type: 'ip', confidence: 99, method: 'Deterministic' },
  { src: 'action', target: 'event.action', type: 'string', confidence: 95, method: 'Template' },
  { src: 'proto', target: 'network.protocol', type: 'string', confidence: 98, method: 'Deterministic' },
  { src: 'dpt', target: 'destination.port', type: 'integer', confidence: 97, method: 'Deterministic' },
  { src: 'spt', target: 'source.port', type: 'integer', confidence: 97, method: 'Deterministic' },
  { src: 'rule', target: 'rule.name', type: 'string', confidence: 89, method: 'Semantic' },
  { src: 'msg', target: 'message', type: 'string', confidence: 99, method: 'Deterministic' },
]

export default function ParserLab() {
  const [activeStep, setActiveStep] = useState(3)
  const [testRan, setTestRan] = useState(false)

  return (
    <div className="animate-fade-in" style={{ paddingBottom: 40 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <div>
          <h1 className="page-title">Parser lab</h1>
          <p className="page-subtitle" style={{ margin: 0 }}>Develop, test, and publish deterministic and AI-assisted log parsers</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary">Upload sample</button>
          <button className="btn btn-primary"><Save size={14} /> Publish to registry</button>
        </div>
      </div>

      {/* Workflow Steps */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 16, overflowX: 'auto', fontSize: 13 }}>
        {['Upload Sample', 'Auto Detect', 'Field Mapping', 'Configure Parser', 'Test', 'Publish'].map((step, i) => (
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap' }}>
            <span
              onClick={() => setActiveStep(i)}
              style={{ cursor: 'pointer', fontWeight: i === activeStep ? 600 : 400, color: i === activeStep ? '#1a56db' : i < activeStep ? '#111928' : '#9ca3af' }}
            >
              {i + 1}. {step}
            </span>
            {i < 5 && <span style={{ color: '#d1d5db', margin: '0 6px' }}>›</span>}
          </span>
        ))}
      </div>

      {/* Detection summary */}
      <div style={{ display: 'flex', gap: 32, padding: '12px 0', marginBottom: 16, borderTop: '1px solid #e5e7eb', borderBottom: '1px solid #e5e7eb', fontSize: 13 }}>
        <div><span style={{ color: '#6b7280' }}>Format: </span><strong>Syslog RFC5424</strong></div>
        <div><span style={{ color: '#6b7280' }}>Vendor: </span><strong>Palo Alto</strong></div>
        <div><span style={{ color: '#6b7280' }}>Confidence: </span><strong style={{ color: '#057a55' }}>92%</strong></div>
        <div><span style={{ color: '#6b7280' }}>Version: </span><strong className="mono">v1.4.2</strong></div>
        <div><span className="badge badge-success">Approved</span></div>
      </div>

      {/* 3-Pane Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 20 }}>
        {/* Pane 1: Sample Log */}
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' }}>
          <div style={{ padding: '10px 16px', borderBottom: '1px solid #e5e7eb', fontSize: 13, fontWeight: 600, display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f7f8fa' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><FileText size={14} color="#6b7280" /> Raw sample</div>
            <span className="badge badge-neutral">Syslog</span>
          </div>
          <div style={{ padding: 16 }}>
            <pre className="code-block" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 11 }}>
              {RAW_SAMPLE}
            </pre>
          </div>
        </div>

        {/* Pane 2: Field Mapping */}
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' }}>
          <div style={{ padding: '10px 16px', borderBottom: '1px solid #e5e7eb', fontSize: 13, fontWeight: 600, display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f7f8fa' }}>
            <span>Suggested mapping</span>
            <span className="badge badge-neutral">{MAPPINGS.length} fields</span>
          </div>
          <div>
            <table className="glass-table" style={{ fontSize: 12 }}>
              <thead>
                <tr>
                  <th>Source field</th>
                  <th>ECS target</th>
                  <th>Conf.</th>
                </tr>
              </thead>
              <tbody>
                {MAPPINGS.map((m, i) => (
                  <tr key={i}>
                    <td className="mono">{m.src}</td>
                    <td className="mono" style={{ color: '#1a56db' }}>{m.target}</td>
                    <td>
                      <span style={{ fontSize: 11, fontWeight: 600, color: m.confidence >= 95 ? '#057a55' : '#c27803' }}>{m.confidence}%</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Pane 3: YAML Config */}
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' }}>
          <div style={{ padding: '10px 16px', borderBottom: '1px solid #e5e7eb', fontSize: 13, fontWeight: 600, display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f7f8fa' }}>
            <span>Parser configuration</span>
            <span className="badge badge-neutral">YAML</span>
          </div>
          <textarea
            className="mono"
            style={{ width: '100%', height: 380, border: 'none', resize: 'vertical', outline: 'none', fontSize: 11, lineHeight: 1.6, padding: 16, color: '#111928' }}
            defaultValue={YAML_CONFIG}
          />
        </div>
      </div>

      {/* Bottom Action Bar */}
      <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 13 }}>
          <span style={{ fontWeight: 600, color: '#057a55' }}>Schema validation passed</span>
          {testRan ? (
            <span style={{ color: '#057a55' }}>10 / 10 events parsed successfully</span>
          ) : (
            <span style={{ color: '#6b7280' }}>Test not yet run</span>
          )}
        </div>
        <button className="btn btn-secondary" onClick={() => setTestRan(true)}>
          <Play size={14} /> Run test
        </button>
      </div>
    </div>
  )
}
