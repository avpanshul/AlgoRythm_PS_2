import { useState, Fragment } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { RotateCw, Search, Wand2 } from 'lucide-react'
import { api } from '../api/client'

function UnknownClustersPanel() {
  const qc = useQueryClient()
  const { data: clusters, isLoading, isError } = useQuery({ queryKey: ['unknown-clusters'], queryFn: () => api.getUnknownClusters() })
  const [drafting, setDrafting] = useState<string | null>(null)
  const [draftResult, setDraftResult] = useState<Record<string, any>>({})

  const clusterList: any[] = Array.isArray(clusters) ? clusters : []

  const draftPack = (clusterId: string) => {
    setDrafting(clusterId)
    api.draftPackForCluster(clusterId)
      .then((res: any) => setDraftResult(prev => ({ ...prev, [clusterId]: res })))
      .catch((e: any) => setDraftResult(prev => ({ ...prev, [clusterId]: { status: 'error', detail: e?.response?.data?.detail || e?.message || 'Draft failed.' } })))
      .finally(() => { setDrafting(null); qc.invalidateQueries({ queryKey: ['dlq-page'] }) })
  }

  if (isLoading) return <div style={{ padding: 20, color: '#8999b0', fontSize: 13 }}>Loading unknown-format clusters…</div>
  if (isError) return <div style={{ padding: 20, color: '#c81e1e', fontSize: 13 }}>Could not reach the backend to load unknown-format clusters.</div>
  if (clusterList.length === 0) return null

  return (
    <div className="glass-table-container" style={{ marginBottom: 20 }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h3 className="section-heading">Unknown-format clusters ({clusterList.length})</h3>
        <span style={{ fontSize: 11, color: '#8999b0' }}>Real Drain3 grouping of DLQ events with no known parser -- draft a pack, then a real human must approve it before it's trusted.</span>
      </div>
      <table className="glass-table">
        <thead>
          <tr><th>Cluster</th><th>Template</th><th>Event count</th><th style={{ textAlign: 'right' }}>Action</th></tr>
        </thead>
        <tbody>
          {clusterList.map(c => {
            const result = draftResult[c.cluster_id]
            return (
              <Fragment key={c.cluster_id}>
                <tr>
                  <td className="mono" style={{ fontSize: 12 }}>{c.cluster_id}</td>
                  <td>
                    <code className="mono" style={{ fontSize: 11, maxWidth: 340, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={c.template_str}>
                      {c.template_str}
                    </code>
                  </td>
                  <td className="mono" style={{ fontSize: 12 }}>{c.event_count}</td>
                  <td style={{ textAlign: 'right', display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                    <button
                      className="btn btn-primary" style={{ padding: '4px 10px', fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 4 }}
                      onClick={() => draftPack(c.cluster_id)} disabled={drafting === c.cluster_id}
                    >
                      <Wand2 size={12} /> {drafting === c.cluster_id ? 'Drafting…' : 'Draft pack'}
                    </button>
                  </td>
                </tr>
                {result && (
                  <tr>
                    <td colSpan={4} style={{ fontSize: 11, padding: '6px 16px', background: result.status === 'error' ? 'rgba(200,30,30,0.05)' : 'rgba(5,122,85,0.05)', color: result.status === 'error' ? '#c81e1e' : '#057a55' }}>
                      {result.status === 'error'
                        ? `Draft failed: ${typeof result.detail === 'string' ? result.detail : JSON.stringify(result.detail)}`
                        : `Drafted parser ${result.parser_id} -- ${result.mapped_field_count} mapped / ${result.unmapped_field_count} unmapped field(s). Review and publish it in Parser Lab.`}
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function FailedEvents() {
  const qc = useQueryClient()
  const [q, setQ] = useState('')

  const { data, isLoading, isError } = useQuery({
    queryKey: ['dlq-page'],
    // Real bug found live: with no status filter, GET /dlq counts every row
    // ever written, including ones already retried successfully (status
    // "resolved") -- so "Total Failed Events" showed 12,205 (19 still-failed
    // + 12,186 resolved history) instead of the real, current failure count.
    // "Failed Events / DLQ" means currently-unresolved failures, so filter
    // to that explicitly rather than the full historical total.
    queryFn: () => api.getDlq({ size: 100, status: 'failed' }),
    retry: false,
  })

  const items: any[] = data?.items || []
  const filtered = items.filter(e =>
    !q || (e.raw_log || '').toLowerCase().includes(q.toLowerCase()) || (e.failure_reason || '').toLowerCase().includes(q.toLowerCase())
  )

  const retry = (id: number) => api.retryDlq(id).then(() => qc.invalidateQueries({ queryKey: ['dlq-page'] }))

  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <div>
          <h1 className="page-title">Failed events / DLQ</h1>
          <p className="page-subtitle" style={{ margin: 0 }}>Events that failed parsing or normalization, queued for review and reprocessing.</p>
        </div>
      </div>

      <UnknownClustersPanel />

      <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 300 }}>
          <Search size={15} color="#6b7280" style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)' }} />
          <input className="glass-input" placeholder="Search raw logs or errors..." style={{ paddingLeft: 36 }} value={q} onChange={e => setQ(e.target.value)} />
        </div>
      </div>

      <div className="glass-table-container">
        <table className="glass-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Source</th>
              <th>Raw Snippet</th>
              <th>Failure Reason</th>
              <th>Drain3 Cluster</th>
              <th style={{ textAlign: 'right' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(evt => (
              <tr key={evt.id}>
                <td className="mono" style={{ fontSize: 11 }}>{evt.created_at ? new Date(evt.created_at).toLocaleString() : '—'}</td>
                <td style={{ fontSize: 12 }}>{evt.source_id || 'UNKNOWN'}</td>
                <td>
                  <code className="mono" style={{ fontSize: 11, maxWidth: 300, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={evt.raw_log}>
                    {evt.raw_log}
                  </code>
                </td>
                <td style={{ fontSize: 12, color: '#c81e1e' }}>{evt.failure_reason}{evt.failure_detail ? `: ${evt.failure_detail}` : ''}</td>
                <td className="mono" style={{ fontSize: 12 }}>{evt.drain_cluster_id || '—'}</td>
                <td style={{ textAlign: 'right' }}>
                  <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 11 }} onClick={() => retry(evt.id)}>
                    <RotateCw size={12} /> Retry
                  </button>
                </td>
              </tr>
            ))}
            {isLoading && (
              <tr><td colSpan={6} style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>Loading…</td></tr>
            )}
            {isError && (
              <tr><td colSpan={6} style={{ textAlign: 'center', padding: 40, color: '#c81e1e' }}>Could not load the DLQ -- check that you're signed in and the backend is reachable.</td></tr>
            )}
            {!isLoading && !isError && filtered.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>Dead Letter Queue is empty.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
