import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { GlassCard } from '../components/glass/GlassCard'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell } from 'recharts'
import { Siren, Activity, ShieldAlert, Plus, Trash2, Filter, X, GitMerge, RefreshCw, Clock } from 'lucide-react'

const PALETTE = ['#002255', '#0044A8', '#0088FF', '#a5c4ff']

const SEVERITY_COLORS: Record<string, string> = { CRITICAL: '#002255', HIGH: '#0044A8', MEDIUM: '#0088FF', LOW: '#a5c4ff' }
const RANGE_OPTIONS = [
  { label: '24H', hours: 24 },
  { label: '7D', hours: 24 * 7 },
  { label: '30D', hours: 24 * 30 },
]

export default function Alerts() {
  const qc = useQueryClient()
  const [activeTab, setActiveTab] = useState('analytics')
  const [range, setRange] = useState(RANGE_OPTIONS[0])
  const [showFilter, setShowFilter] = useState(false)
  const [showCreateRule, setShowCreateRule] = useState(false)
  const [ruleError, setRuleError] = useState<string | null>(null)

  const { data: timeseries } = useQuery({
    queryKey: ['analytics-timeseries', range.hours],
    queryFn: () => api.getTimeseries({
      interval: range.hours <= 24 ? 'hour' : 'day',
      start_date: new Date(Date.now() - range.hours * 3600 * 1000).toISOString(),
      time_field: 'created_at',
    }),
    retry: false,
  })
  const timeData = Array.isArray(timeseries?.timeseries)
    ? timeseries.timeseries.map((d: any) => ({
        time: range.hours <= 24
          ? new Date(d.time).toLocaleTimeString([], { hour: '2-digit' })
          : new Date(d.time).toLocaleDateString([], { month: 'short', day: 'numeric' }),
        events: d.events_normalized,
        failures: d.parse_failures,
      }))
    : []

  const { data: riskSummary } = useQuery({ queryKey: ['risk-summary'], queryFn: () => api.getRiskSummary(), retry: false })
  const severityData = Object.entries(riskSummary?.risk_distribution || {}).map(([name, value]) => ({
    name, value: value as number, color: SEVERITY_COLORS[name] || '#8999b0',
  }))

  const { data: statsData } = useQuery({ queryKey: ['stats'], queryFn: () => api.getStats(), retry: false })
  const typeData = Object.entries(statsData?.top_actions || {}).map(([name, value]) => ({ name, value: value as number }))

  const { data: rules } = useQuery({ queryKey: ['rules'], queryFn: () => api.getRules(), retry: false })
  const rulesList = Array.isArray(rules) ? rules : []

  const deleteRule = (id: number) => {
    api.deleteRule(id).then(() => qc.invalidateQueries({ queryKey: ['rules'] }))
  }

  // Correlation engine (real matched incidents + on-demand evaluation) --
  // merged in from the old standalone Correlation page, since this is the
  // real output of the rules managed right below it.
  const [runningEval, setRunningEval] = useState(false)
  const [evalResult, setEvalResult] = useState<{ total_new: number; new_incidents_by_rule: Record<string, number> } | null>(null)
  const [evalError, setEvalError] = useState<string | null>(null)
  const { data: correlations, isLoading: correlationsLoading } = useQuery({ queryKey: ['correlations'], queryFn: () => api.getCorrelations({ size: 50 }) })
  const correlationItems = correlations?.items || []

  const runEvaluate = async () => {
    setRunningEval(true)
    setEvalError(null)
    setEvalResult(null)
    try {
      const res = await api.evaluateCorrelations()
      setEvalResult(res)
      qc.invalidateQueries({ queryKey: ['correlations'] })
    } catch (e: any) {
      setEvalError(e?.response?.data?.detail || e?.message || 'Evaluation failed.')
    } finally {
      setRunningEval(false)
    }
  }

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 'clamp(40px, 4vw, 52px)', fontWeight: 800, color: '#0044A8', letterSpacing: '-0.03em', lineHeight: 1.1 }}>
            Analytics & Alerts
          </h1>
          <p style={{ fontSize: 'clamp(12px, 0.85vw, 13px)', color: '#8999b0', marginTop: 3 }}>
            Security correlations, risk trends, and anomaly detection.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, background: 'rgba(0,68,168,0.05)', padding: 4, borderRadius: 12 }}>
          <button 
            onClick={() => setActiveTab('analytics')}
            style={{ 
              padding: '6px 16px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
              background: activeTab === 'analytics' ? '#fff' : 'transparent',
              color: activeTab === 'analytics' ? '#0044A8' : '#5b6382',
              boxShadow: activeTab === 'analytics' ? '0 2px 8px rgba(0,68,168,0.1)' : 'none', transition: 'all 0.2s'
            }}>
            Analytics
          </button>
          <button 
            onClick={() => setActiveTab('rules')}
            style={{ 
              padding: '6px 16px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
              background: activeTab === 'rules' ? '#fff' : 'transparent',
              color: activeTab === 'rules' ? '#0044A8' : '#5b6382',
              boxShadow: activeTab === 'rules' ? '0 2px 8px rgba(0,68,168,0.1)' : 'none', transition: 'all 0.2s'
            }}>
            Correlation Rules
          </button>
        </div>
      </header>

      {activeTab === 'analytics' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Main Chart */}
          <GlassCard style={{ padding: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, position: 'relative' }}>
              <h3 className="section-heading">Alert Trends ({range.label})</h3>
              <div style={{ position: 'relative' }}>
                <button
                  onClick={() => setShowFilter(s => !s)}
                  style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'transparent', border: '1px solid rgba(0,68,168,0.2)', padding: '6px 12px', borderRadius: 8, fontSize: 12, fontWeight: 600, color: '#0044A8', cursor: 'pointer' }}
                >
                  <Filter size={14} /> Filter ({range.label})
                </button>
                {showFilter && (
                  <div style={{ position: 'absolute', top: '110%', right: 0, background: '#fff', border: '1px solid rgba(0,68,168,0.15)', borderRadius: 10, boxShadow: '0 8px 24px rgba(0,15,92,0.1)', padding: 6, zIndex: 20, minWidth: 120 }}>
                    {RANGE_OPTIONS.map(opt => (
                      <button
                        key={opt.label}
                        onClick={() => { setRange(opt); setShowFilter(false) }}
                        style={{
                          display: 'block', width: '100%', textAlign: 'left', padding: '8px 10px', borderRadius: 6,
                          border: 'none', background: opt.label === range.label ? 'rgba(0,68,168,0.08)' : 'transparent',
                          color: opt.label === range.label ? '#0044A8' : '#334155', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                        }}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
            {timeData.length === 0 ? (
              <div style={{ height: 240, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <p style={{ fontSize: 12, color: '#b0bace', fontWeight: 500 }}>No real timeseries data yet</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={timeData}>
                  <defs>
                    <linearGradient id="colorEvents" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0044A8" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#0044A8" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorFail" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#c81e1e" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#c81e1e" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#8999b0' }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#8999b0' }} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: 'none', boxShadow: '0 8px 32px rgba(0,68,168,0.1)' }} />
                  <Area type="monotone" dataKey="events" name="Normalized events" stroke="#0044A8" fillOpacity={1} fill="url(#colorEvents)" strokeWidth={2} />
                  <Area type="monotone" dataKey="failures" name="Parse failures" stroke="#c81e1e" fillOpacity={1} fill="url(#colorFail)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </GlassCard>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 24 }}>
            {/* Severity Dist */}
            <GlassCard style={{ padding: 24 }}>
              <h3 className="section-heading" style={{ marginBottom: 24 }}>Severity Distribution</h3>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <ResponsiveContainer width={220} height={220}>
                  <PieChart>
                    <Pie data={severityData} innerRadius={70} outerRadius={100} paddingAngle={5} dataKey="value">
                      {severityData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1, paddingLeft: 30 }}>
                  {severityData.map(s => (
                    <div key={s.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{ width: 12, height: 12, borderRadius: '50%', background: s.color }} />
                        <span style={{ fontSize: 16, color: '#5b6382' }}>{s.name}</span>
                      </div>
                      <span style={{ fontSize: 16, fontWeight: 700, color: '#0a0e27' }}>{s.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </GlassCard>

            {/* Event Type Dist */}
            <GlassCard style={{ padding: 24 }}>
              <h3 className="section-heading" style={{ marginBottom: 24 }}>Event Categories</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={typeData} layout="vertical" margin={{ top: 0, right: 30, left: 10, bottom: 0 }}>
                  <XAxis type="number" hide />
                  <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fontSize: 13, fill: '#5b6382' }} width={120} />
                  <Tooltip cursor={{ fill: 'rgba(0,68,168,0.05)' }} contentStyle={{ borderRadius: 8 }} />
                  <Bar dataKey="value" barSize={24} radius={[0, 4, 4, 0]}>
                    {typeData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={PALETTE[index % PALETTE.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </GlassCard>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Correlation engine: real matched incidents + on-demand evaluation
              (merged in from the old standalone Correlation page) */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <h3 className="section-heading">Correlation Engine</h3>
              <p style={{ fontSize: 12, color: '#8999b0', marginTop: 2 }}>
                Real multi-stage rule matches against stored events -- cross-source, sliding time window.
              </p>
            </div>
            <button onClick={runEvaluate} disabled={runningEval} style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', borderRadius: 10,
              background: 'linear-gradient(135deg, #0044A8, #0088FF)', border: 'none',
              color: '#fff', fontWeight: 600, fontSize: 13, cursor: runningEval ? 'default' : 'pointer', opacity: runningEval ? 0.6 : 1,
            }}>
              <RefreshCw size={14} className={runningEval ? 'animate-spin' : ''} /> {runningEval ? 'Evaluating…' : 'Run Evaluation'}
            </button>
          </div>

          {evalError && (
            <div style={{ padding: '10px 16px', borderRadius: 10, background: 'rgba(200,30,30,0.08)', color: '#c81e1e', fontSize: 13 }}>
              {evalError}
            </div>
          )}
          {evalResult && (
            <div style={{ padding: '10px 16px', borderRadius: 10, background: evalResult.total_new > 0 ? 'rgba(5,122,85,0.08)' : 'rgba(0,68,168,0.06)', color: evalResult.total_new > 0 ? '#057a55' : '#5b6382', fontSize: 13 }}>
              {evalResult.total_new > 0
                ? `Evaluation complete: ${evalResult.total_new} new incident${evalResult.total_new === 1 ? '' : 's'} found (${Object.entries(evalResult.new_incidents_by_rule).filter(([, n]) => n > 0).map(([rule, n]) => `${rule}: ${n}`).join(', ')}).`
                : 'Evaluation complete: no new incidents. Every rule was checked against all stored events -- nothing new matched since the last run.'}
            </div>
          )}

          <GlassCard style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '16px 24px', borderBottom: '1px solid rgba(0,68,168,0.1)' }}>
              <h3 className="section-heading">Correlated Incidents ({correlations?.total ?? 0})</h3>
            </div>
            {correlationsLoading ? (
              <div style={{ padding: 32, textAlign: 'center', color: '#8999b0' }}>Loading…</div>
            ) : correlationItems.length === 0 ? (
              <div style={{ padding: 40, textAlign: 'center' }}>
                <GitMerge size={28} color="#c0cde3" style={{ marginBottom: 8 }} />
                <p style={{ fontSize: 13, color: '#8999b0', fontWeight: 500 }}>No correlated incidents matched yet.</p>
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
                <thead>
                  <tr style={{ background: 'rgba(0,68,168,0.03)', borderBottom: '1px solid rgba(0,68,168,0.1)', color: '#5b6382' }}>
                    <th style={{ padding: '12px 16px', fontWeight: 600 }}>Rule</th>
                    <th style={{ padding: '12px 16px', fontWeight: 600 }}>Correlate Key</th>
                    <th style={{ padding: '12px 16px', fontWeight: 600 }}>Events</th>
                    <th style={{ padding: '12px 16px', fontWeight: 600 }}>Sources</th>
                    <th style={{ padding: '12px 16px', fontWeight: 600 }}>Window</th>
                    <th style={{ padding: '12px 16px', fontWeight: 600 }}>Status</th>
                    <th style={{ padding: '12px 16px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {correlationItems.map((c: any) => (
                    <tr key={c.id} style={{ borderBottom: '1px solid rgba(0,68,168,0.05)' }}>
                      <td style={{ padding: '14px 16px', fontWeight: 600, color: '#0a0e27' }}>{c.rule_name}</td>
                      <td style={{ padding: '14px 16px', color: '#5b6382', fontFamily: 'monospace' }}>{c.correlate_key}</td>
                      <td style={{ padding: '14px 16px', color: '#0a0e27' }}>{c.event_count}</td>
                      <td style={{ padding: '14px 16px', color: '#5b6382' }}>{c.distinct_source_count}</td>
                      <td style={{ padding: '14px 16px', color: '#5b6382', fontSize: 11 }}>
                        {new Date(c.first_event_at).toLocaleTimeString()} → {new Date(c.last_event_at).toLocaleTimeString()}
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: 'rgba(0,68,168,0.1)', color: '#0044A8' }}>{c.status}</span>
                      </td>
                      <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                        <Link to={`/attack-path?incident_id=${c.id}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, fontWeight: 600, color: '#0044A8', textDecoration: 'none' }}>
                          <Clock size={12} /> Timeline
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </GlassCard>

          {/* Rule definitions (create/delete) -- what produces the incidents above */}
          <h3 className="section-heading" style={{ marginTop: 8 }}>Rule Definitions</h3>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button onClick={() => setShowCreateRule(true)} style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', borderRadius: 10,
              background: 'linear-gradient(135deg, #0044A8, #0088FF)', border: 'none',
              color: '#fff', fontWeight: 600, fontSize: 13, cursor: 'pointer', boxShadow: '0 4px 12px rgba(0,68,168,0.2)'
            }}>
              <Plus size={14} /> Create Rule
            </button>
          </div>
          <GlassCard style={{ padding: 0, overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
              <thead>
                <tr style={{ background: 'rgba(0,68,168,0.03)', borderBottom: '1px solid rgba(0,68,168,0.1)', color: '#5b6382' }}>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>Rule Name</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>Severity</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>Condition</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>Matches (24h)</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>Status</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rulesList.length === 0 ? (
                  <tr><td colSpan={6} style={{ padding: 32, textAlign: 'center', color: '#8999b0' }}>No correlation rules active.</td></tr>
                ) : (
                  rulesList.map((r: any) => (
                    <tr key={r.id} style={{ borderBottom: '1px solid rgba(0,68,168,0.05)' }}>
                      <td style={{ padding: '16px', fontWeight: 600, color: '#0a0e27' }}>{r.name}</td>
                      <td style={{ padding: '16px' }}>
                        <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: r.severity === 'critical' ? 'rgba(200,30,30,0.1)' : 'rgba(217,119,6,0.1)', color: r.severity === 'critical' ? '#c81e1e' : '#d97706', textTransform: 'uppercase' }}>
                          {r.severity}
                        </span>
                      </td>
                      <td style={{ padding: '16px', color: '#5b6382', fontFamily: 'monospace', fontSize: 11 }}>
                        {r.description || (r.condition ? `${r.condition.field} ${r.condition.operator || '='} ${r.condition.value ?? ''}`.trim() : '—')}
                        {r.threshold ? ` (≥${r.threshold} in ${r.time_window_seconds || 0}s)` : ''}
                      </td>
                      <td style={{ padding: '16px', color: '#0a0e27', fontWeight: 500 }}>{r.matches_24h ?? '—'}</td>
                      <td style={{ padding: '16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <div style={{ width: 8, height: 8, borderRadius: '50%', background: r.enabled ? '#057a55' : '#8999b0' }} />
                          <span style={{ fontSize: 12, color: r.enabled ? '#057a55' : '#8999b0', fontWeight: 600 }}>{r.enabled ? 'Active' : 'Disabled'}</span>
                        </div>
                      </td>
                      <td style={{ padding: '16px', textAlign: 'right' }}>
                        <button onClick={() => deleteRule(r.id)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: '#c81e1e', padding: 4 }}>
                          <Trash2 size={16} />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </GlassCard>
        </div>
      )}

      {showCreateRule && (
        <CreateRuleModal
          onClose={() => { setShowCreateRule(false); setRuleError(null) }}
          onError={setRuleError}
          error={ruleError}
          onCreated={() => { setShowCreateRule(false); setRuleError(null); qc.invalidateQueries({ queryKey: ['rules'] }) }}
        />
      )}
    </div>
  )
}

function CreateRuleModal({ onClose, onCreated, onError, error }: { onClose: () => void; onCreated: () => void; onError: (e: string | null) => void; error: string | null }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [severity, setSeverity] = useState('medium')
  const [field, setField] = useState('action')
  const [operator, setOperator] = useState('=')
  const [value, setValue] = useState('')
  const [threshold, setThreshold] = useState(5)
  const [windowSeconds, setWindowSeconds] = useState(60)
  const [submitting, setSubmitting] = useState(false)

  const submit = () => {
    if (!name.trim() || !value.trim()) {
      onError('Rule name and condition value are required.')
      return
    }
    setSubmitting(true)
    onError(null)
    api.createRule({
      name: name.trim(),
      description: description.trim() || `${field} ${operator} ${value}`,
      severity,
      enabled: true,
      condition: { field, operator, value },
      threshold,
      time_window_seconds: windowSeconds,
    })
      .then(onCreated)
      .catch((e: any) => onError(e?.response?.data?.detail || e?.message || 'Could not create this rule.'))
      .finally(() => setSubmitting(false))
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,15,46,0.4)', backdropFilter: 'blur(8px)' }}>
      <div style={{ width: '90%', maxWidth: 480, background: '#fff', borderRadius: 16, padding: 28, position: 'relative', boxShadow: '0 16px 48px rgba(0,15,92,0.2)' }}>
        <button onClick={onClose} style={{ position: 'absolute', top: 16, right: 16, background: 'none', border: 'none', cursor: 'pointer' }}><X size={18} color="#8999b0" /></button>
        <h2 style={{ fontSize: 18, fontWeight: 800, color: '#0a0e27', marginBottom: 20 }}>Create Correlation Rule</h2>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: '#5b6382', marginBottom: 6 }}>Rule name</label>
            <input className="glass-input" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Repeated login failures" />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: '#5b6382', marginBottom: 6 }}>Description (optional)</label>
            <input className="glass-input" value={description} onChange={e => setDescription(e.target.value)} placeholder="Shown in the rule list" />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: '#5b6382', marginBottom: 6 }}>Field</label>
              <input className="glass-input" value={field} onChange={e => setField(e.target.value)} placeholder="action" />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: '#5b6382', marginBottom: 6 }}>Operator</label>
              <select className="glass-input" value={operator} onChange={e => setOperator(e.target.value)}>
                <option value="=">=</option>
                <option value=">">&gt;</option>
                <option value="<">&lt;</option>
                <option value=">=">&gt;=</option>
                <option value="<=">&lt;=</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: '#5b6382', marginBottom: 6 }}>Value</label>
              <input className="glass-input" value={value} onChange={e => setValue(e.target.value)} placeholder="login_failed" />
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: '#5b6382', marginBottom: 6 }}>Severity</label>
              <select className="glass-input" value={severity} onChange={e => setSeverity(e.target.value)}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: '#5b6382', marginBottom: 6 }}>Threshold</label>
              <input className="glass-input" type="number" min={1} value={threshold} onChange={e => setThreshold(Number(e.target.value))} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: '#5b6382', marginBottom: 6 }}>Window (s)</label>
              <input className="glass-input" type="number" min={1} value={windowSeconds} onChange={e => setWindowSeconds(Number(e.target.value))} />
            </div>
          </div>

          {error && <div style={{ color: '#c81e1e', fontSize: 12 }}>{error}</div>}

          <button onClick={submit} disabled={submitting} className="btn-primary" style={{ justifyContent: 'center', marginTop: 8 }}>
            {submitting ? 'Creating…' : 'Create Rule'}
          </button>
        </div>
      </div>
    </div>
  )
}
