import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { DEMO_SOURCES, DEMO_ALERTS } from '../data/demo'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell
} from 'recharts'

const DONUT_COLORS = ['#1a56db', '#0e7490', '#6d28d9', '#c27803', '#6b7280', '#d1d5db']

const statStyle: React.CSSProperties = { flex: 1, minWidth: 160 }
const statLabel: React.CSSProperties = { fontSize: 12, color: '#6b7280', marginBottom: 2 }
const statValue: React.CSSProperties = { fontSize: 24, fontWeight: 700, color: '#111928', letterSpacing: '-0.02em' }
const sectionTitle: React.CSSProperties = { fontSize: 14, fontWeight: 600, color: '#111928', marginBottom: 12 }
const panel: React.CSSProperties = { border: '1px solid #e5e7eb', borderRadius: 8, padding: 20, background: '#fff' }

export default function Dashboard() {
  const { data: statsData } = useQuery({ queryKey: ['stats'], queryFn: () => api.getStats() })
  const { data: pipelineData } = useQuery({ queryKey: ['pipelineHealth'], queryFn: () => api.getPipelineHealth() })

  const timelineData = (statsData?.events_over_time || []).length > 0
    ? statsData.events_over_time.slice(-24).map((d: any) => ({
        time: new Date(d.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        events: d.count
      }))
    : Array.from({ length: 24 }).map((_, i) => ({
        time: `${i}:00`,
        events: Math.floor(Math.random() * 500) + 1200
      }))

  const sourceData = [
    { name: 'Firewalls', value: 32.4 },
    { name: 'Servers', value: 24.1 },
    { name: 'Cloud Services', value: 18.3 },
    { name: 'Applications', value: 15.2 },
    { name: 'Network Devices', value: 7.1 },
    { name: 'Others', value: 2.9 },
  ]

  const totalEvents = pipelineData?.total_raw_events || statsData?.total_events || 0
  const parseSuccess = pipelineData?.parse_success_rate || 95.5
  const dlqCount = pipelineData?.dlq_count || 5629
  const pipelineStages = pipelineData?.stages || []

  return (
    <div className="animate-fade-in" style={{ paddingBottom: 40 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle" style={{ margin: 0 }}>Real-time overview of log ingestion, processing and system health</p>
        </div>
        <span style={{ fontSize: 12, color: '#6b7280' }}>Last 24 hours</span>
      </div>

      {/* Stats — plain row, no boxes */}
      <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap', padding: '4px 0 20px', marginBottom: 20, borderBottom: '1px solid #e5e7eb' }}>
        <div style={statStyle}>
          <div style={statLabel}>Events ingested</div>
          <div style={statValue}>{totalEvents.toLocaleString()}</div>
          <div style={{ fontSize: 12, color: '#057a55' }}>+12% vs yesterday</div>
        </div>
        <div style={statStyle}>
          <div style={statLabel}>Parse success</div>
          <div style={statValue}>{parseSuccess}%</div>
          <div style={{ fontSize: 12, color: '#057a55' }}>+0.2 pts</div>
        </div>
        <div style={statStyle}>
          <div style={statLabel}>Failed / DLQ</div>
          <div style={statValue}>{dlqCount.toLocaleString()}</div>
          <div style={{ fontSize: 12, color: '#6b7280' }}>needs review</div>
        </div>
        <div style={statStyle}>
          <div style={statLabel}>Active sources</div>
          <div style={statValue}>12 / 12</div>
          <div style={{ fontSize: 12, color: '#057a55' }}>all healthy</div>
        </div>
      </div>

      {/* Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 20, marginBottom: 28 }}>
        <div style={panel}>
          <div style={sectionTitle}>Event ingestion trend</div>
          <div style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={timelineData}>
                <defs>
                  <linearGradient id="colorEvents" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#1a56db" stopOpacity={0.15}/>
                    <stop offset="95%" stopColor="#1a56db" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#6b7280' }} dy={8} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#6b7280' }} width={48} />
                <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 6, fontSize: 12 }} />
                <Area type="monotone" dataKey="events" stroke="#1a56db" strokeWidth={2} fillOpacity={1} fill="url(#colorEvents)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div style={panel}>
          <div style={sectionTitle}>Events by source type</div>
          <div style={{ height: 240, position: 'relative' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={sourceData} cx="50%" cy="50%" innerRadius={62} outerRadius={84} paddingAngle={2} dataKey="value" stroke="#fff" strokeWidth={2}>
                  {sourceData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={DONUT_COLORS[index % DONUT_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 6, fontSize: 12 }} formatter={(value: any) => [`${value}%`, 'Share']} />
              </PieChart>
            </ResponsiveContainer>
            <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', textAlign: 'center' }}>
              <div style={{ fontSize: 22, fontWeight: 700, color: '#111928' }}>{totalEvents > 1000000 ? (totalEvents/1000000).toFixed(1) + 'M' : totalEvents.toLocaleString()}</div>
              <div style={{ fontSize: 12, color: '#6b7280' }}>Events</div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom lists — plain tables, no nested boxes */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 20 }}>
        <div style={panel}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <div style={sectionTitle}>Recent alerts</div>
            <a href="#" style={{ fontSize: 12, color: '#1a56db', textDecoration: 'none' }}>View all</a>
          </div>
          <table className="glass-table">
            <tbody>
              {DEMO_ALERTS.map(alert => (
                <tr key={alert.id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{alert.message}</div>
                    <div style={{ fontSize: 11, color: '#6b7280' }}>{alert.source} · {alert.time}</div>
                  </td>
                  <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <span className={`badge badge-${alert.severity === 'High' ? 'danger' : alert.severity === 'Medium' ? 'warning' : 'neutral'}`}>
                      {alert.severity}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={panel}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <div style={sectionTitle}>Source health</div>
            <a href="/sources" style={{ fontSize: 12, color: '#1a56db', textDecoration: 'none' }}>Manage</a>
          </div>
          <table className="glass-table">
            <tbody>
              {DEMO_SOURCES.slice(0, 5).map((s, i) => (
                <tr key={i}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{s.name}</div>
                    <div className="mono" style={{ fontSize: 11, color: '#6b7280' }}>{s.eventsPerMin.toLocaleString()} events/min</div>
                  </td>
                  <td style={{ textAlign: 'right', whiteSpace: 'nowrap', fontSize: 12, color: '#6b7280' }}>{s.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={panel}>
          <div style={sectionTitle}>Processing pipeline</div>
          {pipelineStages.length === 0 && <div style={{ fontSize: 13, color: '#6b7280' }}>Loading pipeline health…</div>}
          <table className="glass-table">
            <tbody>
              {pipelineStages.map((stage: any, i: number) => (
                <tr key={i}>
                  <td style={{ fontWeight: 500 }}>{stage.name}</td>
                  <td style={{ textAlign: 'right', whiteSpace: 'nowrap', fontSize: 12, color: '#6b7280' }}>
                    {stage.status} · <span className="mono">{stage.metric}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
