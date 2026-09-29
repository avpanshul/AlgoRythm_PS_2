import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

const EPISTEMIC_LABELS: Record<string, { label: string; color: string; description: string }> = {
  sufficient_evidence: { label: 'Sufficient evidence', color: '#057a55', description: 'Well-populated fields describing activity worth review' },
  evidence_of_absence: { label: 'Evidence of absence', color: '#1a56db', description: 'Well-populated fields describing routine/benign activity' },
  insufficient_data: { label: 'Insufficient data', color: '#c27803', description: 'Too sparse to conclude anything happened or didn\'t' },
  no_evidence: { label: 'No evidence (silent source)', color: '#c81e1e', description: 'Source has gone quiet -- nothing to evaluate' },
}

export default function DataQuality() {
  const { data: quality, isLoading: qLoading } = useQuery({
    queryKey: ['quality-summary'],
    queryFn: () => api.getQualitySummary(),
  })
  const { data: silent } = useQuery({
    queryKey: ['silent-sources'],
    queryFn: () => api.getSilentSources(),
  })
  const { data: volumeAnomalies } = useQuery({
    queryKey: ['volume-anomalies'],
    queryFn: () => api.getVolumeAnomalies(),
  })
  const { data: peerDeviation } = useQuery({
    queryKey: ['peer-deviation'],
    queryFn: () => api.getPeerDeviation(),
  })

  const bySource = quality?.by_source || []
  const epistemicDist: Record<string, number> = quality?.epistemic_distribution || {}
  const epistemicTotal = Object.values(epistemicDist).reduce((a: number, b: number) => a + b, 0)
  const silentSources = silent?.sources || []
  const anomalies = volumeAnomalies?.anomalies || []
  const deviations = peerDeviation?.deviations || []

  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <h1 className="page-title">Data quality & anomaly detection</h1>
        <p className="page-subtitle" style={{ margin: 0 }}>
          Per-source completeness, evidentiary weight (no-evidence / insufficient-data / evidence-of-absence / sufficient-evidence),
          silent sources, volume spikes, and peer-group deviation -- computed live from the pipeline, not simulated.
        </p>
      </div>

      <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap', padding: '4px 0 20px', marginBottom: 20, borderBottom: '1px solid #e5e7eb' }}>
        <div style={{ minWidth: 160 }}>
          <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 2 }}>Overall avg. quality</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: '#111928' }}>
            {qLoading ? '…' : quality?.overall_avg_quality != null ? `${quality.overall_avg_quality}%` : 'No data'}
          </div>
        </div>
        <div style={{ minWidth: 160 }}>
          <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 2 }}>Sources reporting</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: '#111928' }}>{bySource.length}</div>
        </div>
        <div style={{ minWidth: 160 }}>
          <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 2 }}>Silent sources</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: silentSources.length > 0 ? '#c81e1e' : '#111928' }}>{silentSources.length}</div>
        </div>
        <div style={{ minWidth: 160 }}>
          <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 2 }}>Volume anomalies (1h)</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: anomalies.length > 0 ? '#c27803' : '#111928' }}>{anomalies.length}</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 20, marginBottom: 20 }}>
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' }}>
          <div className="section-heading" style={{ padding: '12px 16px', borderBottom: '1px solid #e5e7eb' }}>Per-source quality</div>
          <table className="data-table">
            <thead>
              <tr><th>Source</th><th>Avg. quality</th><th>Events</th></tr>
            </thead>
            <tbody>
              {bySource.map((s: any) => (
                <tr key={s.source_id}>
                  <td style={{ fontWeight: 500, fontSize: 13 }}>{s.source_name}</td>
                  <td className="mono" style={{ fontSize: 12 }}>{s.avg_quality != null ? `${s.avg_quality}%` : '—'}</td>
                  <td style={{ fontSize: 13 }}>{s.event_count}</td>
                </tr>
              ))}
              {bySource.length === 0 && (
                <tr><td colSpan={3} style={{ textAlign: 'center', padding: 24, color: '#6b7280' }}>No normalized events yet</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
          <div className="section-heading" style={{ marginBottom: 12 }}>Epistemic data quality</div>
          {Object.keys(epistemicDist).length === 0 ? (
            <div style={{ color: '#6b7280', fontSize: 13 }}>No classified events yet.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {Object.entries(epistemicDist).map(([category, count]) => {
                const info = EPISTEMIC_LABELS[category] || { label: category, color: '#6b7280', description: '' }
                const pct = epistemicTotal ? Math.round((count / epistemicTotal) * 100) : 0
                return (
                  <div key={category}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                      <span style={{ fontWeight: 600, color: info.color }}>{info.label}</span>
                      <span className="mono">{count} ({pct}%)</span>
                    </div>
                    <div style={{ height: 6, borderRadius: 3, background: '#f3f4f6', overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${pct}%`, background: info.color }} />
                    </div>
                    <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>{info.description}</div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 20 }}>
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' }}>
          <div className="section-heading" style={{ padding: '12px 16px', borderBottom: '1px solid #e5e7eb' }}>Silent sources</div>
          <table className="data-table">
            <thead><tr><th>Source</th><th>Silent for</th><th>Last seen</th></tr></thead>
            <tbody>
              {silentSources.map((s: any) => (
                <tr key={s.source_id}>
                  <td style={{ fontSize: 13, fontWeight: 500 }}>{s.source_name}</td>
                  <td className="mono" style={{ fontSize: 12, color: '#c81e1e' }}>{s.silent_for_minutes}m</td>
                  <td style={{ fontSize: 12, color: '#6b7280' }}>{new Date(s.last_seen).toLocaleString()}</td>
                </tr>
              ))}
              {silentSources.length === 0 && (
                <tr><td colSpan={3} style={{ textAlign: 'center', padding: 24, color: '#6b7280' }}>No silent sources</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' }}>
          <div className="section-heading" style={{ padding: '12px 16px', borderBottom: '1px solid #e5e7eb' }}>Volume spikes / drops</div>
          <table className="data-table">
            <thead><tr><th>Source</th><th>Direction</th><th>z-score</th></tr></thead>
            <tbody>
              {anomalies.map((a: any, i: number) => (
                <tr key={i}>
                  <td style={{ fontSize: 13, fontWeight: 500 }}>{a.source_name}</td>
                  <td><span className={`badge badge-${a.direction === 'spike' ? 'warning' : 'danger'}`}>{a.direction}</span></td>
                  <td className="mono" style={{ fontSize: 12 }}>{a.z_score}</td>
                </tr>
              ))}
              {anomalies.length === 0 && (
                <tr><td colSpan={3} style={{ textAlign: 'center', padding: 24, color: '#6b7280' }}>No volume anomalies detected</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, overflow: 'hidden' }}>
          <div className="section-heading" style={{ padding: '12px 16px', borderBottom: '1px solid #e5e7eb' }}>Peer-group deviation</div>
          <table className="data-table">
            <thead><tr><th>Source</th><th>Peer group</th><th>z-score</th></tr></thead>
            <tbody>
              {deviations.map((d: any, i: number) => (
                <tr key={i}>
                  <td style={{ fontSize: 13, fontWeight: 500 }}>{d.source_name}</td>
                  <td style={{ fontSize: 12, color: '#6b7280' }}>{d.peer_group} ({d.peer_group_size})</td>
                  <td className="mono" style={{ fontSize: 12 }}>{d.z_score}</td>
                </tr>
              ))}
              {deviations.length === 0 && (
                <tr><td colSpan={3} style={{ textAlign: 'center', padding: 24, color: '#6b7280' }}>No peer-deviation outliers</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
