import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { DEMO_SOURCES } from '../data/demo'
import { Plus, Server, MoreHorizontal } from 'lucide-react'

export default function LogSources() {
  const { data: sourcesData } = useQuery({
    queryKey: ['sources'],
    queryFn: () => api.getSources(),
    retry: false
  })

  const sources = sourcesData?.length ? sourcesData : DEMO_SOURCES
  const healthy = sources.filter((s: any) => s.status === 'Healthy').length
  const warning = sources.filter((s: any) => s.status === 'Warning').length
  const failed = sources.filter((s: any) => s.status === 'Failed').length

  return (
    <div className="animate-fade-in" style={{ paddingBottom: 40 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <div>
          <h1 className="page-title">Data Sources</h1>
          <p className="page-subtitle" style={{ margin: 0 }}>Log ingestion pipelines, endpoints, and integrations</p>
        </div>
        <button className="btn btn-primary">
          <Plus size={16} /> Add Log Source
        </button>
      </div>

      <div style={{ display: 'flex', gap: 32, padding: '4px 0 20px', marginBottom: 20, borderBottom: '1px solid #e5e7eb' }}>
        {[
          { label: 'Total sources', value: sources.length },
          { label: 'Healthy', value: healthy },
          { label: 'Warning', value: warning },
          { label: 'Failed', value: failed },
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
              <th>Source Name</th>
              <th>Type</th>
              <th>Vendor</th>
              <th>Transport</th>
              <th>Parser</th>
              <th>Status</th>
              <th>Events/min</th>
              <th>Last Seen</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sources.map((s: any, i: number) => (
              <tr key={s.id || i}>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <Server size={15} color="#6b7280" />
                    <span style={{ fontWeight: 500 }}>{s.name}</span>
                  </div>
                </td>
                <td style={{ color: '#6b7280' }}>{s.type}</td>
                <td>{s.vendor}</td>
                <td><span className="badge badge-neutral">{s.transport}</span></td>
                <td><span className="mono" style={{ fontSize: 12 }}>{s.parser}</span></td>
                <td style={{ fontSize: 13 }}>{s.status}</td>
                <td><span className="mono" style={{ fontSize: 12 }}>{(s.eventsPerMin || 0).toLocaleString()}</span></td>
                <td style={{ color: '#6b7280', fontSize: 12 }}>{s.lastSeen}</td>
                <td>
                  <button className="btn btn-ghost" style={{ padding: 4 }}><MoreHorizontal size={16} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
