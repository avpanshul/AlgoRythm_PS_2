export default function PlatformHealth() {
  const services = [
    { name: 'Message queue (Kafka)', metric: '45,210 EPS', sub: 'consumer lag < 50 ms', ok: true },
    { name: 'Parser fleet', metric: '12 / 12 nodes', sub: 'avg 12 ms / event', ok: true },
    { name: 'Search API (OpenSearch)', metric: '120 ms p99', sub: '45 active queries', ok: true },
    { name: 'Storage (vault)', metric: '45% of 100 TB', sub: 'daily snapshot ok', ok: true },
  ]

  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <h1 className="page-title">Platform health <span className="badge badge-success" style={{ marginLeft: 8, verticalAlign: 'middle' }}>All systems operational</span></h1>
        <p className="page-subtitle" style={{ margin: 0 }}>Backend services, ingestion queues, and storage clusters.</p>
      </div>

      <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap', padding: '4px 0 20px', marginBottom: 20, borderBottom: '1px solid #e5e7eb' }}>
        {services.map(s => (
          <div key={s.name} style={{ minWidth: 180 }}>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 2 }}>{s.name}</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#111928' }}>{s.metric}</div>
            <div style={{ fontSize: 12, color: '#057a55' }}>{s.sub}</div>
          </div>
        ))}
      </div>

      <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>System events</div>
      <div className="glass-table-container">
        <table className="glass-table">
          <thead>
            <tr><th>Time</th><th>Component</th><th>Level</th><th>Message</th></tr>
          </thead>
          <tbody>
            <tr><td className="mono" style={{ fontSize: 11 }}>12:00:00</td><td>Parser Fleet</td><td><span className="badge badge-success">Info</span></td><td>Auto-scaled up to 12 nodes</td></tr>
            <tr><td className="mono" style={{ fontSize: 11 }}>11:45:22</td><td>Kafka Broker 3</td><td><span className="badge badge-warning">Warn</span></td><td>High memory utilization (85%)</td></tr>
            <tr><td className="mono" style={{ fontSize: 11 }}>10:00:00</td><td>Vault Backup</td><td><span className="badge badge-success">Info</span></td><td>Daily snapshot completed successfully</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
