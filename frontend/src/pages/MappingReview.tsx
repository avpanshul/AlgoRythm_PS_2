import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, X } from 'lucide-react'
import { api } from '../api/client'
import { anonymizedVendorLabel } from '../utils/anonymize'

export default function MappingReview() {
  const qc = useQueryClient()
  const [reviewer, setReviewer] = useState('admin')

  const { data: mappings, isLoading, isError } = useQuery({
    queryKey: ['mappings', 'needs-review'],
    queryFn: () => api.getMappings({ needs_review: true }),
    retry: false,
  })

  const list: any[] = Array.isArray(mappings) ? mappings : []

  const approve = (id: number) => api.approveMapping(id, { reviewer }).then(() => qc.invalidateQueries({ queryKey: ['mappings', 'needs-review'] }))
  const reject = (id: number) => api.rejectMapping(id, { reviewer, reason: 'rejected via Mapping Review' }).then(() => qc.invalidateQueries({ queryKey: ['mappings', 'needs-review'] }))

  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ marginBottom: 20, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <h1 className="page-title">Mapping review</h1>
        <p className="page-subtitle" style={{ margin: 0 }}>
          Field-level mappings suggested by the semantic/LLM fallback (see <code>app/services/mapping_service.py</code>) --
          nothing here is auto-approved. Approve to add a mapping to the registry, reject to discard it.
        </p>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 16, alignItems: 'center' }}>
        <span style={{ fontSize: 12, color: '#6b7280' }}>Reviewing as:</span>
        <input className="glass-input" style={{ width: 160 }} value={reviewer} onChange={e => setReviewer(e.target.value)} />
      </div>

      <div className="glass-table-container">
        <table className="glass-table">
          <thead>
            <tr>
              <th>Vendor</th>
              <th>Raw field</th>
              <th>Suggested canonical field</th>
              <th>Method</th>
              <th>Confidence</th>
              <th style={{ textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {list.map((m: any) => (
              <tr key={m.id}>
                <td style={{ fontSize: 12 }}>{m.vendor ? anonymizedVendorLabel(m.vendor) : 'Generic'}{m.device_type ? ` / ${m.device_type}` : ''}</td>
                <td className="mono" style={{ fontSize: 12 }}>{m.raw_field}</td>
                <td className="mono" style={{ fontSize: 12, color: '#1a56db' }}>{m.canonical_field}</td>
                <td><span className="badge badge-neutral">{m.mapping_type}</span></td>
                <td className="mono" style={{ fontSize: 12, fontWeight: 600, color: m.confidence >= 0.9 ? '#057a55' : '#c27803' }}>{Math.round(m.confidence * 100)}%</td>
                <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                  <button className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: 11, marginRight: 6 }} onClick={() => approve(m.id)}>
                    <Check size={12} /> Approve
                  </button>
                  <button className="btn btn-ghost" style={{ padding: '4px 8px', fontSize: 11 }} onClick={() => reject(m.id)}>
                    <X size={12} color="#c81e1e" />
                  </button>
                </td>
              </tr>
            ))}
            {isLoading && <tr><td colSpan={6} style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>Loading…</td></tr>}
            {isError && <tr><td colSpan={6} style={{ textAlign: 'center', padding: 40, color: '#c81e1e' }}>Could not reach the backend.</td></tr>}
            {!isLoading && !isError && list.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>No field mappings awaiting review.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
