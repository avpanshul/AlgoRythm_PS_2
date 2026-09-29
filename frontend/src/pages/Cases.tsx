import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { GlassCard } from '../components/glass/GlassCard'
import { ClipboardList, Bell, X, Plus } from 'lucide-react'

const SEV_COLORS: Record<string, string> = { low: '#8999b0', medium: '#0044A8', high: '#d97706', critical: '#c81e1e' }

export default function Cases() {
  const qc = useQueryClient()
  const [severityFilter, setSeverityFilter] = useState<string>('')
  const [notifyResult, setNotifyResult] = useState<{ caseId: string; status: string; detail?: string } | null>(null)
  const [showContacts, setShowContacts] = useState(false)
  const { data, isLoading } = useQuery({ queryKey: ['cases', severityFilter], queryFn: () => api.getCases({ severity: severityFilter || undefined, size: 50 }) })
  const items = data?.items || []
  const { data: contacts } = useQuery({ queryKey: ['oncall'], queryFn: api.getOnCallContacts, retry: false })
  const contactList = Array.isArray(contacts) ? contacts : []
  const hasEnabledContact = contactList.some((c: any) => c.enabled)

  const notify = async (id: string) => {
    setNotifyResult(null)
    try {
      const res = await api.notifyCase(id)
      setNotifyResult({ caseId: id, status: res.status, detail: res.detail })
      if (res.status !== 'failed') qc.invalidateQueries({ queryKey: ['cases'] })
    } catch (e: any) {
      setNotifyResult({ caseId: id, status: 'failed', detail: e?.response?.data?.detail || e?.message || 'Notify request failed.' })
    }
  }

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <header style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 'clamp(40px, 4vw, 52px)', fontWeight: 800, color: '#0044A8', letterSpacing: '-0.03em', lineHeight: 1.1 }}>
            Incident Cases
          </h1>
          <p style={{ fontSize: 13, color: '#8999b0', marginTop: 3 }}>Real cases -- manually opened or auto-opened by the live correlation-detection cycle.</p>
        </div>
        <button onClick={() => setShowContacts(true)} style={{
          display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', borderRadius: 10,
          background: 'rgba(0,68,168,0.06)', border: '1px solid rgba(0,68,168,0.15)',
          color: '#0044A8', fontWeight: 600, fontSize: 13, cursor: 'pointer',
        }}>
          <Bell size={14} /> On-Call Contacts ({contactList.length})
        </button>
      </header>

      {!hasEnabledContact && (
        <div style={{ padding: '10px 16px', borderRadius: 10, background: 'rgba(217,119,6,0.08)', color: '#8a6d00', fontSize: 13 }}>
          No enabled on-call contact is registered, so Notify will honestly report a failed delivery for every case. Add one via "On-Call Contacts" above to actually receive notifications.
        </div>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        {['', 'low', 'medium', 'high', 'critical'].map(s => (
          <button key={s} onClick={() => setSeverityFilter(s)} style={{
            padding: '6px 14px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600,
            background: severityFilter === s ? '#0044A8' : 'rgba(0,68,168,0.06)',
            color: severityFilter === s ? '#fff' : '#5b6382',
          }}>{s || 'All'}</button>
        ))}
      </div>

      <GlassCard style={{ padding: 0, overflow: 'hidden' }}>
        {isLoading ? (
          <div style={{ padding: 32, textAlign: 'center', color: '#8999b0' }}>Loading…</div>
        ) : items.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <ClipboardList size={28} color="#c0cde3" style={{ marginBottom: 8 }} />
            <p style={{ fontSize: 13, color: '#8999b0', fontWeight: 500 }}>No cases yet.</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
            <thead>
              <tr style={{ background: 'rgba(0,68,168,0.03)', borderBottom: '1px solid rgba(0,68,168,0.1)', color: '#5b6382' }}>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Title</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Severity</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Status</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Owner</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Opened</th>
                <th style={{ padding: '12px 16px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((c: any) => (
                <tr key={c.id} style={{ borderBottom: '1px solid rgba(0,68,168,0.05)' }}>
                  <td style={{ padding: '14px 16px', fontWeight: 600, color: '#0a0e27', maxWidth: 400 }}>{c.title}</td>
                  <td style={{ padding: '14px 16px' }}>
                    <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: `${SEV_COLORS[c.severity]}18`, color: SEV_COLORS[c.severity], textTransform: 'uppercase' }}>{c.severity}</span>
                  </td>
                  <td style={{ padding: '14px 16px', color: '#5b6382' }}>{c.status}</td>
                  <td style={{ padding: '14px 16px', color: '#5b6382' }}>{c.owner || '—'}</td>
                  <td style={{ padding: '14px 16px', color: '#5b6382', fontSize: 11 }}>{new Date(c.created_at).toLocaleString()}</td>
                  <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
                      <button onClick={() => notify(c.id)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: '#0044A8', display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, fontWeight: 600 }}>
                        <Bell size={14} /> Notify
                      </button>
                      {notifyResult && notifyResult.caseId === c.id && (
                        <span style={{ fontSize: 11, color: notifyResult.status === 'failed' ? '#c81e1e' : '#057a55', maxWidth: 220, textAlign: 'right' }}>
                          {notifyResult.status === 'failed' ? (notifyResult.detail || 'Delivery failed.') : `Notification ${notifyResult.status}.`}
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </GlassCard>

      {showContacts && (
        <OnCallContactsModal
          contacts={contactList}
          onClose={() => setShowContacts(false)}
          onChanged={() => qc.invalidateQueries({ queryKey: ['oncall'] })}
        />
      )}
    </div>
  )
}

function OnCallContactsModal({ contacts, onClose, onChanged }: { contacts: any[]; onClose: () => void; onChanged: () => void }) {
  const [name, setName] = useState('')
  const [channel, setChannel] = useState('console')
  const [address, setAddress] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = () => {
    if (!name.trim() || !address.trim()) {
      setError('Name and address are required.')
      return
    }
    setSubmitting(true)
    setError(null)
    api.createOnCallContact({ name: name.trim(), channel, address: address.trim(), escalation_order: contacts.length })
      .then(() => {
        setName('')
        setAddress('')
        onChanged()
      })
      .catch((e: any) => setError(e?.response?.data?.detail || e?.message || 'Could not add this contact.'))
      .finally(() => setSubmitting(false))
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,15,46,0.4)', backdropFilter: 'blur(8px)' }}>
      <div style={{ width: '90%', maxWidth: 480, background: '#fff', borderRadius: 16, padding: 28, position: 'relative', boxShadow: '0 16px 48px rgba(0,15,92,0.2)' }}>
        <button onClick={onClose} style={{ position: 'absolute', top: 16, right: 16, background: 'none', border: 'none', cursor: 'pointer' }}><X size={18} color="#8999b0" /></button>
        <h2 style={{ fontSize: 18, fontWeight: 800, color: '#0a0e27', marginBottom: 20 }}>On-Call Contacts</h2>

        {contacts.length === 0 ? (
          <p style={{ fontSize: 13, color: '#8999b0', marginBottom: 20 }}>
            None registered yet -- this is why Notify reports a failed delivery for every case (app/models/all.py:OnCallContact is intentionally empty until a real admin adds a real contact).
          </p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 20 }}>
            {contacts.map((c: any) => (
              <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', background: 'rgba(0,68,168,0.03)', borderRadius: 8, fontSize: 13 }}>
                <span style={{ fontWeight: 600, color: '#0a0e27' }}>{c.name}</span>
                <span style={{ color: '#5b6382' }}>{c.channel} · {c.address} {c.enabled ? '' : '(disabled)'}</span>
              </div>
            ))}
          </div>
        )}

        <div style={{ borderTop: '1px solid rgba(0,68,168,0.1)', paddingTop: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#5b6382', textTransform: 'uppercase' }}>Add a contact</div>
          <input className="glass-input" placeholder="Name" value={name} onChange={e => setName(e.target.value)} />
          <div style={{ display: 'flex', gap: 8 }}>
            <select className="glass-input" value={channel} onChange={e => setChannel(e.target.value)} style={{ width: 140 }}>
              <option value="console">console (dev/demo)</option>
              <option value="sms">sms</option>
            </select>
            <input className="glass-input" placeholder={channel === 'sms' ? 'Phone number' : 'Label'} value={address} onChange={e => setAddress(e.target.value)} style={{ flex: 1 }} />
          </div>
          {error && <div style={{ color: '#c81e1e', fontSize: 12 }}>{error}</div>}
          <button onClick={submit} disabled={submitting} className="btn-primary" style={{ justifyContent: 'center', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Plus size={14} /> {submitting ? 'Adding…' : 'Add Contact'}
          </button>
        </div>
      </div>
    </div>
  )
}
