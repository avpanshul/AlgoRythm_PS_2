import React, { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { GlassCard } from '../components/glass/GlassCard'
import { anonymizedVendorLabel } from '../utils/anonymize'
import {
  ArrowLeft, Search, Filter, Calendar, ChevronDown, ChevronRight,
  ShieldCheck, Database, FileText, Terminal, Activity, Code2,
} from 'lucide-react'

const RANGE_OPTIONS = [
  { label: 'Last 24 Hours', hours: 24 },
  { label: 'Last 7 Days', hours: 24 * 7 },
  { label: 'All Time', hours: undefined },
]

function displaySourceName(name: string) {
  return name || 'Unnamed source'
}

export default function SourceDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [search, setSearch] = useState('')
  const [expandedRow, setExpandedRow] = useState<string | null>(null)
  const [rangeOpen, setRangeOpen] = useState(false)
  const [range, setRange] = useState(RANGE_OPTIONS[2])
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [severity, setSeverity] = useState('')
  const [riskLevel, setRiskLevel] = useState('')

  const { data: sources, isLoading: sourcesLoading, isError: sourcesError } = useQuery({ queryKey: ['sources'], queryFn: () => api.getSources() })
  const source = Array.isArray(sources) ? sources.find((s: any) => s.id === id) : null

  const { data: eventsData, isLoading: eventsLoading } = useQuery({
    queryKey: ['source-events', id, search, range.hours, severity, riskLevel],
    queryFn: () => api.getEvents({
      source_id: id,
      q: search || undefined,
      since_hours: range.hours,
      severity: severity || undefined,
      risk_level: riskLevel || undefined,
      size: 50,
    }),
    enabled: !!id,
  })
  const events = eventsData?.events || []

  const { data: rawEvent, isLoading: rawLoading, isError: rawError } = useQuery({
    queryKey: ['eventRaw', expandedRow],
    queryFn: () => api.getRawEvent(expandedRow as string),
    enabled: !!expandedRow,
    retry: false,
  })

  if (sourcesLoading) {
    return <div style={{ padding: 40, textAlign: 'center', color: '#8999b0' }}>Loading source…</div>
  }
  if (sourcesError) {
    return <div style={{ padding: 40, textAlign: 'center', color: '#c81e1e' }}>Could not reach the backend to load this source.</div>
  }
  if (!source) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <h2 className="section-heading">Source not found</h2>
        <p style={{ fontSize: 13, color: '#8999b0', margin: '8px 0 16px' }}>ID: {id}</p>
        <Link to="/sources" style={{ fontSize: 12, color: '#0044A8', fontWeight: 600 }}>← Back to Data Sources</Link>
      </div>
    )
  }

  const isLive = source.enabled

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <button
        onClick={() => navigate('/sources')}
        style={{
          display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none', cursor: 'pointer',
          color: '#0044A8', fontWeight: 600, fontSize: 13, padding: 0, width: 'fit-content',
        }}
      >
        <ArrowLeft size={16} /> Back to Data Sources
      </button>

      {/* Source info header -- same look/fields as the Data Sources card */}
      <GlassCard style={{ padding: 24 }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 20, flexWrap: 'wrap' }}>
          <div style={{
            width: 52, height: 52, borderRadius: 14,
            background: isLive ? 'rgba(5,122,85,0.1)' : 'rgba(137,153,176,0.1)',
            border: `1px solid ${isLive ? 'rgba(5,122,85,0.2)' : 'rgba(137,153,176,0.2)'}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}>
            <Database size={26} color={isLive ? '#057a55' : '#8999b0'} />
          </div>
          <div style={{ flex: 1, minWidth: 200 }}>
            <h1 style={{ fontSize: 'clamp(28px, 3vw, 36px)', fontWeight: 800, color: '#0044A8', letterSpacing: '-0.02em', lineHeight: 1.1 }}>
              {displaySourceName(source.name)}
            </h1>
            <div style={{ fontSize: 12, color: '#8999b0', fontFamily: 'monospace', marginTop: 2 }}>{source.id}</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 11, color: '#5b6382', textTransform: 'uppercase', fontWeight: 700, marginBottom: 4 }}>Status</div>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, fontSize: 14, color: isLive ? '#057a55' : '#8999b0' }}>
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: isLive ? '#057a55' : '#8999b0', boxShadow: isLive ? '0 0 6px rgba(5,122,85,0.4)' : 'none' }} />
              {isLive ? 'LIVE' : 'DISABLED'}
            </span>
          </div>
          <div>
            <div style={{ fontSize: 11, color: '#5b6382', textTransform: 'uppercase', fontWeight: 700, marginBottom: 4 }}>Vendor / Protocol</div>
            <div style={{ fontWeight: 600, fontSize: 14, color: '#0a0e27' }}>{anonymizedVendorLabel(source.id)} / {source.protocol || 'Syslog'}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: '#5b6382', textTransform: 'uppercase', fontWeight: 700, marginBottom: 4 }}>Parser Assigned</div>
            <div style={{ fontWeight: 600, fontSize: 14, color: '#0044A8', display: 'flex', alignItems: 'center', gap: 4 }}>
              <Terminal size={14} /> {source.parser_id || 'auto-detect'}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: '#5b6382', textTransform: 'uppercase', fontWeight: 700, marginBottom: 4 }}>Events Ingested</div>
            <div style={{ fontWeight: 700, fontSize: 14, color: '#0a0e27', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Activity size={14} color={isLive ? '#0044A8' : '#8999b0'} /> {(eventsData?.total ?? 0).toLocaleString()} total
            </div>
          </div>
        </div>
      </GlassCard>

      {/* Search + filters, scoped to this source */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <h2 className="section-heading">Events from this source</h2>
        <div style={{ position: 'relative' }}>
          <button onClick={() => setRangeOpen(v => !v)} style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', borderRadius: 10,
            background: 'rgba(0,68,168,0.05)', border: '1px solid rgba(0,68,168,0.15)',
            color: '#0044A8', fontWeight: 600, fontSize: 13, cursor: 'pointer'
          }}>
            <Calendar size={14} /> {range.label} <ChevronDown size={14} />
          </button>
          {rangeOpen && (
            <div style={{ position: 'absolute', top: '110%', right: 0, zIndex: 20, background: '#fff', borderRadius: 10, boxShadow: '0 8px 24px rgba(0,68,168,0.15)', border: '1px solid rgba(0,68,168,0.1)', overflow: 'hidden', minWidth: 160 }}>
              {RANGE_OPTIONS.map(opt => (
                <div key={opt.label} onClick={() => { setRange(opt); setRangeOpen(false) }} style={{
                  padding: '10px 16px', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                  color: opt.label === range.label ? '#0044A8' : '#5b6382',
                  background: opt.label === range.label ? 'rgba(0,68,168,0.06)' : 'transparent',
                }}>{opt.label}</div>
              ))}
            </div>
          )}
        </div>
      </div>

      <GlassCard style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 12, position: 'relative' }}>
        <Search size={18} color="#8999b0" />
        <input
          type="text"
          placeholder="Search this source's events by IP, user, hash, or message text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ flex: 1, border: 'none', background: 'transparent', fontSize: 15, color: '#0a0e27', outline: 'none' }}
        />
        <button onClick={() => setFiltersOpen(v => !v)} style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, color: '#0044A8', fontWeight: 600, fontSize: 13 }}>
          <Filter size={14} /> Filters {(severity || riskLevel) && <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#c81e1e' }} />}
        </button>
        {filtersOpen && (
          <div style={{ position: 'absolute', top: '110%', right: 0, zIndex: 20, background: '#fff', borderRadius: 10, boxShadow: '0 8px 24px rgba(0,68,168,0.15)', border: '1px solid rgba(0,68,168,0.1)', padding: 16, minWidth: 220, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#8999b0', marginBottom: 4, textTransform: 'uppercase' }}>Severity</div>
              <select value={severity} onChange={e => setSeverity(e.target.value)} style={{ width: '100%', padding: '6px 10px', borderRadius: 8, border: '1px solid rgba(0,68,168,0.15)', fontSize: 13 }}>
                <option value="">Any</option>
                {['info', 'low', 'medium', 'high', 'critical', 'notice'].map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#8999b0', marginBottom: 4, textTransform: 'uppercase' }}>Risk Level</div>
              <select value={riskLevel} onChange={e => setRiskLevel(e.target.value)} style={{ width: '100%', padding: '6px 10px', borderRadius: 8, border: '1px solid rgba(0,68,168,0.15)', fontSize: 13 }}>
                <option value="">Any</option>
                {['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            {(severity || riskLevel) && (
              <button onClick={() => { setSeverity(''); setRiskLevel('') }} style={{ fontSize: 12, color: '#c81e1e', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', fontWeight: 600 }}>Clear filters</button>
            )}
          </div>
        )}
      </GlassCard>

      {/* Events table */}
      <GlassCard style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left', tableLayout: 'fixed' }}>
          <thead>
            <tr style={{ background: 'rgba(0,68,168,0.03)', borderBottom: '1px solid rgba(0,68,168,0.1)', color: '#5b6382' }}>
              <th style={{ padding: '12px 16px', fontWeight: 600, width: 40 }}></th>
              <th style={{ padding: '12px 16px', fontWeight: 600, width: 170 }}>Timestamp</th>
              <th style={{ padding: '12px 16px', fontWeight: 600 }}>Event Type</th>
              <th style={{ padding: '12px 16px', fontWeight: 600 }}>IP Address</th>
              <th style={{ padding: '12px 16px', fontWeight: 600, width: 110 }}>Outcome</th>
            </tr>
          </thead>
          <tbody>
            {eventsLoading ? (
              <tr><td colSpan={5} style={{ padding: 32, textAlign: 'center', color: '#8999b0' }}>Loading events...</td></tr>
            ) : events.length === 0 ? (
              <tr><td colSpan={5} style={{ padding: 32, textAlign: 'center', color: '#8999b0' }}>No events from this source match your query.</td></tr>
            ) : (
              events.map((e: any) => {
                const rowId = e.event_id
                const outcome = String(e.event?.outcome || '').toLowerCase()
                const outcomeIsBad = ['fail', 'failed', 'denied', 'deny', 'block', 'error'].some(k => outcome.includes(k))
                const isExpanded = expandedRow === rowId
                return (
                  <React.Fragment key={rowId}>
                    <tr
                      style={{ borderBottom: '1px solid rgba(0,68,168,0.05)', cursor: 'pointer', background: isExpanded ? 'rgba(0,68,168,0.02)' : 'transparent' }}
                      onClick={() => setExpandedRow(isExpanded ? null : rowId)}
                    >
                      <td style={{ padding: '12px 16px', color: '#8999b0' }}>
                        {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                      </td>
                      <td style={{ padding: '12px 16px', color: '#0a0e27', fontWeight: 500 }}>{e.timestamp ? new Date(e.timestamp).toLocaleString() : '—'}</td>
                      <td style={{ padding: '12px 16px', color: '#0044A8', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.event?.category || e.event?.type || '—'}</td>
                      <td style={{ padding: '12px 16px', color: '#5b6382', fontFamily: 'monospace' }}>{e.source?.ip || '—'}</td>
                      <td style={{ padding: '12px 16px' }}>
                        <span style={{
                          padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600,
                          background: outcomeIsBad ? 'rgba(200,30,30,0.1)' : 'rgba(5,122,85,0.1)',
                          color: outcomeIsBad ? '#c81e1e' : '#057a55',
                        }}>
                          {e.event?.outcome ? String(e.event.outcome).toUpperCase() : 'UNKNOWN'}
                        </span>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr style={{ background: 'rgba(0,68,168,0.02)' }}>
                        <td colSpan={5} style={{ padding: '24px 32px', maxWidth: 0 }}>
                          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
                            <div style={{ flex: '1 1 360px', minWidth: 0 }}>
                              <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: '#8999b0', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                                <Code2 size={14} /> Raw Log
                              </div>
                              {rawLoading ? (
                                <div style={{ fontSize: 12, color: '#8999b0' }}>Loading raw log…</div>
                              ) : rawError ? (
                                <div style={{ fontSize: 12, color: '#c81e1e' }}>Could not load the raw log for this event.</div>
                              ) : (
                                <pre style={{ background: 'rgba(255,255,255,0.8)', padding: 12, borderRadius: 8, border: '1px solid rgba(0,68,168,0.1)', fontSize: 11, fontFamily: 'monospace', color: '#334155', maxHeight: 200, overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                                  {rawEvent?.raw_content || '—'}
                                </pre>
                              )}

                              <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: '#8999b0', margin: '16px 0 8px', display: 'flex', alignItems: 'center', gap: 6 }}>
                                <FileText size={14} /> Normalized Event (JSON)
                              </div>
                              <pre style={{ background: 'rgba(255,255,255,0.8)', padding: 12, borderRadius: 8, border: '1px solid rgba(0,68,168,0.1)', fontSize: 11, fontFamily: 'monospace', color: '#334155', maxHeight: 260, overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                                {JSON.stringify(e, null, 2)}
                              </pre>
                            </div>
                            <div style={{ width: 280, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
                              <div>
                                <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: '#8999b0', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                                  <ShieldCheck size={14} /> Integrity
                                </div>
                                <div style={{ fontSize: 10, color: '#5b6382', fontFamily: 'monospace', marginTop: 2, wordBreak: 'break-all' }}>
                                  {e.provenance?.raw_sha256 ? `sha256:${e.provenance.raw_sha256}` : 'no hash recorded'}
                                </div>
                                <Link to={`/events/${rowId}`} onClick={(ev) => ev.stopPropagation()} style={{ fontSize: 11, color: '#0044A8', fontWeight: 600 }}>
                                  Full event detail + Merkle proof →
                                </Link>
                              </div>
                              <div>
                                <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: '#8999b0', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                                  <Database size={14} /> Provenance
                                </div>
                                <div style={{ fontSize: 12, color: '#0a0e27', wordBreak: 'break-all' }}>
                                  Raw event: <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{e.provenance?.raw_event_id || '—'}</span>
                                </div>
                                <div style={{ fontSize: 12, color: '#0a0e27' }}>
                                  Parser: <span style={{ fontWeight: 600 }}>{e.parser?.parser_id || e.parser?.format || '—'}</span>
                                </div>
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                )
              })
            )}
          </tbody>
        </table>
      </GlassCard>
    </div>
  )
}
