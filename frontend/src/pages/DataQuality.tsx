import { BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, Cell } from 'recharts'

const MOCK_SCORES = [
  { name: 'SRC-001 (HQ Edge Firewall)', score: 99.8, unmapped: 0, format: 'CEF', compliance: 100 },
  { name: 'SRC-002 (Data Center IDS)', score: 98.5, unmapped: 2, format: 'Syslog', compliance: 95 },
  { name: 'SRC-003 (Public Web Nginx)', score: 99.9, unmapped: 0, format: 'Apache/Nginx', compliance: 100 },
  { name: 'SRC-006 (Corporate Proxy)', score: 94.5, unmapped: 12, format: 'Plaintext', compliance: 85 },
  { name: 'SRC-008 (Payment API)', score: 0, unmapped: 45, format: 'JSON', compliance: 0 },
]

const CHART_DATA = [
  { metric: 'source.ip', score: 100 },
  { metric: 'destination.ip', score: 100 },
  { metric: 'event.action', score: 98 },
  { metric: 'user.name', score: 85 },
  { metric: 'network.protocol', score: 92 },
  { metric: 'event.outcome', score: 95 },
]

export default function DataQuality() {
  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <h1 className="page-title">Data quality & schema compliance</h1>
        <p className="page-subtitle" style={{ margin: 0 }}>
          How well parsed logs adhere to the ULPF canonical schema. High quality ensures accurate downstream detection.
        </p>
      </div>

      <div style={{ display: 'flex', gap: 32, padding: '4px 0 20px', marginBottom: 20, borderBottom: '1px solid #e5e7eb' }}>
        {[
          { label: 'Overall completeness', value: '96.4%', sub: '+2.1% vs last week' },
          { label: 'Unmapped fields', value: '59', sub: 'across 2 sources' },
          { label: 'Schema compliance', value: '98.2%', sub: 'strict schema match' },
        ].map(s => (
          <div key={s.label} style={{ minWidth: 160 }}>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 2 }}>{s.label}</div>
            <div style={{ fontSize: 24, fontWeight: 700, color: '#111928' }}>{s.value}</div>
            <div style={{ fontSize: 12, color: '#6b7280' }}>{s.sub}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 20 }}>
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid #e5e7eb', fontSize: 14, fontWeight: 600 }}>Source quality rankings</div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Score</th>
                <th>Unmapped</th>
              </tr>
            </thead>
            <tbody>
              {MOCK_SCORES.map(s => (
                <tr key={s.name}>
                  <td style={{ fontWeight: 500, fontSize: 13 }}>{s.name}</td>
                  <td className="mono" style={{ fontSize: 12 }}>{s.score}%</td>
                  <td style={{ fontSize: 13 }}>{s.unmapped === 0 ? <span style={{ color: '#057a55' }}>0</span> : <span style={{ color: '#c81e1e', fontWeight: 600 }}>{s.unmapped}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Canonical field extraction rate</div>
          <div style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={CHART_DATA} layout="vertical" margin={{ top: 0, right: 30, left: 40, bottom: 0 }}>
                <XAxis type="number" domain={[0, 100]} stroke="#6b7280" fontSize={11} tickFormatter={v => `${v}%`} />
                <YAxis dataKey="metric" type="category" stroke="#6b7280" fontSize={11} width={110} />
                <RechartsTooltip cursor={{ fill: '#f9fafb' }} contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 6, fontSize: 12 }} />
                <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={16}>
                  {CHART_DATA.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.score > 95 ? '#057a55' : entry.score > 90 ? '#1a56db' : '#c27803'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}
