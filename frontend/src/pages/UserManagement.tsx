import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { GlassCard } from '../components/glass/GlassCard'
import { Users, Shield, Building2, Search, Plus, MoreHorizontal, X, Copy, Check } from 'lucide-react'

export default function UserManagement() {
  const qc = useQueryClient()
  const [activeTab, setActiveTab] = useState('users')
  const [search, setSearch] = useState('')
  const [showInvite, setShowInvite] = useState(false)
  const [showOrgForm, setShowOrgForm] = useState(false)
  const [tempPassword, setTempPassword] = useState<{ email: string; password: string } | null>(null)
  const [openMenuId, setOpenMenuId] = useState<string | null>(null)

  const { data: usersData } = useQuery({ queryKey: ['users'], queryFn: api.getUsers })
  const users: any[] = Array.isArray(usersData) ? usersData : []
  const filteredUsers = users.filter(u =>
    !search.trim() || u.name.toLowerCase().includes(search.toLowerCase()) || u.email.toLowerCase().includes(search.toLowerCase())
  )

  const { data: rolesData } = useQuery({ queryKey: ['roles'], queryFn: api.getRoles })
  const roles: any[] = Array.isArray(rolesData) ? rolesData : []

  const { data: orgsData } = useQuery({ queryKey: ['organizations'], queryFn: api.getOrganizations })
  const orgs: any[] = Array.isArray(orgsData) ? orgsData : []

  const { data: policiesData } = useQuery({ queryKey: ['privacy-policies'], queryFn: () => api.getPrivacyPolicies() })
  const policies: any[] = Array.isArray(policiesData) ? policiesData : []

  const toggleStatus = (u: any) => {
    api.updateUser(u.id, { status: u.status === 'active' ? 'inactive' : 'active' })
      .then(() => qc.invalidateQueries({ queryKey: ['users'] }))
    setOpenMenuId(null)
  }

  const removeUser = (u: any) => {
    api.deleteUser(u.id).then(() => qc.invalidateQueries({ queryKey: ['users'] }))
    setOpenMenuId(null)
  }

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 'clamp(40px, 4vw, 52px)', fontWeight: 800, color: '#0044A8', letterSpacing: '-0.03em', lineHeight: 1.1 }}>
            Administration
          </h1>
          <p style={{ fontSize: 'clamp(12px, 0.85vw, 13px)', color: '#8999b0', marginTop: 3 }}>
            Manage users, roles, organizations, and privacy policies.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, background: 'rgba(0,68,168,0.05)', padding: 4, borderRadius: 12 }}>
          {[
            { id: 'users', label: 'Users', icon: Users },
            { id: 'roles', label: 'Roles & RBAC', icon: Shield },
            { id: 'orgs', label: 'Organizations & Policies', icon: Building2 },
          ].map(t => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '6px 16px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
                background: activeTab === t.id ? '#fff' : 'transparent',
                color: activeTab === t.id ? '#0044A8' : '#5b6382',
                boxShadow: activeTab === t.id ? '0 2px 8px rgba(0,68,168,0.1)' : 'none', transition: 'all 0.2s'
              }}>
              <t.icon size={14} /> {t.label}
            </button>
          ))}
        </div>
      </header>

      {activeTab === 'users' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <GlassCard style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 12, flex: 1, maxWidth: 400 }}>
              <Search size={16} color="#8999b0" />
              <input
                type="text" placeholder="Search users by name or email..." value={search} onChange={e => setSearch(e.target.value)}
                style={{ border: 'none', background: 'transparent', outline: 'none', fontSize: 14, flex: 1 }}
              />
            </GlassCard>
            <button onClick={() => setShowInvite(true)} style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', borderRadius: 10,
              background: 'linear-gradient(135deg, #0044A8, #0088FF)', border: 'none',
              color: '#fff', fontWeight: 600, fontSize: 13, cursor: 'pointer', boxShadow: '0 4px 12px rgba(0,68,168,0.2)'
            }}>
              <Plus size={14} /> Invite User
            </button>
          </div>

          <GlassCard style={{ padding: 0, overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
              <thead>
                <tr style={{ background: 'rgba(0,68,168,0.03)', borderBottom: '1px solid rgba(0,68,168,0.1)', color: '#5b6382' }}>
                  <th style={{ padding: '16px', fontWeight: 600 }}>User</th>
                  <th style={{ padding: '16px', fontWeight: 600 }}>Role</th>
                  <th style={{ padding: '16px', fontWeight: 600 }}>Status</th>
                  <th style={{ padding: '16px', fontWeight: 600 }}>Last Active</th>
                  <th style={{ padding: '16px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.length === 0 ? (
                  <tr><td colSpan={5} style={{ padding: 32, textAlign: 'center', color: '#8999b0' }}>
                    {search ? `No users match "${search}".` : 'No users yet.'}
                  </td></tr>
                ) : filteredUsers.map(user => (
                  <tr key={user.id} style={{ borderBottom: '1px solid rgba(0,68,168,0.05)' }}>
                    <td style={{ padding: '16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'linear-gradient(135deg, #0044A8, #0088FF)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 12, flexShrink: 0 }}>
                          {user.name.split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase()}
                        </div>
                        <div>
                          <div style={{ fontWeight: 600, color: '#0a0e27' }}>{user.name}</div>
                          <div style={{ fontSize: 11, color: '#8999b0' }}>{user.email}</div>
                        </div>
                      </div>
                    </td>
                    <td style={{ padding: '16px' }}>
                      <span style={{ padding: '4px 10px', borderRadius: 12, background: 'rgba(0,68,168,0.05)', color: '#0044A8', fontSize: 11, fontWeight: 600 }}>
                        {user.role_name || '—'}
                      </span>
                    </td>
                    <td style={{ padding: '16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div style={{ width: 8, height: 8, borderRadius: '50%', background: user.status === 'active' ? '#057a55' : '#8999b0' }} />
                        <span style={{ fontSize: 12, color: user.status === 'active' ? '#057a55' : '#8999b0', fontWeight: 600, textTransform: 'capitalize' }}>{user.status}</span>
                      </div>
                    </td>
                    <td style={{ padding: '16px', color: '#5b6382' }}>{user.last_active ? new Date(user.last_active).toLocaleString() : 'Never'}</td>
                    <td style={{ padding: '16px', textAlign: 'right', position: 'relative' }}>
                      <button onClick={() => setOpenMenuId(openMenuId === user.id ? null : user.id)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: '#8999b0' }}>
                        <MoreHorizontal size={16} />
                      </button>
                      {openMenuId === user.id && (
                        <div style={{ position: 'absolute', top: '110%', right: 16, background: '#fff', border: '1px solid rgba(0,68,168,0.15)', borderRadius: 10, boxShadow: '0 8px 24px rgba(0,15,92,0.1)', padding: 6, zIndex: 20, minWidth: 160 }}>
                          <button onClick={() => toggleStatus(user)} style={{ display: 'block', width: '100%', textAlign: 'left', padding: '8px 10px', borderRadius: 6, border: 'none', background: 'transparent', color: '#334155', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
                            {user.status === 'active' ? 'Deactivate' : 'Activate'}
                          </button>
                          <button onClick={() => removeUser(user)} style={{ display: 'block', width: '100%', textAlign: 'left', padding: '8px 10px', borderRadius: 6, border: 'none', background: 'transparent', color: '#c81e1e', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
                            Delete
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </GlassCard>
        </div>
      )}

      {activeTab === 'roles' && (
        <GlassCard style={{ padding: 0, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
            <thead>
              <tr style={{ background: 'rgba(0,68,168,0.03)', borderBottom: '1px solid rgba(0,68,168,0.1)', color: '#5b6382' }}>
                <th style={{ padding: '16px', fontWeight: 600 }}>Role Name</th>
                <th style={{ padding: '16px', fontWeight: 600 }}>Assigned Users</th>
                <th style={{ padding: '16px', fontWeight: 600 }}>Permissions</th>
              </tr>
            </thead>
            <tbody>
              {roles.length === 0 ? (
                <tr><td colSpan={3} style={{ padding: 32, textAlign: 'center', color: '#8999b0' }}>No roles defined.</td></tr>
              ) : roles.map(role => (
                <tr key={role.id} style={{ borderBottom: '1px solid rgba(0,68,168,0.05)' }}>
                  <td style={{ padding: '16px', fontWeight: 600, color: '#0a0e27' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Shield size={16} color="#0044A8" /> {role.name}
                    </div>
                  </td>
                  <td style={{ padding: '16px', color: '#5b6382' }}>{users.filter(u => u.role_name === role.name).length} Users</td>
                  <td style={{ padding: '16px', color: '#5b6382', fontFamily: 'monospace', fontSize: 12 }}>{(role.permissions || []).join(', ') || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </GlassCard>
      )}

      {activeTab === 'orgs' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <GlassCard style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid rgba(0,68,168,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <h3 className="section-heading">Organizations ({orgs.length})</h3>
              <button onClick={() => setShowOrgForm(true)} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 8, background: '#0044A8', border: 'none', color: '#fff', fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>
                <Plus size={12} /> Add Organization
              </button>
            </div>
            {orgs.length === 0 ? (
              <div style={{ padding: 32, textAlign: 'center', color: '#8999b0', fontSize: 13 }}>No organizations registered yet.</div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
                <thead>
                  <tr style={{ background: 'rgba(0,68,168,0.03)', borderBottom: '1px solid rgba(0,68,168,0.1)', color: '#5b6382' }}>
                    <th style={{ padding: '12px 16px', fontWeight: 600 }}>Name</th>
                    <th style={{ padding: '12px 16px', fontWeight: 600 }}>Type</th>
                    <th style={{ padding: '12px 16px', fontWeight: 600 }}>Sector</th>
                    <th style={{ padding: '12px 16px', fontWeight: 600 }}>Contact</th>
                  </tr>
                </thead>
                <tbody>
                  {orgs.map((o: any) => (
                    <tr key={o.id} style={{ borderBottom: '1px solid rgba(0,68,168,0.05)' }}>
                      <td style={{ padding: '14px 16px', fontWeight: 600, color: '#0a0e27' }}>{o.name}</td>
                      <td style={{ padding: '14px 16px', color: '#5b6382' }}>{o.type || '—'}</td>
                      <td style={{ padding: '14px 16px', color: '#5b6382' }}>{o.sector || '—'}</td>
                      <td style={{ padding: '14px 16px', color: '#5b6382' }}>{o.contact_email || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </GlassCard>

          <GlassCard style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid rgba(0,68,168,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <h3 className="section-heading">Privacy Policies ({policies.length})</h3>
              <Link to="/privacy" style={{ fontSize: 12, fontWeight: 600, color: '#0044A8', textDecoration: 'none' }}>Manage in full →</Link>
            </div>
            {policies.length === 0 ? (
              <div style={{ padding: 32, textAlign: 'center', color: '#8999b0', fontSize: 13 }}>
                No privacy policies configured yet -- create one from the Privacy Policies page.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 16 }}>
                {policies.map((p: any) => (
                  <div key={p.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 14px', background: 'rgba(0,68,168,0.03)', borderRadius: 8, fontSize: 13 }}>
                    <span style={{ fontWeight: 600, color: '#0a0e27' }}>{p.name}</span>
                    <span style={{ color: '#5b6382' }}>{(p.redact_fields || []).length} redacted fields</span>
                  </div>
                ))}
              </div>
            )}
          </GlassCard>
        </div>
      )}

      {showInvite && (
        <InviteUserModal
          roles={roles}
          orgs={orgs}
          onClose={() => setShowInvite(false)}
          onCreated={(email: string, password: string) => {
            setShowInvite(false)
            setTempPassword({ email, password })
            qc.invalidateQueries({ queryKey: ['users'] })
          }}
        />
      )}

      {showOrgForm && (
        <AddOrgModal
          onClose={() => setShowOrgForm(false)}
          onCreated={() => { setShowOrgForm(false); qc.invalidateQueries({ queryKey: ['organizations'] }) }}
        />
      )}

      {tempPassword && (
        <TempPasswordModal email={tempPassword.email} password={tempPassword.password} onClose={() => setTempPassword(null)} />
      )}
    </div>
  )
}

function InviteUserModal({ roles, orgs, onClose, onCreated }: { roles: any[]; orgs: any[]; onClose: () => void; onCreated: (email: string, password: string) => void }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [roleName, setRoleName] = useState(roles[0]?.name || '')
  const [orgId, setOrgId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const submit = () => {
    if (!name.trim() || !email.trim()) {
      setError('Name and email are required.')
      return
    }
    const id = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '').slice(0, 32) || `user-${Date.now()}`
    setSubmitting(true)
    setError(null)
    api.createUser({ id, name: name.trim(), email: email.trim(), role_name: roleName || undefined, organization_id: orgId || undefined })
      .then((res: any) => onCreated(res.email, res.temporary_password))
      .catch((e: any) => setError(e?.response?.data?.detail || e?.message || 'Could not create this user.'))
      .finally(() => setSubmitting(false))
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,15,46,0.4)', backdropFilter: 'blur(8px)' }}>
      <div style={{ width: '90%', maxWidth: 440, background: '#fff', borderRadius: 16, padding: 28, position: 'relative', boxShadow: '0 16px 48px rgba(0,15,92,0.2)' }}>
        <button onClick={onClose} style={{ position: 'absolute', top: 16, right: 16, background: 'none', border: 'none', cursor: 'pointer' }}><X size={18} color="#8999b0" /></button>
        <h2 style={{ fontSize: 18, fontWeight: 800, color: '#0a0e27', marginBottom: 4 }}>Invite User</h2>
        <p style={{ fontSize: 12, color: '#8999b0', marginBottom: 20 }}>No email delivery is configured -- a real temporary password is generated and shown once; share it out of band.</p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: '#5b6382', marginBottom: 6 }}>Full name</label>
            <input className="glass-input" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Naina Singh" />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: '#5b6382', marginBottom: 6 }}>Email</label>
            <input className="glass-input" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="name@ulpf.local" />
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', fontSize: 12, color: '#5b6382', marginBottom: 6 }}>Role</label>
              <select className="glass-input" value={roleName} onChange={e => setRoleName(e.target.value)}>
                {roles.map(r => <option key={r.id} value={r.name}>{r.name}</option>)}
              </select>
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', fontSize: 12, color: '#5b6382', marginBottom: 6 }}>Organization</label>
              <select className="glass-input" value={orgId} onChange={e => setOrgId(e.target.value)}>
                <option value="">None</option>
                {orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            </div>
          </div>

          {error && <div style={{ color: '#c81e1e', fontSize: 12 }}>{error}</div>}

          <button onClick={submit} disabled={submitting} className="btn-primary" style={{ justifyContent: 'center', marginTop: 4 }}>
            {submitting ? 'Inviting…' : 'Invite User'}
          </button>
        </div>
      </div>
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
        <button onClick={onClose} style={{ position: 'absolute', top: 16, right: 16, background: 'none', border: 'none', cursor: 'pointer' }}><X size={18} color="#8999b0" /></button>
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

function TempPasswordModal({ email, password, onClose }: { email: string; password: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard?.writeText(password).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,15,46,0.4)', backdropFilter: 'blur(8px)' }}>
      <div style={{ width: '90%', maxWidth: 420, background: '#fff', borderRadius: 16, padding: 28, position: 'relative', boxShadow: '0 16px 48px rgba(0,15,92,0.2)' }}>
        <button onClick={onClose} style={{ position: 'absolute', top: 16, right: 16, background: 'none', border: 'none', cursor: 'pointer' }}><X size={18} color="#8999b0" /></button>
        <h2 style={{ fontSize: 18, fontWeight: 800, color: '#0a0e27', marginBottom: 8 }}>User Created</h2>
        <p style={{ fontSize: 13, color: '#5b6382', marginBottom: 16 }}>
          Share this temporary password with <strong>{email}</strong> -- it won't be shown again.
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: 'rgba(0,68,168,0.05)', borderRadius: 10, fontFamily: 'monospace', fontSize: 14 }}>
          <span style={{ flex: 1 }}>{password}</span>
          <button onClick={copy} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: '#0044A8' }}>
            {copied ? <Check size={16} /> : <Copy size={16} />}
          </button>
        </div>
      </div>
    </div>
  )
}
