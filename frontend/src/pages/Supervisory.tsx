import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

export default function Supervisory() {
  const qc = useQueryClient()
  const [showAddOrg, setShowAddOrg] = useState(false)
  const [showAssign, setShowAssign] = useState(false)

  // Real fix: this used to default to a rolling 24h/7d/30d window, but this
  // project's seeded/demo corpora are ingested once in a short real burst,
  // not continuously -- 24h was always empty once a day had passed since
  // seeding, and 7d/30d were identical since nothing exists in between. A
  // supervisor's real question is "what does this org's traffic look like
  // overall", so all-time (no window_hours param) is the real default now.
  const { data, isLoading, isError, isFetching, refetch } = useQuery({
    queryKey: ['supervisory-overview'],
    queryFn: () => api.getSupervisoryOverview(),
  })

  const orgs = data?.organizations || []

  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <div>
          <h1 className="page-title">Multi-CSE supervisory view</h1>
          <p className="page-subtitle" style={{ margin: 0 }}>
            Aggregate-only rollup across Critical Sector Entities (organizations), all-time. A supervisor sees
            counts and rates per organization -- never another org's raw per-event data.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button onClick={() => refetch()} disabled={isFetching} className="btn-secondary" style={{ fontSize: 12 }}>
            {isFetching ? 'Refreshing…' : 'Refresh'}
          </button>
          <button onClick={() => setShowAssign(true)} className="btn-secondary" style={{ fontSize: 12 }}>
            Assign Sources
          </button>
          <button onClick={() => setShowAddOrg(true)} className="btn-primary" style={{ fontSize: 12 }}>
            + Add Organization
          </button>
        </div>
      </div>

      <div className="glass-table-container">
        <table className="glass-table">
          <thead>
            <tr>
              <th>Organization</th>
              <th>Sector</th>
              <th>Sources</th>
              <th>Events (all-time)</th>
              <th>Avg. quality</th>
              <th>Avg. risk</th>
              <th>Critical events</th>
              <th>Silent sources</th>
            </tr>
          </thead>
          <tbody>
            {orgs.map((o: any) => (
              <tr key={o.organization_id}>
                <td style={{ fontWeight: 600, fontSize: 13 }}>{o.organization_name}</td>
                <td style={{ fontSize: 12, color: '#6b7280' }}>{o.sector || '—'}</td>
                <td className="mono" style={{ fontSize: 12 }}>{o.source_count}</td>
                <td className="mono" style={{ fontSize: 12 }}>{o.event_count}</td>
                <td className="mono" style={{ fontSize: 12 }}>{o.avg_quality != null ? `${o.avg_quality}%` : '—'}</td>
                <td className="mono" style={{ fontSize: 12 }}>{o.avg_risk != null ? o.avg_risk : '—'}</td>
                <td>
                  {o.critical_events > 0
                    ? <span className="badge badge-danger">{o.critical_events}</span>
                    : <span style={{ color: '#057a55' }}>0</span>}
                </td>
                <td>
                  {o.silent_sources > 0
                    ? <span className="badge badge-warning">{o.silent_sources}</span>
                    : <span style={{ color: '#057a55' }}>0</span>}
                </td>
              </tr>
            ))}
            {isLoading && <tr><td colSpan={8} style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>Loading…</td></tr>}
            {isError && <tr><td colSpan={8} style={{ textAlign: 'center', padding: 40, color: '#c81e1e' }}>Could not reach the backend.</td></tr>}
            {!isLoading && !isError && orgs.length === 0 && (
              <tr><td colSpan={8} style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>
                No organizations configured yet -- use "Add Organization" above to create one.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showAddOrg && (
        <AddOrgModal
          onClose={() => setShowAddOrg(false)}
          onCreated={() => { setShowAddOrg(false); qc.invalidateQueries({ queryKey: ['supervisory-overview'] }) }}
        />
      )}
      {showAssign && (
        <AssignSourcesModal
          onClose={() => setShowAssign(false)}
          onChanged={() => qc.invalidateQueries({ queryKey: ['supervisory-overview'] })}
        />
      )}
    </div>
  )
}

function AddOrgModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState('')
  const [type, setType] = useState('')
  const [sector, setSector] = useState('')
  const [contactEmail, setContactEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const submit = () => {
    if (!name.trim()) {
      setError('Organization name is required.')
      return
    }
    const id = name.trim().toUpperCase().replace(/[^A-Z0-9]+/g, '-').replace(/(^-|-$)/g, '').slice(0, 32) || `ORG-${Date.now()}`
    setSubmitting(true)
    setError(null)
    api.createOrganization({ id, name: name.trim(), type: type || undefined, sector: sector || undefined, contact_email: contactEmail || undefined })
      .then(onCreated)
      .catch((e: any) => setError(e?.response?.data?.detail || e?.message || 'Could not create this organization.'))
      .finally(() => setSubmitting(false))
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,15,46,0.4)', backdropFilter: 'blur(8px)' }}>
      <div style={{ width: '90%', maxWidth: 440, background: '#fff', borderRadius: 16, padding: 28, position: 'relative', boxShadow: '0 16px 48px rgba(0,15,92,0.2)' }}>
        <button onClick={onClose} style={{ position: 'absolute', top: 16, right: 16, background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: '#8999b0' }}>×</button>
        <h2 style={{ fontSize: 18, fontWeight: 800, color: '#0a0e27', marginBottom: 20 }}>Add Organization</h2>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <input className="glass-input" value={name} onChange={e => setName(e.target.value)} placeholder="Organization name" />
          <input className="glass-input" value={type} onChange={e => setType(e.target.value)} placeholder="Type (e.g. Ministry, PSU, CERT, SOC)" />
          <input className="glass-input" value={sector} onChange={e => setSector(e.target.value)} placeholder="Sector" />
          <input className="glass-input" type="email" value={contactEmail} onChange={e => setContactEmail(e.target.value)} placeholder="Contact email" />
          {error && <div style={{ color: '#c81e1e', fontSize: 12 }}>{error}</div>}
          <button onClick={submit} disabled={submitting} className="btn-primary" style={{ justifyContent: 'center' }}>
            {submitting ? 'Adding…' : 'Add Organization'}
          </button>
        </div>
      </div>
    </div>
  )
}

function AssignSourcesModal({ onClose, onChanged }: { onClose: () => void; onChanged: () => void }) {
  const qc = useQueryClient()
  const { data: sourcesData } = useQuery({ queryKey: ['sources'], queryFn: api.getSources })
  const { data: orgsData } = useQuery({ queryKey: ['organizations'], queryFn: api.getOrganizations })
  const sources: any[] = Array.isArray(sourcesData) ? sourcesData : []
  const orgs: any[] = Array.isArray(orgsData) ? orgsData : []
  const [saving, setSaving] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const assign = (sourceId: string, orgId: string) => {
    setSaving(sourceId)
    setError(null)
    api.updateSource(sourceId, { organization_id: orgId || null })
      .then(() => {
        qc.invalidateQueries({ queryKey: ['sources'] })
        onChanged()
      })
      .catch((e: any) => setError(e?.response?.data?.detail || e?.message || 'Could not update this source.'))
      .finally(() => setSaving(null))
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,15,46,0.4)', backdropFilter: 'blur(8px)' }}>
      <div style={{ width: '90%', maxWidth: 600, maxHeight: '80vh', overflowY: 'auto', background: '#fff', borderRadius: 16, padding: 28, position: 'relative', boxShadow: '0 16px 48px rgba(0,15,92,0.2)' }}>
        <button onClick={onClose} style={{ position: 'absolute', top: 16, right: 16, background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: '#8999b0' }}>×</button>
        <h2 style={{ fontSize: 18, fontWeight: 800, color: '#0a0e27', marginBottom: 4 }}>Assign Sources to Organizations</h2>
        <p style={{ fontSize: 12, color: '#8999b0', marginBottom: 20 }}>
          The supervisory rollup only counts a source once it's assigned to an organization.
        </p>

        {orgs.length === 0 ? (
          <p style={{ fontSize: 13, color: '#8999b0' }}>Add an organization first, then assign sources to it here.</p>
        ) : sources.length === 0 ? (
          <p style={{ fontSize: 13, color: '#8999b0' }}>No sources registered yet.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {sources.map((s: any) => (
              <div key={s.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '10px 14px', background: 'rgba(0,68,168,0.03)', borderRadius: 10 }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#0a0e27', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.name}</div>
                  <div style={{ fontSize: 11, color: '#8999b0', fontFamily: 'monospace' }}>{s.id}</div>
                </div>
                <select
                  className="glass-input"
                  value={s.organization_id || ''}
                  disabled={saving === s.id}
                  onChange={e => assign(s.id, e.target.value)}
                  style={{ width: 200, flexShrink: 0 }}
                >
                  <option value="">Unassigned</option>
                  {orgs.map((o: any) => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select>
              </div>
            ))}
          </div>
        )}
        {error && <div style={{ color: '#c81e1e', fontSize: 12, marginTop: 12 }}>{error}</div>}
      </div>
    </div>
  )
}
