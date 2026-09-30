import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import ForceGraph2D from 'react-force-graph-2d'
import { api } from '../api/client'
import { GlassCard } from '../components/glass/GlassCard'
import { Radar } from 'lucide-react'

export default function EntityGraph() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [pivot, setPivot] = useState<string | null>(params.get('entity'))
  const [selected, setSelected] = useState<any | null>(null)

  const { data, isError, isLoading } = useQuery({
    queryKey: ['graph', pivot],
    queryFn: () => api.getGraph(pivot ? { entity: pivot } : {}),
    retry: false,
  })

  const graphData = useMemo(() => {
    if (!data) return { nodes: [], links: [] }
    return {
      nodes: (data.nodes || []).map((n: any) => ({ id: n.id, risk: n.risk_score ?? 0, eventCount: n.event_count })),
      links: (data.edges || []).map((e: any) => ({ source: e.source, target: e.target, weight: e.weight, correlationIds: e.correlation_ids })),
    }
  }, [data])

  // Entity Behavior (Sentinel per-entity risk baselines) -- merged into this
  // page since Entity Graph's own nodes are colored by this exact data;
  // showing the underlying table right below the graph it colors, instead
  // of on a separate page, keeps the one real dataset in one place.
  const { data: behaviorData, isLoading: behaviorLoading } = useQuery({
    queryKey: ['entities'], queryFn: () => api.getEntities({ size: 50, sort: 'risk_score', order: 'desc' }),
  })
  const behaviorItems = behaviorData?.items || []

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 'clamp(40px, 4vw, 52px)', fontWeight: 800, color: '#0044A8', letterSpacing: '-0.03em', lineHeight: 1.1 }}>Entity Behavior &amp; Graph</h1>
          <p style={{ fontSize: 13, color: '#8999b0', marginTop: 3 }}>
            Real source→destination IP relationships, colored by each entity's real Sentinel behavioral risk score -- click a node to inspect, right-click to pivot.
            The full per-entity risk table (same real data) is below the graph.
          </p>
        </div>
        {pivot && <button onClick={() => setPivot(null)} style={{ padding: '8px 16px', borderRadius: 8, background: 'rgba(0,68,168,0.08)', border: 'none', color: '#0044A8', fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>Clear pivot ({pivot})</button>}
      </header>

      {isError && <div style={{ color: '#c81e1e', fontSize: 13 }}>Could not load the graph.</div>}
      {!isError && !isLoading && graphData.nodes.length === 0 && (
        <GlassCard style={{ padding: 40, textAlign: 'center' }}>
          {pivot ? (
            <p style={{ color: '#8999b0', fontSize: 13 }}>
              <strong style={{ color: '#0a0e27' }}>{pivot}</strong> has real behavioral data (see the table below), but none of its events
              have both a source IP and a destination IP recorded together -- so there's no real source→destination pair to draw as a
              graph edge for it. This isn't an error or missing data; the graph only shows entities with a real paired connection.
            </p>
          ) : (
            <p style={{ color: '#8999b0', fontSize: 13 }}>No source/destination IP pairs in stored events yet -- built entirely from real data, nothing fabricated to fill this view.</p>
          )}
        </GlassCard>
      )}

      {graphData.nodes.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: selected ? '1fr 320px' : '1fr', gap: 16 }}>
          <GlassCard style={{ padding: 0, overflow: 'hidden', height: 420 }}>
            <ForceGraph2D
              graphData={graphData}
              nodeId="id"
              nodeLabel={(n: any) => `${n.id}${n.risk ? ` — risk ${n.risk}` : ''}`}
              nodeColor={(n: any) => n.risk >= 30 ? '#c81e1e' : n.risk > 0 ? '#d97706' : '#8999b0'}
              nodeRelSize={5}
              linkWidth={(l: any) => Math.min(4, 1 + Math.log2(1 + (l.weight || 1)))}
              linkColor={(l: any) => (l.correlationIds && l.correlationIds.length > 0) ? '#c81e1e' : '#d1d5db'}
              linkDirectionalArrowLength={4}
              onNodeClick={(n: any) => setSelected(n)}
              onNodeRightClick={(n: any) => setPivot(n.id)}
              height={420}
            />
          </GlassCard>
          {selected && (
            <GlassCard style={{ padding: 20 }}>
              <div className="mono" style={{ fontSize: 14, fontWeight: 700, marginBottom: 8, color: '#0a0e27' }}>{selected.id}</div>
              <div style={{ fontSize: 12, color: '#5b6382', marginBottom: 4 }}>Sentinel risk score: {selected.risk ?? 'no profile yet'}</div>
              <div style={{ fontSize: 12, color: '#5b6382', marginBottom: 16 }}>Events profiled: {selected.eventCount ?? '—'}</div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={() => setPivot(selected.id)} style={{ padding: '8px 14px', borderRadius: 8, background: '#0044A8', color: '#fff', border: 'none', fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>Pivot here</button>
                <button onClick={() => navigate(`/attack-path?entity=${encodeURIComponent(selected.id)}`)} style={{ padding: '8px 14px', borderRadius: 8, background: 'rgba(0,68,168,0.08)', border: 'none', color: '#0044A8', fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>View attack path</button>
              </div>
            </GlassCard>
          )}
        </div>
      )}
      <div style={{ fontSize: 11, color: '#b0bace' }}>Right-click a node to pivot to its neighborhood. Red edges matched a correlation rule.</div>

      {/* Entity Behavior table -- below the graph, per request */}
      <h2 className="section-heading" style={{ marginTop: 8 }}>Entity Behavior (Sentinel risk baselines)</h2>
      <GlassCard style={{ padding: 0, overflow: 'hidden' }}>
        {behaviorLoading ? (
          <div style={{ padding: 32, textAlign: 'center', color: '#8999b0' }}>Loading…</div>
        ) : behaviorItems.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <Radar size={28} color="#c0cde3" style={{ marginBottom: 8 }} />
            <p style={{ fontSize: 13, color: '#8999b0', fontWeight: 500 }}>No entity profiles yet.</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
            <thead>
              <tr style={{ background: 'rgba(0,68,168,0.03)', borderBottom: '1px solid rgba(0,68,168,0.1)', color: '#5b6382' }}>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Entity</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Risk Score</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Events</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Known Ports</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Known Peers</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Last Seen</th>
                <th style={{ padding: '12px 16px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {behaviorItems.map((e: any) => (
                <tr key={e.entity_id} style={{ borderBottom: '1px solid rgba(0,68,168,0.05)' }}>
                  <td style={{ padding: '14px 16px', fontWeight: 600, color: '#0a0e27', fontFamily: 'monospace' }}>{e.entity_id}</td>
                  <td style={{ padding: '14px 16px' }}>
                    <span style={{ fontWeight: 700, color: e.risk_score >= 80 ? '#c81e1e' : e.risk_score >= 40 ? '#d97706' : '#057a55' }}>{e.risk_score}</span>
                  </td>
                  <td style={{ padding: '14px 16px', color: '#5b6382' }}>{e.event_count}</td>
                  <td style={{ padding: '14px 16px', color: '#5b6382' }}>{e.known_dest_port_count}</td>
                  <td style={{ padding: '14px 16px', color: '#5b6382' }}>{e.known_peer_count}</td>
                  <td style={{ padding: '14px 16px', color: '#5b6382', fontSize: 11 }}>{e.last_event_at ? new Date(e.last_event_at).toLocaleString() : '—'}</td>
                  <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                    <button onClick={() => setPivot(e.entity_id)} style={{ fontSize: 12, fontWeight: 600, color: '#0044A8', background: 'none', border: 'none', cursor: 'pointer' }}>Pivot graph to this →</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </GlassCard>
    </div>
  )
}
