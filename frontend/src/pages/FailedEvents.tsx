import { useState } from 'react'
import { RotateCw, Trash2, Search } from 'lucide-react'

const MOCK_DLQ = [
  { id: 'err-101', timestamp: '2026-09-23T12:05:10Z', source: 'SRC-006 (Corporate Proxy)', rawSnippet: '192.168.1.100 - - [23/Sep/2026:12:05:10 +0000] "GET / HTTP/1.1" 200 -', error: 'Parser mismatch: Expected JSON, got Plaintext', parser: 'generic-syslog-parser' },
  { id: 'err-102', timestamp: '2026-09-23T12:06:22Z', source: 'SRC-008 (Payment API Gateway)', rawSnippet: '{"txn_id":"txn_9921", "amt": 500}', error: 'Schema Validation: Missing required field @timestamp', parser: 'custom-api-parser' },
  { id: 'err-103', timestamp: '2026-09-23T12:07:45Z', source: 'SRC-008 (Payment API Gateway)', rawSnippet: '{"txn_id":"txn_9922", "amt": 1500}', error: 'Schema Validation: Missing required field @timestamp', parser: 'custom-api-parser' },
  { id: 'err-104', timestamp: '2026-09-23T12:08:00Z', source: 'SRC-002 (Data Center IDS)', rawSnippet: '<14>Sep 23 12:08:00 ids-01 suricata[892]: [1:2010935:2] ET SCAN...', error: 'Timeout during semantic parsing', parser: 'generic-syslog-parser' }
]

export default function FailedEvents() {
  const [selected, setSelected] = useState<string[]>([])

  const toggleSelect = (id: string) => {
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  }

  const selectAll = () => {
    if (selected.length === MOCK_DLQ.length) setSelected([])
    else setSelected(MOCK_DLQ.map(e => e.id))
  }

  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <div>
          <h1 className="page-title">Failed events / DLQ <span className="badge badge-danger" style={{ marginLeft: 8, verticalAlign: 'middle' }}>{MOCK_DLQ.length} errors</span></h1>
          <p className="page-subtitle" style={{ margin: 0 }}>Events that failed parsing or schema validation, queued for review and reprocessing.</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary" disabled={selected.length === 0}>
            <Trash2 size={14} /> Discard ({selected.length})
          </button>
          <button className="btn btn-primary" disabled={selected.length === 0}>
            <RotateCw size={14} /> Reprocess ({selected.length})
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 300 }}>
          <Search size={15} color="#6b7280" style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)' }} />
          <input className="glass-input" placeholder="Search raw logs or errors..." style={{ paddingLeft: 36 }} />
        </div>
        <select className="glass-input" style={{ width: 200 }}>
          <option>All Sources</option>
          <option>SRC-008 (Payment API Gateway)</option>
          <option>SRC-006 (Corporate Proxy)</option>
        </select>
        <select className="glass-input" style={{ width: 180 }}>
          <option>All Error Types</option>
          <option>Parser mismatch</option>
          <option>Schema Validation</option>
          <option>Timeout</option>
        </select>
      </div>

      {selected.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12, fontSize: 13 }}>
          <span style={{ fontWeight: 600 }}>{selected.length} events selected</span>
          <select className="glass-input" style={{ width: 250 }}>
            <option value="">Select parser to override...</option>
            <option value="nginx-access-parser">nginx-access-parser v2.0.1</option>
            <option value="custom-api-parser-v2">custom-api-parser v2.0.0</option>
          </select>
          <button className="btn btn-primary" style={{ padding: '6px 14px', fontSize: 12 }}>Reprocess with parser</button>
        </div>
      )}

      <div className="glass-table-container">
        <table className="glass-table">
          <thead>
            <tr>
              <th style={{ width: 40 }}><input type="checkbox" checked={selected.length === MOCK_DLQ.length && MOCK_DLQ.length > 0} onChange={selectAll} /></th>
              <th>Timestamp</th>
              <th>Source / Original Parser</th>
              <th>Raw Snippet</th>
              <th>Error Reason</th>
              <th style={{ textAlign: 'right' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {MOCK_DLQ.map(evt => (
              <tr key={evt.id}>
                <td><input type="checkbox" checked={selected.includes(evt.id)} onChange={() => toggleSelect(evt.id)} /></td>
                <td className="mono" style={{ fontSize: 11 }}>{new Date(evt.timestamp).toLocaleString()}</td>
                <td>
                  <div style={{ fontSize: 12, fontWeight: 500 }}>{evt.source}</div>
                  <div className="mono" style={{ fontSize: 11, color: '#6b7280' }}>{evt.parser}</div>
                </td>
                <td>
                  <code className="mono" style={{ fontSize: 11, maxWidth: 300, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={evt.rawSnippet}>
                    {evt.rawSnippet}
                  </code>
                </td>
                <td style={{ fontSize: 12, color: '#c81e1e' }}>{evt.error}</td>
                <td style={{ textAlign: 'right' }}>
                  <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 11 }}>
                    <RotateCw size={12} /> Retry
                  </button>
                </td>
              </tr>
            ))}
            {MOCK_DLQ.length === 0 && (
              <tr>
                <td colSpan={6} style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>Dead Letter Queue is empty.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
