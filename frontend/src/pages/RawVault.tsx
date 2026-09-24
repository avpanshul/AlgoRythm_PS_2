import { useState } from 'react'
import { Search, Download } from 'lucide-react'

const MOCK_VAULT = [
  { refId: 'raw-abc123', timestamp: '2026-09-23T12:00:00Z', source: 'SRC-001 (Firewall)', size: '240 B', hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855' },
  { refId: 'raw-def456', timestamp: '2026-09-23T12:01:15Z', source: 'SRC-003 (Web Nginx)', size: '1.2 KB', hash: '8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4' },
  { refId: 'raw-ghi789', timestamp: '2026-09-23T12:05:10Z', source: 'SRC-006 (Proxy)', size: '512 B', hash: 'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3' },
]

export default function RawVault() {
  const [q, setQ] = useState('')
  const [selectedRef, setSelectedRef] = useState<string | null>(null)

  const filtered = MOCK_VAULT.filter(v => v.refId.toLowerCase().includes(q.toLowerCase()) || v.hash.toLowerCase().includes(q.toLowerCase()))
  const selected = filtered.find(v => v.refId === selectedRef) || null

  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <div>
          <h1 className="page-title">Raw log vault <span className="badge badge-neutral" style={{ marginLeft: 8, verticalAlign: 'middle' }}>Cold storage</span></h1>
          <p className="page-subtitle" style={{ margin: 0 }}>Immutable store of original logs. Each parsed event links back here by reference ID.</p>
        </div>
        <button className="btn btn-secondary">
          <Download size={14} /> Export audit log
        </button>
      </div>

      <div style={{ position: 'relative', maxWidth: 600, marginBottom: 12 }}>
        <Search size={15} color="#6b7280" style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)' }} />
        <input
          className="glass-input mono"
          placeholder="Search by reference ID or SHA-256 hash..."
          value={q}
          onChange={e => setQ(e.target.value)}
          style={{ paddingLeft: 36 }}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: selected ? '1fr 340px' : '1fr', gap: 20, alignItems: 'flex-start' }}>
        <div className="glass-table-container">
          <table className="glass-table">
            <thead>
              <tr>
                <th>Reference ID</th>
                <th>Ingestion Time</th>
                <th>Source</th>
                <th>Size</th>
                <th>Integrity Hash</th>
                <th style={{ textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(v => (
                <tr key={v.refId} onClick={() => setSelectedRef(v.refId)} style={{ cursor: 'pointer' }}>
                  <td className="mono" style={{ fontWeight: 600 }}>{v.refId}</td>
                  <td className="mono" style={{ fontSize: 11 }}>{new Date(v.timestamp).toLocaleString()}</td>
                  <td style={{ fontSize: 12 }}>{v.source}</td>
                  <td style={{ fontSize: 12, color: '#6b7280' }}>{v.size}</td>
                  <td className="mono" style={{ fontSize: 11, color: '#6b7280', maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis' }} title={v.hash}>{v.hash}</td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 11 }}>View</button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>No records found matching search query.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {selected && (
          <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600 }}>Vault record</h3>
              <button className="btn btn-ghost" onClick={() => setSelectedRef(null)} style={{ padding: '2px 8px', fontSize: 12 }}>Close</button>
            </div>
            <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 2 }}>Reference ID</div>
            <div className="mono" style={{ fontSize: 14, marginBottom: 12 }}>{selected.refId}</div>
            <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 2 }}>SHA-256</div>
            <div className="mono" style={{ fontSize: 12, wordBreak: 'break-all', marginBottom: 12, color: '#057a55' }}>{selected.hash}</div>
            <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 4 }}>Original payload</div>
            <pre className="code-block" style={{ marginBottom: 12 }}>
              {selected.refId === 'raw-abc123'
                ? 'Sep 23 12:00:00 gateway-01 sshd[14512]: Failed password for admin from 203.0.113.15 port 48125 ssh2'
                : '{"time":"2026-09-23T12:01:15Z", "src":"192.168.1.5", "action":"DENY"}'}
            </pre>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#057a55', marginBottom: 12 }}>Block confirmed (tamper-proof)</div>
            <button className="btn btn-secondary" style={{ width: '100%' }}>
              <Download size={14} /> Download evidence (.zip)
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
