import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { GlassCard } from '../components/glass/GlassCard'
import { Plus, Server, Database, Activity, Settings, RefreshCw, Terminal, Filter } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { anonymizedVendorLabel, displaySourceName } from '../utils/anonymize'

export default function LogSources() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState('')
  const { data: sourcesData, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['sources'],
    queryFn: () => api.getSources(),
    retry: 2,
  })

  const allSources: any[] = Array.isArray(sourcesData) ? sourcesData : []
  const activeCount = allSources.filter(s => s.enabled).length

  // retry: 2 -- real bug reported live: a single transient fetch failure on
  // this call (no retry previously) left eventCountBySource empty for the
  // rest of the session, since nothing here re-triggers it -- every card
  // silently showed "0 total" even though the real backend had the data,
  // with no visible error to explain why.
  const { data: qualitySummary } = useQuery({ queryKey: ['quality-summary'], queryFn: () => api.getQualitySummary(), retry: 2 })
  const eventCountBySource: Record<string, number> = {}
  for (const s of qualitySummary?.by_source || []) eventCountBySource[s.source_id] = s.event_count
  const totalEventsIngested = Object.values(eventCountBySource).reduce((a, b) => a + b, 0)

  // Real client-side filter (was a decorative input with no handler at
  // all): matches against the source's real id/name/device_type, not the
  // anonymized vendor label, since filtering by a randomized display label
  // wouldn't be useful.
  const sources = useMemo(() => {
    const f = filter.trim().toLowerCase()
    if (!f) return allSources
    return allSources.filter(s =>
      (s.name || '').toLowerCase().includes(f) ||
      (s.id || '').toLowerCase().includes(f) ||
      (s.device_type || '').toLowerCase().includes(f)
    )
  }, [allSources, filter])

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 'clamp(40px, 4vw, 52px)', fontWeight: 800, color: '#0044A8', letterSpacing: '-0.03em', lineHeight: 1.1 }}>
            Data Sources
          </h1>
          <p style={{ fontSize: 'clamp(12px, 0.85vw, 13px)', color: '#8999b0', marginTop: 3 }}>
            {sources.length > 0 ? `${activeCount} active of ${sources.length} total sources` : 'Configured ingestion connectors & feeds'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <button style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', borderRadius: 10,
            background: 'rgba(0,68,168,0.05)', border: '1px solid rgba(0,68,168,0.15)',
            color: '#0044A8', fontWeight: 600, fontSize: 13, cursor: isFetching ? 'default' : 'pointer', opacity: isFetching ? 0.6 : 1,
          }} onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} /> {isFetching ? 'Refreshing…' : 'Refresh'}
          </button>
          <Link to="/add-source" style={{ textDecoration: 'none' }}>
            <button style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', borderRadius: 10,
              background: 'linear-gradient(135deg, #0044A8, #0088FF)', border: 'none',
              color: '#fff', fontWeight: 600, fontSize: 13, cursor: 'pointer', boxShadow: '0 4px 12px rgba(0,68,168,0.2)'
            }}>
              <Plus size={14} /> Add Source
            </button>
          </Link>
        </div>
      </header>

      {/* KPI Row */}
      <GlassCard style={{ display: 'flex', alignItems: 'center', padding: '24px 40px', marginBottom: 24, borderRadius: 32 }}>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(0,68,168,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Server size={24} color="#0044A8" />
          </div>
          <div>
            <div style={{ fontSize: 13, color: '#8999b0', fontWeight: 500, marginBottom: 4 }}>Total Sources</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: '#0a0e27', lineHeight: 1 }}>{sources.length || 0}</div>
            <div style={{ fontSize: 12, color: '#057a55', fontWeight: 600, marginTop: 6 }}>↑ Active</div>
          </div>
        </div>

        <div style={{ width: 1, height: 64, background: 'rgba(0,68,168,0.1)', margin: '0 24px' }} />

        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(5,122,85,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Activity size={24} color="#057a55" />
          </div>
          <div>
            <div style={{ fontSize: 13, color: '#8999b0', fontWeight: 500, marginBottom: 4 }}>Active Streams</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: '#0a0e27', lineHeight: 1 }}>{activeCount || 0}</div>
            <div style={{ fontSize: 12, color: '#057a55', fontWeight: 600, marginTop: 6 }}>Healthy</div>
          </div>
        </div>

        <div style={{ width: 1, height: 64, background: 'rgba(0,68,168,0.1)', margin: '0 24px' }} />

        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(0,68,168,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Database size={24} color="#0044A8" />
          </div>
          <div>
            <div style={{ fontSize: 13, color: '#8999b0', fontWeight: 500, marginBottom: 4 }}>Total Events Ingested</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: '#0a0e27', lineHeight: 1 }}>{totalEventsIngested.toLocaleString()}</div>
            <div style={{ fontSize: 12, color: '#8999b0', fontWeight: 600, marginTop: 6 }}>Across all real sources</div>
          </div>
        </div>
      </GlassCard>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <GlassCard style={{ padding: '6px 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Filter size={14} color="#8999b0" />
            <input type="text" placeholder="Filter sources..." value={filter} onChange={e => setFilter(e.target.value)} style={{ border: 'none', background: 'transparent', outline: 'none', fontSize: 13, width: 200 }} />
          </GlassCard>
        </div>
      </div>

      {isLoading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 24 }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <GlassCard key={i} style={{ height: 180 }}>
              <div style={{ height: 16, width: '60%', borderRadius: 6, background: 'rgba(0,68,168,0.08)', animation: 'shimmer 1.5s infinite' }} />
            </GlassCard>
          ))}
        </div>
      ) : allSources.length === 0 ? (
        <GlassCard style={{ padding: 64, textAlign: 'center' }}>
          <Server size={48} color="#0044A8" style={{ opacity: 0.3, margin: '0 auto 16px' }} />
          <h3 className="section-heading" style={{ marginBottom: 8 }}>No Log Sources Configured</h3>
          <p style={{ color: '#5b6382', maxWidth: 400, margin: '0 auto 24px' }}>
            Connect Syslog, Windows Event Forwarder, AWS CloudWatch, or custom API webhooks to start ingesting events.
          </p>
          <Link to="/add-source" style={{ textDecoration: 'none' }}>
            <button style={{
              display: 'inline-flex', alignItems: 'center', gap: 8, padding: '10px 20px', borderRadius: 10,
              background: '#0044A8', color: '#fff', border: 'none', fontWeight: 600, fontSize: 14, cursor: 'pointer'
            }}>
              <Plus size={16} /> Configure First Source
            </button>
          </Link>
        </GlassCard>
      ) : sources.length === 0 ? (
        <GlassCard style={{ padding: 40, textAlign: 'center' }}>
          <p style={{ color: '#8999b0', fontSize: 13 }}>No sources match "{filter}".</p>
        </GlassCard>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 24 }}>
          {sources.map((source: any, i: number) => {
            const isLive = source.enabled
            const eventCount = eventCountBySource[source.id] ?? 0
            
            return (
              <GlassCard
                key={source.id || i}
                onClick={() => navigate(`/sources/${source.id}`)}
                style={{ padding: 20, position: 'relative', overflow: 'hidden' }}
              >
                {isLive && (
                  <div style={{ position: 'absolute', top: 0, right: 0, width: 100, height: 100, background: 'radial-gradient(circle, rgba(5,122,85,0.08) 0%, transparent 70%)', pointerEvents: 'none' }} />
                )}
                
                <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16 }}>
                  <div style={{
                    width: 44, height: 44, borderRadius: 12,
                    background: isLive ? 'rgba(5,122,85,0.1)' : 'rgba(137,153,176,0.1)',
                    border: `1px solid ${isLive ? 'rgba(5,122,85,0.2)' : 'rgba(137,153,176,0.2)'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    <Database size={22} color={isLive ? '#057a55' : '#8999b0'} />
                  </div>
                  <div>
                    <h3 className="section-heading" style={{ marginBottom: 2 }}>
                      {displaySourceName(source.name)}
                    </h3>
                    <div style={{ fontSize: 12, color: '#8999b0', fontFamily: 'monospace' }}>{source.id}</div>
                  </div>
                </div>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 20 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ color: '#5b6382' }}>Status</span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, color: isLive ? '#057a55' : '#8999b0' }}>
                      <div style={{ width: 6, height: 6, borderRadius: '50%', background: isLive ? '#057a55' : '#8999b0', boxShadow: isLive ? '0 0 6px rgba(5,122,85,0.4)' : 'none' }} />
                      {isLive ? 'LIVE' : 'DISABLED'}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ color: '#5b6382' }}>Vendor / Protocol</span>
                    <span style={{ fontWeight: 600, color: '#0a0e27' }}>{anonymizedVendorLabel(source.id)} / {source.protocol || 'Syslog'}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ color: '#5b6382' }}>Parser Assigned</span>
                    <span style={{ fontWeight: 600, color: '#0044A8', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Terminal size={12} /> {source.parser_id || 'auto-detect'}
                    </span>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', background: 'rgba(0,68,168,0.03)', borderRadius: 10, border: '1px solid rgba(0,68,168,0.05)' }}>
                  <div>
                    <div style={{ fontSize: 11, color: '#5b6382', textTransform: 'uppercase', fontWeight: 600, marginBottom: 2 }}>Events Ingested</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: '#0a0e27' }}>{eventCount.toLocaleString()} <span style={{ fontSize: 12, color: '#8999b0', fontWeight: 600 }}>total</span></div>
                  </div>
                  <Activity size={24} color={isLive ? '#0044A8' : '#8999b0'} style={{ opacity: isLive ? 1 : 0.3 }} />
                </div>
              </GlassCard>
            )
          })}
        </div>
      )}
    </div>
  )
}
