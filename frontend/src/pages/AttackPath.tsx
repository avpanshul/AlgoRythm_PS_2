import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Eye, Zap, Clock, Route as RouteIcon, Search } from 'lucide-react'
import { api } from '../api/client'
import { GlassCard } from '../components/glass/GlassCard'

const SEVERITY_COLOR: Record<string, string> = { critical: '#c81e1e', high: '#c81e1e', medium: '#d97706', low: '#8999b0' }
const triggerLabel: Record<string, string> = {
  correlated_incident: 'Correlated incident',
  risk_threshold: 'Risk threshold crossed',
}

export default function AttackPath() {
  const [params] = useSearchParams()

  const [mode, setMode] = useState<'entity' | 'incident'>(params.get('incident_id') ? 'incident' : 'entity')
  const [entityInput, setEntityInput] = useState(params.get('entity') || '')
  const [incidentInput, setIncidentInput] = useState(params.get('incident_id') || '')
  const [queriedEntity, setQueriedEntity] = useState<string | null>(params.get('entity'))
  const [queriedIncident, setQueriedIncident] = useState<string | null>(params.get('incident_id'))
  const [view, setView] = useState<'path' | 'timeline'>(params.get('incident_id') ? 'timeline' : 'path')
  const [sparkReason, setSparkReason] = useState<{ entity: string; reason: string; trigger_type: string } | null>(null)

  const { data: sparks, isLoading: sparksLoading } = useQuery({ queryKey: ['sparks'], queryFn: () => api.getSparks() })
  const sparkList: any[] = Array.isArray(sparks) ? sparks : []

  const { data: pathData, isError: pathError, isLoading: pathLoading } = useQuery({
    queryKey: ['attack-path', queriedEntity],
    queryFn: () => api.getAttackPath(queriedEntity as string),
    enabled: mode === 'entity' && !!queriedEntity,
    retry: false,
  })

  const timelineParams = mode === 'incident' ? (queriedIncident ? { incident_id: queriedIncident } : null) : (queriedEntity ? { entity: queriedEntity } : null)
  const { data: timelineData, isError: timelineError, isLoading: timelineLoading } = useQuery({
    queryKey: ['timeline', timelineParams],
    queryFn: () => api.getTimeline(timelineParams as any),
    enabled: !!timelineParams,
    retry: false,
  })

  const runEntity = (entity: string, fromSpark?: any) => {
    setMode('entity')
    setEntityInput(entity)
    setQueriedEntity(entity)
    setQueriedIncident(null)
    setView('path')
    setSparkReason(fromSpark ? { entity: fromSpark.entity, reason: fromSpark.reason, trigger_type: fromSpark.trigger_type } : null)
  }
  const runIncident = (incidentId: string) => {
    setMode('incident')
    setIncidentInput(incidentId)
    setQueriedIncident(incidentId)
    setQueriedEntity(null)
    setView('timeline')
    setSparkReason(null)
  }
  const submitSearch = () => {
    if (mode === 'entity' && entityInput.trim()) runEntity(entityInput.trim())
    if (mode === 'incident' && incidentInput.trim()) runIncident(incidentInput.trim())
  }

  // Re-sync from URL if it changes externally (e.g. a link from Entity Graph or Alerts)
  useEffect(() => {
    const e = params.get('entity')
    const inc = params.get('incident_id')
    if (e) runEntity(e)
    else if (inc) runIncident(inc)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.get('entity'), params.get('incident_id')])

  const hasQuery = mode === 'entity' ? !!queriedEntity : !!queriedIncident

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <header>
        <h1 style={{ fontSize: 'clamp(40px, 4vw, 52px)', fontWeight: 800, color: '#0044A8', letterSpacing: '-0.03em', lineHeight: 1.1 }}>Attack Path</h1>
        <p style={{ fontSize: 13, color: '#8999b0', marginTop: 3 }}>
          Real, explainable starting points (Sparks) → the real, time-ordered path and chronological timeline they lead to.
          Advisory only: shows what actually happened, never a prediction of what happens next.
        </p>
      </header>

      {/* Sparks: real, explainable entry points into an investigation */}
      <GlassCard style={{ padding: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <Zap size={16} color="#0044A8" />
          <span className="section-heading">Sparks</span>
          <span style={{ fontSize: 11, color: '#8999b0' }}>-- explicit trigger reasons: a newly-opened correlated incident, or a risk-threshold crossing</span>
        </div>
        {sparksLoading ? (
          <div style={{ fontSize: 12, color: '#8999b0' }}>Loading sparks…</div>
        ) : sparkList.length === 0 ? (
          <div style={{ fontSize: 12, color: '#8999b0' }}>No sparks yet -- either detection is disabled, or nothing has crossed a real trigger yet.</div>
        ) : (
          <div style={{ display: 'flex', gap: 10, overflowX: 'auto', paddingBottom: 4 }}>
            {sparkList.map(s => (
              <button
                key={s.id}
                onClick={() => runEntity(s.entity, s)}
                style={{
                  flexShrink: 0, textAlign: 'left', minWidth: 220, padding: '10px 14px', borderRadius: 12, cursor: 'pointer',
                  border: sparkReason?.entity === s.entity && queriedEntity === s.entity ? '1.5px solid #0044A8' : '1px solid rgba(0,68,168,0.12)',
                  background: sparkReason?.entity === s.entity && queriedEntity === s.entity ? 'rgba(0,68,168,0.06)' : '#fff',
                  transition: 'all 0.15s ease',
                }}
              >
                <div className="mono" style={{ fontSize: 12, fontWeight: 700, color: '#0a0e27', marginBottom: 4 }}>{s.entity}</div>
                <span className={`badge ${s.trigger_type === 'risk_threshold' ? 'badge-warning' : 'badge-danger'}`} style={{ marginBottom: 4 }}>
                  {triggerLabel[s.trigger_type] || s.trigger_type}
                </span>
                <div style={{ fontSize: 11, color: '#8999b0', marginTop: 4 }}>{s.hop_count} hop{s.hop_count === 1 ? '' : 's'} · {s.detected_at ? new Date(s.detected_at).toLocaleString() : '—'}</div>
              </button>
            ))}
          </div>
        )}
      </GlassCard>

      {/* Search: trace any entity or incident directly */}
      <GlassCard style={{ padding: '12px 16px', display: 'flex', gap: 8, alignItems: 'center' }}>
        <select
          value={mode}
          onChange={e => { setMode(e.target.value as any); setSparkReason(null) }}
          style={{ border: 'none', background: 'rgba(0,68,168,0.06)', borderRadius: 8, padding: '8px 10px', fontSize: 13, fontWeight: 600, color: '#0044A8' }}
        >
          <option value="entity">By entity</option>
          <option value="incident">By incident</option>
        </select>
        <Search size={16} color="#8999b0" />
        {mode === 'entity' ? (
          <input
            className="mono" placeholder="Entity (IP address) to trace" value={entityInput}
            onChange={e => setEntityInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && submitSearch()}
            style={{ flex: 1, border: 'none', background: 'transparent', outline: 'none', fontSize: 14, color: '#0a0e27' }}
          />
        ) : (
          <input
            className="mono" placeholder="Correlation / incident ID" value={incidentInput}
            onChange={e => setIncidentInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && submitSearch()}
            style={{ flex: 1, border: 'none', background: 'transparent', outline: 'none', fontSize: 14, color: '#0a0e27' }}
          />
        )}
        <button
          onClick={submitSearch}
          disabled={mode === 'entity' ? !entityInput.trim() : !incidentInput.trim()}
          style={{ padding: '8px 20px', borderRadius: 8, background: '#0044A8', color: '#fff', border: 'none', fontWeight: 600, fontSize: 13, cursor: 'pointer' }}
        >
          Trace
        </button>
      </GlassCard>

      {!hasQuery && (
        <div style={{ color: '#8999b0', fontSize: 13 }}>Click a spark above, or enter an entity/incident to trace its real path and timeline.</div>
      )}

      {hasQuery && (
        <>
          {sparkReason && (
            <GlassCard style={{ padding: '14px 20px', background: 'rgba(0,68,168,0.03)', border: '1px solid rgba(0,68,168,0.12)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <Zap size={14} color="#0044A8" />
                <span style={{ fontSize: 12, fontWeight: 700, color: '#0044A8', textTransform: 'uppercase', letterSpacing: '0.03em' }}>Why this is a spark</span>
              </div>
              <p style={{ fontSize: 13, color: '#5b6382', lineHeight: 1.5, margin: 0 }}>{sparkReason.reason}</p>
            </GlassCard>
          )}

          {/* View tabs -- Path only makes sense for an entity; Timeline works for both */}
          <div style={{ display: 'flex', gap: 8, background: 'rgba(0,68,168,0.05)', padding: 4, borderRadius: 12, width: 'fit-content' }}>
            {mode === 'entity' && (
              <button
                onClick={() => setView('path')}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6, padding: '6px 16px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
                  background: view === 'path' ? '#fff' : 'transparent', color: view === 'path' ? '#0044A8' : '#5b6382',
                  boxShadow: view === 'path' ? '0 2px 8px rgba(0,68,168,0.1)' : 'none', transition: 'all 0.2s',
                }}
              >
                <RouteIcon size={14} /> Path
              </button>
            )}
            <button
              onClick={() => setView('timeline')}
              style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '6px 16px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
                background: view === 'timeline' ? '#fff' : 'transparent', color: view === 'timeline' ? '#0044A8' : '#5b6382',
                boxShadow: view === 'timeline' ? '0 2px 8px rgba(0,68,168,0.1)' : 'none', transition: 'all 0.2s',
              }}
            >
              <Clock size={14} /> Timeline
            </button>
          </div>

          {view === 'path' && mode === 'entity' && (
            <>
              {pathError && <div style={{ color: '#c81e1e', fontSize: 13 }}>Could not load the attack path.</div>}
              {pathLoading && <div style={{ color: '#8999b0', fontSize: 13 }}>Loading path…</div>}
              {pathData && (
                <>
                  <GlassCard style={{ padding: 24 }}>
                    {pathData.path.length === 0 && (
                      <div style={{ color: '#8999b0', fontSize: 13, marginBottom: 12 }}>No forward-time chain found from this entity in currently-stored events.</div>
                    )}
                    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
                      <span className="mono" style={{ padding: '4px 10px', borderRadius: 8, background: 'rgba(0,68,168,0.08)', color: '#0044A8', fontSize: 12, fontWeight: 700 }}>{queriedEntity}</span>
                      {pathData.path.map((hop: any, i: number) => (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <ArrowRight size={16} color="#8999b0" />
                          <div style={{ textAlign: 'center' }}>
                            <span
                              className="mono"
                              style={{
                                padding: '4px 10px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                                background: hop.correlation_id ? 'rgba(200,30,30,0.1)' : 'rgba(0,68,168,0.08)',
                                color: hop.correlation_id ? '#c81e1e' : '#0044A8',
                              }}
                            >
                              {hop.to}
                            </span>
                            <div style={{ fontSize: 10, color: '#b0bace', marginTop: 2 }}>{hop.at ? new Date(hop.at).toLocaleString() : ''}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div style={{ fontSize: 11, color: '#8999b0', marginTop: 12 }}>Current front: <span className="mono" style={{ fontWeight: 600 }}>{pathData.front}</span></div>
                  </GlassCard>

                  <GlassCard style={{ padding: 20 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6, color: '#0a0e27' }}>
                      <Eye size={14} /> Worth watching (proximity-based, not predictive)
                    </div>
                    <div style={{ fontSize: 11, color: '#8999b0', marginBottom: 10 }}>{pathData.proximity_note}</div>
                    {pathData.proximity_watchlist.length === 0 ? (
                      <div style={{ color: '#b0bace', fontSize: 12 }}>Nothing else in the same /24.</div>
                    ) : (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        {pathData.proximity_watchlist.map((ip: string) => (
                          <button
                            key={ip} onClick={() => runEntity(ip)}
                            className="mono"
                            style={{ padding: '2px 8px', borderRadius: 8, fontSize: 12, fontWeight: 600, background: 'rgba(217,119,6,0.1)', color: '#d97706', border: 'none', cursor: 'pointer' }}
                          >
                            {ip}
                          </button>
                        ))}
                      </div>
                    )}
                  </GlassCard>
                </>
              )}
            </>
          )}

          {view === 'timeline' && (
            <>
              {timelineError && <div style={{ color: '#c81e1e', fontSize: 13 }}>Could not load the timeline.</div>}
              {timelineLoading && <div style={{ color: '#8999b0', fontSize: 13 }}>Loading timeline…</div>}
              {timelineData && timelineData.mode === 'incident' && timelineData.found === false && (
                <div style={{ color: '#c81e1e', fontSize: 13 }}>No incident found with that ID.</div>
              )}
              {timelineData && timelineData.found !== false && (
                <GlassCard style={{ padding: 20 }}>
                  {timelineData.mode === 'incident' && (
                    <div style={{ fontSize: 12, color: '#5b6382', marginBottom: 12 }}>
                      Rule: <strong>{timelineData.rule_name}</strong> · Status: <span style={{ padding: '2px 8px', borderRadius: 8, background: 'rgba(0,68,168,0.08)', color: '#0044A8', fontSize: 11 }}>{timelineData.status}</span>
                    </div>
                  )}
                  {timelineData.events.length === 0 ? (
                    <div style={{ color: '#8999b0', fontSize: 13 }}>No real events found for this {timelineData.mode}.</div>
                  ) : (
                    <div style={{ position: 'relative', paddingLeft: 20 }}>
                      <div style={{ position: 'absolute', left: 5, top: 6, bottom: 6, width: 2, background: 'rgba(0,68,168,0.1)' }} />
                      {timelineData.events.map((evt: any) => (
                        <div key={evt.event_id} style={{ position: 'relative', marginBottom: 16 }}>
                          <div style={{ position: 'absolute', left: -20, top: 4, width: 10, height: 10, borderRadius: '50%', background: '#0044A8', border: '2px solid #fff' }} />
                          <div style={{ border: '1px solid rgba(0,68,168,0.08)', borderRadius: 10, padding: 12, background: 'rgba(255,255,255,0.5)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#8999b0' }}>
                                <Clock size={12} /> {evt.timestamp ? new Date(evt.timestamp).toLocaleString() : 'unknown time'}
                              </div>
                              {evt.severity && (
                                <span style={{ padding: '2px 8px', borderRadius: 8, fontSize: 10, fontWeight: 700, background: `${SEVERITY_COLOR[String(evt.severity).toLowerCase()] || '#8999b0'}18`, color: SEVERITY_COLOR[String(evt.severity).toLowerCase()] || '#8999b0' }}>{evt.severity}</span>
                              )}
                            </div>
                            <div style={{ fontSize: 13, marginBottom: 4, color: '#0a0e27' }}>
                              {evt.category && <span style={{ fontWeight: 600 }}>{evt.category}</span>}
                              {evt.action && <span style={{ color: '#5b6382' }}> — {evt.action}</span>}
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                              {evt.source_ip && (
                                <button onClick={() => runEntity(evt.source_ip)} className="mono" style={{ padding: '2px 8px', borderRadius: 8, background: 'rgba(0,68,168,0.06)', fontSize: 11, border: 'none', cursor: 'pointer' }}>src {evt.source_ip}</button>
                              )}
                              {evt.dest_ip && (
                                <button onClick={() => runEntity(evt.dest_ip)} className="mono" style={{ padding: '2px 8px', borderRadius: 8, background: 'rgba(0,68,168,0.06)', fontSize: 11, border: 'none', cursor: 'pointer' }}>dst {evt.dest_ip}</button>
                              )}
                              {evt.user_name && <span className="mono" style={{ padding: '2px 8px', borderRadius: 8, background: 'rgba(0,68,168,0.06)', fontSize: 11 }}>user {evt.user_name}</span>}
                              {evt.correlation_id && (
                                <button onClick={() => runIncident(evt.correlation_id)} className="mono" style={{ padding: '2px 8px', borderRadius: 8, background: 'rgba(200,30,30,0.08)', color: '#c81e1e', fontSize: 11, border: 'none', cursor: 'pointer' }}>corr {evt.correlation_id.slice(0, 8)}</button>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {timelineData.truncated && <div style={{ fontSize: 11, color: '#b0bace', marginTop: 8 }}>Truncated at the query limit.</div>}
                </GlassCard>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
