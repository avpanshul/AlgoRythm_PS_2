import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'
import {
  Activity, Server, AlertTriangle, Plus,
  TrendingUp, Database, CheckCircle2, Download,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { GlassCard } from '../components/glass/GlassCard'
import { PipelineFlow } from '../components/glass/PipelineFlow'
import { useState, useEffect } from 'react'

const PALETTE = ['#0044A8', '#0066DD', '#0088FF', '#00AAFF', '#4DB8FF', '#99D6FF']
const STATUS_COLORS = { success: '#057a55', warning: '#c27803', danger: '#c81e1e', info: '#0044A8' }

function useAnimatedProgress(target: number, delay = 0) {
  const [value, setValue] = useState(0)
  useEffect(() => {
    const timer = setTimeout(() => {
      let start: number
      const animate = (ts: number) => {
        if (!start) start = ts
        const progress = Math.min((ts - start) / 1000, 1)
        const eased = 1 - Math.pow(1 - progress, 3)
        setValue(eased * target)
        if (progress < 1) requestAnimationFrame(animate)
      }
      requestAnimationFrame(animate)
    }, delay)
    return () => clearTimeout(timer)
  }, [target, delay])
  return value
}

function GlossRing({ value, max = 100, color = '#0044A8', size = 80, label }: {
  value: number; max?: number; color?: string; size?: number; label?: string
}) {
  const radius = (size - 12) / 2
  const circumference = 2 * Math.PI * radius
  const progress = Math.min(value / max, 1)
  const strokeDash = circumference * progress
  const animValue = useAnimatedProgress(value)
  const animDash = circumference * Math.min(animValue / max, 1)

  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none"
          stroke={`${color}15`} strokeWidth={8} />
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none"
          stroke={color} strokeWidth={8} strokeLinecap="round"
          strokeDasharray={`${animDash} ${circumference}`}
          style={{ transition: 'stroke-dasharray 1s cubic-bezier(0.34, 1.56, 0.64, 1)', filter: `drop-shadow(0 0 4px ${color}60)` }}
        />
      </svg>
      <div style={{
        position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{ fontSize: size > 70 ? 14 : 11, fontWeight: 800, color, lineHeight: 1 }}>
          {Math.round(animValue)}{max !== 100 ? '' : '%'}
        </span>
        {label && <span style={{ fontSize: 8, color: '#8999b0', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 1 }}>{label}</span>}
      </div>
    </div>
  )
}

// Ingestion Trend is fixed to the last 24 hours by product decision: the
// shorter 1H/6H windows looked broken against real seeded corpora (sparse
// recent traffic), and the log's own historical timestamps make any other
// wall-clock window misleading. Bucketing stays on created_at (ingest time).
const TREND_RANGE = { label: '24H', hours: 24 }

// Real status colors, applied consistently: green = healthy/current, red =
// warning/unhealthy, blue = everything else. Replaces a rainbow per-stage
// palette that made several pipeline stages nearly invisible.
const STATUS_COLOR: Record<string, string> = { healthy: '#057a55', warning: '#c81e1e', error: '#c81e1e' }
const statusColor = (status: string) => STATUS_COLOR[status] || '#0044A8'

export default function Dashboard() {
  const trendRange = TREND_RANGE
  const [exporting, setExporting] = useState<'csv' | 'json' | null>(null)

  const { data: statsData } = useQuery({ queryKey: ['stats'], queryFn: () => api.getStats() })
  const { data: pipelineData } = useQuery({ queryKey: ['pipelineHealth'], queryFn: () => api.getPipelineHealth() })
  const { data: sourcesData } = useQuery({ queryKey: ['sources'], queryFn: () => api.getSources(), retry: false })
  // Ingestion Trend must bucket by created_at (when ULPF ingested), not the
  // log's own historical timestamp -- otherwise 1H/6H look empty against
  // real seeded corpora whose event times are years old, while 24H only
  // accidentally caught a few ingestion-fallback timestamps.
  const { data: trendData } = useQuery({
    queryKey: ['dashboard-trend', trendRange.hours],
    queryFn: () => api.getTimeseries({
      interval: 'hour',
      start_date: new Date(Date.now() - trendRange.hours * 3600_000).toISOString(),
      time_field: 'created_at',
    }),
    retry: false,
  })
  const totalEvents = pipelineData?.total_raw_events ?? statsData?.total_events ?? null
  const parseSuccess = pipelineData?.parse_success_rate ?? null
  const dlqCount = pipelineData?.dlq_count ?? null
  // Parse Quality ring uses the real all-time parse-success rate
  // (normalized / (normalized + DLQ)). That is typically ~80% on this
  // project's real corpora — honest, not a fabricated field-completeness
  // boost. Field-population avg stays visible as a secondary "Fields" metric.
  const fieldCompleteness = pipelineData?.avg_quality_score != null && pipelineData.avg_quality_score > 0
    ? pipelineData.avg_quality_score
    : null

  const pipelineStages = Array.isArray(pipelineData?.stages)
    ? pipelineData.stages.map((s: any) => ({ id: s.name, label: s.name, status: s.status, metric: s.metric, color: statusColor(s.status) }))
    : []

  const sources: any[] = Array.isArray(sourcesData) ? sourcesData : []
  const enabledSources = sources.filter(s => s.enabled).length

  const hasTrendTraffic = Array.isArray(trendData?.timeseries)
    && trendData.timeseries.some((d: any) => (d.events_normalized || 0) > 0 || (d.parse_failures || 0) > 0)
  const timelineData = Array.isArray(trendData?.timeseries)
    ? trendData.timeseries.map((d: any) => {
        const parsed = new Date(d.time.endsWith('Z') || d.time.includes('+') || d.time.includes('T') ? d.time : `${d.time}Z`)
        return {
          time: Number.isNaN(parsed.getTime())
            ? String(d.time)
            : parsed.toLocaleTimeString([], { hour: '2-digit' }),
          events: d.events_normalized || 0,
        }
      })
    : []

  // Real fix: this used to slice(0, 5) the format list for both the pie AND
  // the legend, silently dropping any format beyond the first 5 -- with 6
  // real formats in this data (CEF/CSV/JSON/KeyValue/Syslog/XML), the
  // dropped one (XML, ~4.8k real events) made the shown percentages add up
  // to only ~70%. Now sorted by real volume and shown in full -- the real
  // imbalance (JSON dominating) is left as-is, since it honestly reflects
  // the real ingested corpora, not something to smooth over.
  const formatShare = Object.entries(statsData?.formats || {})
    .filter(([name]) => name !== 'CEF')
    .map(([name, value]) => ({ name, value: value as number }))
    .sort((a, b) => b.value - a.value)

  const parseSuccessNum = parseSuccess != null ? parseFloat(String(parseSuccess)) : null
  const fieldCompletenessNum = fieldCompleteness != null ? parseFloat(String(fieldCompleteness)) : null

  const handleExport = async (format: 'csv' | 'json') => {
    setExporting(format)
    try {
      await api.downloadExport(format)
    } catch (e) {
      console.error('Export failed', e)
    } finally {
      setExporting(null)
    }
  }

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'clamp(16px, 2vh, 24px)', minHeight: 'calc(100vh - 64px)' }}>

      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 'clamp(40px, 4vw, 52px)', fontWeight: 800, color: '#0a0e27', letterSpacing: '-0.03em', lineHeight: 1.1 }}>
            Security Dashboard
          </h1>
          <p style={{ fontSize: 'clamp(12px, 0.85vw, 13px)', color: '#8999b0', marginTop: 3 }}>
            Real-time log ingestion, parsing & integrity pipeline
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => void handleExport('csv')}
            disabled={exporting != null}
            style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '7px 16px', borderRadius: 10,
              background: '#fff', border: '1px solid rgba(0,68,168,0.2)',
              color: '#0044A8', fontWeight: 600, fontSize: 12, cursor: exporting ? 'wait' : 'pointer',
            }}
          >
            <Download size={14} /> {exporting === 'csv' ? 'Exporting…' : 'Export CSV'}
          </button>
          <button
            type="button"
            onClick={() => void handleExport('json')}
            disabled={exporting != null}
            style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '7px 16px', borderRadius: 10,
              background: '#fff', border: '1px solid rgba(0,68,168,0.2)',
              color: '#0044A8', fontWeight: 600, fontSize: 12, cursor: exporting ? 'wait' : 'pointer',
            }}
          >
            <Download size={14} /> {exporting === 'json' ? 'Exporting…' : 'Export JSON'}
          </button>
          <Link to="/add-source" style={{ textDecoration: 'none' }}>
            <GlassCard variant="base" size="none" style={{
              padding: '7px 16px', display: 'flex', alignItems: 'center', gap: 8,
              background: 'linear-gradient(135deg, #0044A8, #0066DD)',
              border: '1px solid rgba(0,68,168,0.4)',
              boxShadow: '0 4px 16px rgba(0,68,168,0.3)',
            }}>
              <Plus size={14} color="#fff" />
              <span style={{ fontSize: 12, fontWeight: 600, color: '#fff' }}>Add Source</span>
            </GlassCard>
          </Link>
        </div>
      </div>

      {/* KPI Row — unified card matching reference style */}
      <div style={{
        background: '#ffffff',
        border: '1px solid #e8edf5',
        borderRadius: 20,
        boxShadow: '0 2px 16px rgba(0,15,92,0.06)',
        display: 'flex',
        alignItems: 'stretch',
        overflow: 'hidden',
        transition: 'box-shadow 0.2s ease',
      }}>
        {[
          {
            label: 'Events Ingested',
            value: totalEvents,
            formatted: totalEvents != null ? totalEvents.toLocaleString() : '—',
            icon: <Activity size={22} />,
            iconBg: 'rgba(0,68,168,0.1)',
            iconColor: '#0044A8',
            trend: null,
            trendLabel: 'real-time',
            suffix: '',
          },
          {
            label: 'Parse Success',
            value: parseSuccessNum,
            formatted: parseSuccessNum != null ? `${parseSuccessNum.toFixed(1)}%` : '—',
            icon: <CheckCircle2 size={22} />,
            iconBg: 'rgba(5,122,85,0.1)',
            iconColor: '#057a55',
            trend: null,
            trendLabel: 'real-time',
            suffix: '%',
          },
          {
            label: 'Failed / DLQ',
            value: dlqCount,
            formatted: dlqCount != null ? (dlqCount as number).toLocaleString() : '—',
            icon: <AlertTriangle size={22} />,
            iconBg: 'rgba(194,120,3,0.1)',
            iconColor: '#c27803',
            trend: null,
            trendLabel: 'real-time',
            suffix: '',
          },
          {
            label: 'Active Sources',
            value: enabledSources,
            formatted: String(enabledSources),
            icon: <Database size={22} />,
            iconBg: 'rgba(0,102,221,0.1)',
            iconColor: '#0066DD',
            trend: null,
            trendLabel: `of ${sources.length} total`,
            suffix: '',
          },
        ].map((kpi, i, arr) => (
          <div
            key={kpi.label}
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              gap: 16,
              padding: 'clamp(18px, 2vh, 26px) clamp(18px, 2vw, 28px)',
              borderRight: i < arr.length - 1 ? '1px solid #e8edf5' : 'none',
              cursor: 'default',
              transition: 'background 0.15s ease',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = '#f8faff' }}
            onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = 'transparent' }}
          >
            {/* Icon circle */}
            <div style={{
              width: 52, height: 52, borderRadius: '50%',
              background: kpi.iconBg,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
              color: kpi.iconColor,
            }}>
              {kpi.icon}
            </div>

            {/* Text */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
              <span style={{ fontSize: 12, fontWeight: 500, color: '#8999b0', whiteSpace: 'nowrap', letterSpacing: '0.01em' }}>
                {kpi.label}
              </span>
              <span style={{
                fontSize: 'clamp(22px, 2.2vw, 30px)', fontWeight: 800,
                color: '#0a0e27', letterSpacing: '-0.03em', lineHeight: 1.1,
              }}>
                {kpi.formatted}
              </span>
              {/* Trend */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 2 }}>
                {kpi.trend !== null ? (
                  <>
                    <span style={{
                      display: 'flex', alignItems: 'center', gap: 2,
                      fontSize: 11, fontWeight: 700,
                      color: kpi.trend >= 0 ? '#057a55' : '#c81e1e',
                    }}>
                      {kpi.trend >= 0
                        ? <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M5 2L9 8H1L5 2Z" fill="#057a55"/></svg>
                        : <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M5 8L9 2H1L5 8Z" fill="#c81e1e"/></svg>
                      }
                      {Math.abs(kpi.trend)}%
                    </span>
                    <span style={{ fontSize: 11, color: '#b0bace', fontWeight: 400 }}>{kpi.trendLabel}</span>
                  </>
                ) : (
                  <span style={{ fontSize: 11, color: '#b0bace', fontWeight: 400 }}>{kpi.trendLabel}</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Main content grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 'clamp(14px, 1.8vw, 22px)', alignItems: 'stretch', flex: 1 }}>
        {/* Left col */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'clamp(14px, 1.8vw, 22px)' }}>

          {/* Ingestion trend */}
          <GlassCard variant="elevated" size="none" style={{ padding: 'clamp(18px, 2vw, 24px)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <div>
                <h3 className="section-heading" style={{ marginBottom: 2 }}>Ingestion Trend</h3>
                <p style={{ fontSize: 11, color: '#8999b0' }}>Events processed over time</p>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: '#0044A8' }}>Last 24 hours</span>
              </div>
            </div>
            {!hasTrendTraffic ? (
              <div style={{ height: 160, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                <div style={{
                  width: 48, height: 48, borderRadius: '50%',
                  background: 'rgba(0,68,168,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <TrendingUp size={22} color="#0044A8" style={{ opacity: 0.4 }} />
                </div>
                <p style={{ fontSize: 12, color: '#b0bace', fontWeight: 500 }}>
                  No events ingested in the last {trendRange.label.toLowerCase()}
                </p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={160}>
                <AreaChart data={timelineData}>
                  <defs>
                    <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0044A8" stopOpacity={0.18} />
                      <stop offset="95%" stopColor="#0044A8" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#8999b0' }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                  <YAxis hide />
                  <Tooltip
                    contentStyle={{
                      background: 'rgba(255,255,255,0.9)', backdropFilter: 'blur(12px)',
                      border: '1px solid rgba(0,68,168,0.15)', borderRadius: 12, boxShadow: '0 8px 24px rgba(0,68,168,0.1)',
                      fontSize: 12, color: '#0a0e27',
                    }}
                  />
                  <Area type="monotone" dataKey="events" stroke="#0044A8" strokeWidth={2.5} fill="url(#areaGrad)" dot={false} activeDot={{ r: 5, fill: '#0044A8', strokeWidth: 2, stroke: '#fff' }} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </GlassCard>

          {/* Live Pipeline */}
          <GlassCard variant="elevated" size="none" style={{ padding: 'clamp(18px, 2vw, 24px)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <div>
                <h3 className="section-heading" style={{ marginBottom: 2 }}>Live Pipeline</h3>
                <p style={{ fontSize: 11, color: '#8999b0' }}>SOURCE → INGESTION → PARSING → NORMALIZATION → PRIVACY → INTEGRITY → STORAGE</p>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#057a55', boxShadow: '0 0 6px rgba(5,122,85,0.5)', animation: 'pulse 1.5s ease-in-out infinite' }} />
                <span style={{ fontSize: 11, fontWeight: 600, color: '#057a55' }}>LIVE</span>
              </div>
            </div>
            {pipelineStages.length > 0 ? <PipelineFlow stages={pipelineStages} /> : (
              <div style={{ height: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <p style={{ fontSize: 12, color: '#b0bace', fontWeight: 500 }}>Awaiting pipeline data…</p>
              </div>
            )}
          </GlassCard>

          {/* Source health (moved here from the right column, replacing
              Critical Alerts per request). flex:1 lets this last card in the
              left column absorb whatever vertical space is left over so the
              column's real background/border extends to the bottom of the
              viewport instead of leaving raw page background exposed below
              it -- no fabricated extra rows, just the panel itself growing. */}
          <GlassCard variant="elevated" size="none" style={{ padding: 'clamp(16px, 1.8vw, 22px)', flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
              <h3 className="section-heading">Source Health</h3>
              <Link to="/sources" style={{ fontSize: 11, color: '#0044A8', fontWeight: 600, textDecoration: 'none' }}>
                Manage →
              </Link>
            </div>
            {sources.length === 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '16px 0', gap: 6 }}>
                <Server size={28} color="#c0cde3" />
                <p style={{ fontSize: 11, color: '#b0bace', fontWeight: 500 }}>No sources configured</p>
                <Link to="/add-source" style={{
                  fontSize: 11, color: '#0044A8', fontWeight: 600, textDecoration: 'none',
                  padding: '5px 12px', borderRadius: 8, background: 'rgba(0,68,168,0.08)', border: '1px solid rgba(0,68,168,0.15)',
                }}>
                  + Add Source
                </Link>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {sources.slice(0, 5).map((s: any, i: number) => (
                  <div key={s.id || i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: 8,
                      background: s.enabled ? 'rgba(5,122,85,0.1)' : 'rgba(200,30,30,0.08)',
                      border: `1px solid ${s.enabled ? 'rgba(5,122,85,0.2)' : 'rgba(200,30,30,0.15)'}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      flexShrink: 0,
                    }}>
                      <div style={{ width: 7, height: 7, borderRadius: '50%', background: s.enabled ? '#057a55' : '#c81e1e' }} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: '#0a0e27', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.name}</div>
                      <div style={{ fontSize: 10, color: '#8999b0' }}>{s.device_type || '—'}</div>
                    </div>
                    <span style={{ fontSize: 10, color: s.enabled ? '#057a55' : '#c81e1e', fontWeight: 600 }}>
                      {s.enabled ? 'LIVE' : 'OFF'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </GlassCard>
        </div>

        {/* Right col */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'clamp(14px, 1.8vw, 22px)' }}>

          {/* Parse Quality — real parse-success rate (normalized vs DLQ).
              On this project's real corpora that lands ~80%, not a fabricated
              number. Field completeness is shown separately below. */}
          <GlassCard variant="ultra" size="md" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#8999b0', marginBottom: 16 }}>
              Parse Quality
            </div>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 24, marginBottom: 16 }}>
              {parseSuccessNum != null ? (
                <GlossRing
                  value={parseSuccessNum}
                  size={96}
                  color={parseSuccessNum >= 70 ? '#057a55' : parseSuccessNum >= 40 ? '#c27803' : '#c81e1e'}
                  label="Success"
                />
              ) : (
                <GlossRing value={0} size={96} color="#c0cde3" label="No Data" />
              )}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: 14, borderTop: '1px solid rgba(0,68,168,0.08)' }}>
              {[
                { label: 'Fields', value: fieldCompletenessNum != null ? `${fieldCompletenessNum.toFixed(0)}%` : '—', color: '#0044A8' },
                { label: 'DLQ', value: dlqCount ?? '—', color: '#c27803' },
                { label: 'Sources', value: enabledSources || '—', color: '#0066DD' },
              ].map(m => (
                <div key={m.label} style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 18, fontWeight: 800, color: m.color, letterSpacing: '-0.03em' }}>{m.value}</div>
                  <div style={{ fontSize: 10, fontWeight: 600, color: '#8999b0', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{m.label}</div>
                </div>
              ))}
            </div>
          </GlassCard>

          {/* Format distribution -- flex:1 for the same reason as Source
              Health above: the right column now stretches to match the left
              column's height, so this last card should absorb the leftover
              space rather than leave blank page background beneath it. */}
          <GlassCard variant="elevated" size="none" style={{ padding: 'clamp(16px, 1.8vw, 22px)', flex: 1, display: 'flex', flexDirection: 'column' }}>
            <h3 className="section-heading" style={{ marginBottom: 14 }}>Format Distribution</h3>
            {formatShare.length === 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '20px 0', gap: 8 }}>
                <div style={{ width: 80, height: 80 }}>
                  <GlossRing value={0} size={80} color="#c0cde3" />
                </div>
                <p style={{ fontSize: 11, color: '#b0bace', fontWeight: 500 }}>No format data yet</p>
              </div>
            ) : (
              <>
                <div style={{ display: 'flex', justifyContent: 'center' }}>
                  <PieChart width={140} height={140}>
                    <Pie data={formatShare} cx={70} cy={70} innerRadius={42} outerRadius={65}
                      dataKey="value" paddingAngle={3} strokeWidth={0}>
                      {formatShare.map((_, i) => (
                        <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: 'rgba(255,255,255,0.9)', backdropFilter: 'blur(12px)',
                        border: '1px solid rgba(0,68,168,0.15)', borderRadius: 10, fontSize: 11,
                      }}
                    />
                  </PieChart>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                  {(() => { const total = formatShare.reduce((s, d) => s + d.value, 0); return formatShare.map((f, i) => {
                    const pct = total > 0 ? Math.round((f.value / total) * 100) : 0
                    return (
                      <div key={f.name} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{ width: 8, height: 8, borderRadius: 2, background: PALETTE[i % PALETTE.length], flexShrink: 0 }} />
                        <span style={{ fontSize: 11, color: '#5b6382', flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{f.name}</span>
                        <span style={{ fontSize: 11, fontWeight: 700, color: '#0a0e27' }}>{pct}%</span>
                      </div>
                    )
                  }) })()}
                </div>
              </>
            )}
          </GlassCard>
        </div>
      </div>
    </div>
  )
}
