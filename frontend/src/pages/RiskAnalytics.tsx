import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts'
import { Activity, ShieldAlert, GitMerge, TrendingUp } from 'lucide-react'

const QUALITY_DATA = [
  { time: '08:00', quality: 97 }, { time: '09:00', quality: 96 },
  { time: '10:00', quality: 98 }, { time: '11:00', quality: 95 },
  { time: '12:00', quality: 99 }, { time: '13:00', quality: 97 },
  { time: '14:00', quality: 94 }, { time: '15:00', quality: 98 },
  { time: '16:00', quality: 97 }, { time: '17:00', quality: 99 },
]

const TREND_DATA = [
  { time: '08:00', events: 1840 }, { time: '09:00', events: 2120 },
  { time: '10:00', events: 3450 }, { time: '11:00', events: 4100 },
  { time: '12:00', events: 3800 }, { time: '13:00', events: 4500 },
  { time: '14:00', events: 5200 }, { time: '15:00', events: 4900 },
  { time: '16:00', events: 4300 }, { time: '17:00', events: 3600 },
]

const FAILURE_DATA = [
  { name: 'Unknown Format', count: 2841 },
  { name: 'Schema Error', count: 1790 },
  { name: 'Parser Error', count: 998 },
]

const RULES = [
  { name: 'Brute Force → Success Login', desc: 'Multiple failed logins followed by success', severity: 'danger', status: 'success', matches: 14 },
  { name: 'Port Scan → Lateral Movement', desc: 'Internal scan then RDP/SSH access', severity: 'warning', status: 'success', matches: 3 },
  { name: 'Impossible Travel', desc: 'Logins from two distant geos within 1h', severity: 'warning', status: 'success', matches: 0 },
  { name: 'Data Exfiltration Volume', desc: 'Outbound transfer > 500MB in 10 minutes', severity: 'danger', status: 'success', matches: 1 },
]

export default function AnalyticsAndAlerts() {
  return (
    <div className="animate-fade-in" style={{ paddingBottom: 40 }}>
      <div style={{ marginBottom: 24 }}>
        <h1 className="page-title">Analytics & Alerts</h1>
        <p className="page-subtitle">Monitor correlation rules, data quality trends, parsing anomalies, and security events</p>
      </div>

      {/* Top Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 28 }}>
        {[
          { label: 'Avg Quality Score', value: '96.8', unit: '%', color: 'var(--color-success)', icon: TrendingUp },
          { label: 'DLQ Failures (24h)', value: '5,629', unit: '', color: 'var(--color-danger)', icon: ShieldAlert },
          { label: 'Active Correlation Rules', value: '4', unit: '', color: 'var(--color-primary-light)', icon: GitMerge },
          { label: 'Anomalies Detected', value: '18', unit: '', color: 'var(--color-warning)', icon: Activity },
        ].map(s => (
          <div key={s.label} className="glass-card" style={{ padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>{s.label}</div>
              <div style={{ fontSize: 26, fontWeight: 700, color: s.color, letterSpacing: '-0.03em' }}>{s.value}<span style={{ fontSize: 14, fontWeight: 500, marginLeft: 2 }}>{s.unit}</span></div>
            </div>
            <div style={{ width: 40, height: 40, borderRadius: 12, background: `${s.color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <s.icon size={18} color={s.color} />
            </div>
          </div>
        ))}
      </div>

      {/* Charts Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 20, marginBottom: 24 }}>
        {/* Event Trend */}
        <div className="glass-card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
            <Activity size={16} color="var(--color-primary-light)" />
            <h3 style={{ fontSize: 14, fontWeight: 600 }}>Event Volume Trend</h3>
          </div>
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={TREND_DATA}>
                <defs>
                  <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--color-primary-light)" stopOpacity={0.25}/>
                    <stop offset="95%" stopColor="var(--color-primary-light)" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.05)" />
                <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }} dy={8} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }} dx={-8} />
                <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.9)', borderRadius: 8, border: '1px solid rgba(255,255,255,1)', boxShadow: '0 8px 24px rgba(30,60,100,0.1)' }} />
                <Area type="monotone" dataKey="events" stroke="var(--color-primary-light)" strokeWidth={2.5} fillOpacity={1} fill="url(#trendGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Data Quality */}
        <div className="glass-card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
            <Activity size={16} color="var(--color-success)" />
            <h3 style={{ fontSize: 14, fontWeight: 600 }}>Data Quality Score</h3>
          </div>
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={QUALITY_DATA}>
                <defs>
                  <linearGradient id="qualGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--color-success)" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="var(--color-success)" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.05)" />
                <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }} dy={8} />
                <YAxis domain={[90, 100]} axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }} dx={-8} />
                <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.9)', borderRadius: 8, border: '1px solid rgba(255,255,255,1)', boxShadow: '0 8px 24px rgba(30,60,100,0.1)' }} />
                <Area type="monotone" dataKey="quality" stroke="var(--color-success)" strokeWidth={2.5} fillOpacity={1} fill="url(#qualGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* DLQ Failures */}
        <div className="glass-card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
            <ShieldAlert size={16} color="var(--color-warning)" />
            <h3 style={{ fontSize: 14, fontWeight: 600 }}>Parsing Failures by Type</h3>
          </div>
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={FAILURE_DATA} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(0,0,0,0.05)" />
                <XAxis type="number" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }} />
                <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} width={110} />
                <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.9)', borderRadius: 8, border: '1px solid rgba(255,255,255,1)' }} cursor={{ fill: 'rgba(0,0,0,0.03)' }} />
                <Bar dataKey="count" fill="var(--color-warning)" radius={[0, 4, 4, 0]} barSize={20} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Correlation Rules */}
      <div className="glass-card" style={{ padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
          <GitMerge size={16} color="var(--color-ai)" />
          <h3 style={{ fontSize: 15, fontWeight: 600 }}>Active Correlation Rules</h3>
        </div>
        <table className="glass-table">
          <thead>
            <tr><th>Rule Name</th><th>Description</th><th>Severity</th><th>Status</th><th>Matches (24h)</th></tr>
          </thead>
          <tbody>
            {RULES.map((rule, i) => (
              <tr key={i}>
                <td style={{ fontWeight: 500 }}>{rule.name}</td>
                <td style={{ color: 'var(--color-text-muted)', fontSize: 12 }}>{rule.desc}</td>
                <td><span className={`badge badge-${rule.severity}`}>{rule.severity === 'danger' ? 'Critical' : 'High'}</span></td>
                <td><span className={`badge badge-${rule.status}`}>Active</span></td>
                <td className="mono" style={{ fontWeight: 600 }}>{rule.matches}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
