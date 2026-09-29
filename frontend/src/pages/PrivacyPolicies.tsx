import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { PlusCircle, Trash2 } from 'lucide-react'
import { api } from '../api/client'

export default function PrivacyPolicies() {
  const qc = useQueryClient()
  const [showNew, setShowNew] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [scope, setScope] = useState('all')
  const [formError, setFormError] = useState<string | null>(null)

  const { data: policies, isLoading, isError } = useQuery({
    queryKey: ['privacy-policies'],
    queryFn: () => api.getPrivacyPolicies(),
    retry: false,
  })

  const list: any[] = Array.isArray(policies) ? policies : []

  const createPolicy = () => {
    setFormError(null)
    api.createPrivacyPolicy({ name, description, scope, rules: [], enabled: true })
      .then(() => {
        qc.invalidateQueries({ queryKey: ['privacy-policies'] })
        setShowNew(false)
        setName(''); setDescription('')
      })
      .catch(e => setFormError(e?.response?.status === 401
        ? 'Requires an authenticated session (no login UI is wired up yet).'
        : (e?.response?.data?.detail || e?.message || 'Failed to create policy.')))
  }

  const toggleEnabled = (pol: any) => {
    api.updatePrivacyPolicy(pol.id, { enabled: !pol.enabled }).then(() => qc.invalidateQueries({ queryKey: ['privacy-policies'] }))
  }

  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <div>
          <h1 className="page-title">Privacy & redaction policies</h1>
          <p className="page-subtitle" style={{ margin: 0 }}>
            Redaction runs on normalized/exported data (see the pipeline's <code>redact_pii</code> step);
            the raw vault is never touched. Policy rows here are metadata about which redaction scope applies where --
            the actual patterns matched (email/phone/PAN/Aadhaar) are defined in the pipeline itself today.
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowNew(v => !v)}>
          <PlusCircle size={14} /> Create policy
        </button>
      </div>

      {showNew && (
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginBottom: 20 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10, marginBottom: 12 }}>
            <input className="glass-input" placeholder="Policy name" value={name} onChange={e => setName(e.target.value)} />
            <input className="glass-input" placeholder="Description" value={description} onChange={e => setDescription(e.target.value)} />
            <select className="glass-input" value={scope} onChange={e => setScope(e.target.value)}>
              <option value="all">all</option>
              <option value="analytics">analytics</option>
              <option value="export">export</option>
            </select>
          </div>
          <button className="btn btn-primary" onClick={createPolicy} disabled={!name}>Create policy</button>
          {formError && <div style={{ marginTop: 10, fontSize: 12, color: '#c81e1e' }}>{formError}</div>}
        </div>
      )}

      <div className="glass-table-container">
        <table className="glass-table">
          <thead>
            <tr><th>Policy</th><th>Scope</th><th>Status</th><th style={{ textAlign: 'right' }}>Actions</th></tr>
          </thead>
          <tbody>
            {list.map(pol => (
              <tr key={pol.id}>
                <td>
                  <div style={{ fontWeight: 600 }}>{pol.name}</div>
                  <div style={{ fontSize: 12, color: '#6b7280' }}>{pol.description}</div>
                </td>
                <td className="mono" style={{ fontSize: 12 }}>{pol.scope}</td>
                <td>
                  <button className={`badge badge-${pol.enabled ? 'success' : 'neutral'}`} style={{ border: 'none', cursor: 'pointer' }} onClick={() => toggleEnabled(pol)}>
                    {pol.enabled ? 'enabled' : 'disabled'}
                  </button>
                </td>
                <td style={{ textAlign: 'right' }}>
                  <button className="btn btn-ghost" style={{ padding: 4 }} onClick={() => api.deletePrivacyPolicy(pol.id).then(() => qc.invalidateQueries({ queryKey: ['privacy-policies'] }))}>
                    <Trash2 size={13} color="#c81e1e" />
                  </button>
                </td>
              </tr>
            ))}
            {isLoading && <tr><td colSpan={4} style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>Loading…</td></tr>}
            {isError && <tr><td colSpan={4} style={{ textAlign: 'center', padding: 40, color: '#c81e1e' }}>This endpoint requires an authenticated session (no login UI is wired up yet).</td></tr>}
            {!isLoading && !isError && list.length === 0 && (
              <tr><td colSpan={4} style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>No privacy policies configured yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
