import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

export default function PlatformHealth() {
  const qc = useQueryClient()

  const { data: health } = useQuery({ queryKey: ['health'], queryFn: () => api.checkHealth() })
  const { data: pipeline } = useQuery({ queryKey: ['pipeline-health'], queryFn: () => api.getPipelineHealth() })
  const { data: checkpoint, isError: checkpointMissing } = useQuery({
    queryKey: ['latest-checkpoint'],
    queryFn: () => api.getLatestCheckpoint(),
    retry: false,
  })
  const { data: silent } = useQuery({ queryKey: ['silent-sources'], queryFn: () => api.getSilentSources() })

  const allOk = pipeline && (pipeline.parse_success_rate ?? 0) > 90 && (silent?.sources?.length ?? 0) === 0

  const stats = [
    { name: 'Ingestion rate (1h)', metric: pipeline ? `${pipeline.ingestion_rate} events` : '…', sub: pipeline ? `${pipeline.processing_rate} processed` : '' },
    { name: 'Parse success rate', metric: pipeline ? (pipeline.parse_success_rate != null ? `${pipeline.parse_success_rate}%` : 'n/a') : '…', sub: pipeline ? `${pipeline.dlq_count} in DLQ` : '' },
    { name: 'Avg. quality score', metric: pipeline ? `${pipeline.avg_quality_score}%` : '…', sub: pipeline ? `${pipeline.total_normalized_events} normalized events` : '' },
    { name: 'Queue lag', metric: pipeline ? `${pipeline.queue_lag} events` : '…', sub: pipeline ? `${pipeline.total_raw_events} raw events total` : '' },
  ]

  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <h1 className="page-title">
          Platform health
          <span className={`badge badge-${allOk ? 'success' : 'warning'}`} style={{ marginLeft: 8, verticalAlign: 'middle' }}>
            {health ? `${health.project} v${health.version}` : 'Connecting…'}
          </span>
        </h1>
        <p className="page-subtitle" style={{ margin: 0 }}>Live pipeline metrics from PostgreSQL, plus Merkle checkpoint status.</p>
      </div>

      <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap', padding: '4px 0 20px', marginBottom: 20, borderBottom: '1px solid #e5e7eb' }}>
        {stats.map(s => (
          <div key={s.name} style={{ minWidth: 180 }}>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 2 }}>{s.name}</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#111928' }}>{s.metric}</div>
            <div style={{ fontSize: 12, color: '#057a55' }}>{s.sub}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 20, marginBottom: 20 }}>
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div className="section-heading">Merkle checkpoint</div>
            <button
              className="btn btn-secondary"
              style={{ padding: '4px 10px', fontSize: 11 }}
              onClick={() => api.createCheckpoint().then(() => qc.invalidateQueries({ queryKey: ['latest-checkpoint'] }))}
            >
              Issue checkpoint
            </button>
          </div>
          {checkpointMissing || !checkpoint ? (
            <div style={{ color: '#6b7280', fontSize: 13 }}>No checkpoint issued yet -- ingest an event or click "Issue checkpoint".</div>
          ) : (
            <table className="glass-table">
              <tbody>
                <tr><td style={{ fontSize: 12, color: '#6b7280' }}>Tree size</td><td className="mono" style={{ fontSize: 12 }}>{checkpoint.tree_size}</td></tr>
                <tr><td style={{ fontSize: 12, color: '#6b7280' }}>Root hash</td><td className="mono" style={{ fontSize: 11, wordBreak: 'break-all' }}>{checkpoint.root_hash}</td></tr>
                <tr><td style={{ fontSize: 12, color: '#6b7280' }}>Signature valid</td><td>{checkpoint.signature_valid ? <span style={{ color: '#057a55' }}>Yes</span> : <span style={{ color: '#c81e1e' }}>No</span>}</td></tr>
                <tr><td style={{ fontSize: 12, color: '#6b7280' }}>Issued</td><td className="mono" style={{ fontSize: 12 }}>{new Date(checkpoint.created_at).toLocaleString()}</td></tr>
              </tbody>
            </table>
          )}
        </div>

        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
          <div className="section-heading" style={{ marginBottom: 12 }}>Silent sources</div>
          {(!silent?.sources || silent.sources.length === 0) ? (
            <div style={{ color: '#057a55', fontSize: 13 }}>All enabled sources reporting normally.</div>
          ) : (
            <table className="glass-table">
              <tbody>
                {silent.sources.map((s: any) => (
                  <tr key={s.source_id}>
                    <td style={{ fontSize: 13 }}>{s.source_name}</td>
                    <td className="mono" style={{ fontSize: 12, color: '#c81e1e', textAlign: 'right' }}>{s.silent_for_minutes}m silent</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="section-heading" style={{ marginBottom: 12 }}>Pipeline stages</div>
      <div className="glass-table-container">
        <table className="glass-table">
          <thead>
            <tr><th>Stage</th><th>Status</th><th>Metric</th></tr>
          </thead>
          <tbody>
            {(pipeline?.stages || []).map((stage: any) => (
              <tr key={stage.name}>
                <td>{stage.name}</td>
                <td><span className={`badge badge-${stage.status === 'healthy' ? 'success' : 'warning'}`}>{stage.status}</span></td>
                <td className="mono" style={{ fontSize: 12 }}>{stage.metric}</td>
              </tr>
            ))}
            {!pipeline && <tr><td colSpan={3} style={{ textAlign: 'center', color: '#6b7280' }}>Loading…</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}
