import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { ShieldCheck, ShieldAlert, RotateCcw, Play, RefreshCw, Hash, Cpu, FileWarning, Search } from 'lucide-react'
import { GlassCard } from '../components/glass/GlassCard'

export default function ReplayCenter() {
  const qc = useQueryClient()
  const [verifyId, setVerifyId] = useState('')
  const [proofId, setProofId] = useState<string | null>(null)
  
  const { data: replayJobs } = useQuery({ queryKey: ['replayJobs'], queryFn: () => api.getReplayJobs() })
  // status: 'failed' -- without it, /dlq's total counts every row ever
  // written including already-resolved retries, wildly overstating current
  // failures (see the same fix in FailedEvents.tsx for the full story).
  const { data: dlqEvents = { items: [], total: 0 } } = useQuery({ queryKey: ['dlq', 'failed'], queryFn: () => api.getDlq({ status: 'failed' }) })
  const [auditSearch, setAuditSearch] = useState('')
  const { data: auditLogs } = useQuery({
    queryKey: ['auditLogs', auditSearch],
    queryFn: () => api.getAuditLogs(auditSearch ? { q: auditSearch } : undefined),
    retry: false,
  })
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: api.getCurrentUser, retry: false })

  const [isVerifying, setIsVerifying] = useState(false)
  const [verifyResult, setVerifyResult] = useState<any>(null)
  const [verifyError, setVerifyError] = useState<string | null>(null)
  const [startingJob, setStartingJob] = useState(false)

  const handleVerify = () => {
    if (!verifyId.trim()) return
    setIsVerifying(true)
    setVerifyResult(null)
    setVerifyError(null)
    api.getEventProof(verifyId.trim())
      .then(setVerifyResult)
      .catch((e: any) => setVerifyError(e?.response?.data?.detail || e?.message || 'No Merkle proof found for this event ID.'))
      .finally(() => setIsVerifying(false))
  }

  const startReplayJob = () => {
    setStartingJob(true)
    api.createReplayJob({ requested_by: me?.id || me?.email })
      .then(() => qc.invalidateQueries({ queryKey: ['replayJobs'] }))
      .finally(() => setStartingJob(false))
  }

  const runJobNow = (id: number) => {
    api.runReplayJob(id).then(() => qc.invalidateQueries({ queryKey: ['replayJobs'] }))
  }

  const retryDlqEvent = (id: number) => {
    api.retryDlq(id).then(() => qc.invalidateQueries({ queryKey: ['dlq'] }))
  }

  const jobs = replayJobs?.items || []
  const logs = auditLogs?.items || []

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <header style={{ 
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, 
        position: 'sticky', top: 0, zIndex: 50, 
        background: 'rgba(238, 242, 246, 0.9)', backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)',
        padding: '16px', margin: '-16px -16px 24px -16px', borderRadius: 12,
        boxShadow: '0 4px 20px rgba(0,0,0,0.02)'
      }}>
        <div>
          <h1 style={{ fontSize: 'clamp(40px, 4vw, 52px)', fontWeight: 800, color: '#0044A8', letterSpacing: '-0.03em', lineHeight: 1.1 }}>
            Integrity & Replay
          </h1>
          <p style={{ fontSize: 'clamp(12px, 0.85vw, 13px)', color: '#8999b0', marginTop: 3 }}>
            Verify log provenance, reprocess events, and manage dead-letter queues.
          </p>
        </div>
      </header>

      <div id="integrity" style={{ scrollMarginTop: 120 }}>
        <h2 style={{ fontSize: 24, fontWeight: 800, color: '#0a0e27', marginBottom: 16 }}>Integrity Verification</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
          <GlassCard style={{ padding: 24 }}>
            <h3 className="section-heading" style={{ marginBottom: 12 }}>Verify Event Integrity</h3>
            <p style={{ fontSize: 13, color: '#5b6382', marginBottom: 24 }}>
              Enter an event ID to fetch its Merkle inclusion proof and verify the raw event has not been tampered with.
            </p>
            <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
              <input 
                type="text" 
                placeholder="evt_xxxx_xxxx" 
                value={verifyId}
                onChange={e => setVerifyId(e.target.value)}
                style={{
                  flex: 1, padding: '12px 16px', borderRadius: 10, border: '1px solid rgba(0,68,168,0.2)',
                  background: 'rgba(255,255,255,0.7)', fontSize: 14, fontFamily: 'monospace', outline: 'none'
                }}
              />
              <button 
                onClick={handleVerify}
                disabled={!verifyId || isVerifying}
                style={{
                  padding: '0 24px', borderRadius: 10, border: 'none',
                  background: 'linear-gradient(135deg, #0044A8, #0088FF)',
                  color: '#fff', fontWeight: 600, fontSize: 14, cursor: 'pointer',
                  opacity: (!verifyId || isVerifying) ? 0.7 : 1
                }}
              >
                {isVerifying ? 'Verifying...' : 'Verify'}
              </button>
            </div>
          </GlassCard>
          
          <GlassCard style={{ padding: 24, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 300 }}>
            {isVerifying ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
                <RefreshCw size={40} color="#0044A8" className="animate-spin" style={{ animation: 'spin 1s linear infinite' }} />
                <div style={{ fontSize: 14, color: '#0044A8', fontWeight: 600 }}>Fetching real Merkle proof...</div>
              </div>
            ) : verifyError ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, textAlign: 'center', padding: '0 16px' }}>
                <ShieldAlert size={40} color="#c81e1e" />
                <div style={{ fontSize: 14, color: '#0a0e27', fontWeight: 600 }}>Not Verified</div>
                <div style={{ fontSize: 12, color: '#8999b0' }}>{verifyError}</div>
              </div>
            ) : verifyResult ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16, width: '100%' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                  <div style={{ width: 48, height: 48, borderRadius: '50%', background: verifyResult.included ? 'rgba(5,122,85,0.1)' : 'rgba(217,119,6,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {verifyResult.included ? <ShieldCheck size={24} color="#057a55" /> : <ShieldAlert size={24} color="#d97706" />}
                  </div>
                  <div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: verifyResult.included ? '#057a55' : '#d97706' }}>
                      {verifyResult.included ? 'Real Merkle Proof Found' : 'Not Yet in a Checkpoint'}
                    </div>
                    <div style={{ fontSize: 12, color: '#8999b0' }}>
                      {verifyResult.included ? "From this deployment's own checkpoint ledger." : (verifyResult.reason || 'This event has not been sealed into a signed checkpoint yet.')}
                    </div>
                  </div>
                </div>
                <pre style={{ background: 'rgba(0,68,168,0.03)', border: '1px solid rgba(0,68,168,0.1)', padding: 12, borderRadius: 8, fontSize: 11, fontFamily: 'monospace', color: '#0a0e27', wordBreak: 'break-all', whiteSpace: 'pre-wrap', margin: 0, maxHeight: 220, overflowY: 'auto' }}>
                  {JSON.stringify(verifyResult, null, 2)}
                </pre>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, opacity: 0.5 }}>
                <Hash size={48} color="#0044A8" />
                <div style={{ fontSize: 14, color: '#0a0e27', fontWeight: 600 }}>Awaiting Event ID</div>
              </div>
            )}
          </GlassCard>
        </div>
      </div>

      <div id="replay" style={{ scrollMarginTop: 120 }}>
        <h2 style={{ fontSize: 24, fontWeight: 800, color: '#0a0e27', marginBottom: 16 }}>Replay Jobs</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button onClick={startReplayJob} disabled={startingJob} style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '10px 20px', borderRadius: 10,
              background: 'linear-gradient(135deg, #0044A8, #0088FF)', border: 'none',
              color: '#fff', fontWeight: 600, fontSize: 13, cursor: startingJob ? 'not-allowed' : 'pointer',
              boxShadow: '0 4px 12px rgba(0,68,168,0.2)', opacity: startingJob ? 0.7 : 1,
            }}>
              <RotateCcw size={16} /> {startingJob ? 'Starting…' : 'Start Replay Job'}
            </button>
          </div>
          <GlassCard style={{ padding: 0, overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
              <thead>
                <tr style={{ background: 'rgba(0,68,168,0.03)', borderBottom: '1px solid rgba(0,68,168,0.1)', color: '#5b6382' }}>
                  <th style={{ padding: '16px', fontWeight: 600 }}>Job ID</th>
                  <th style={{ padding: '16px', fontWeight: 600 }}>Target Source</th>
                  <th style={{ padding: '16px', fontWeight: 600 }}>Progress</th>
                  <th style={{ padding: '16px', fontWeight: 600 }}>Status</th>
                  <th style={{ padding: '16px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.length === 0 ? (
                  <tr>
                    <td colSpan={5} style={{ padding: 32, textAlign: 'center', color: '#8999b0' }}>
                      <Cpu size={32} color="#0044A8" style={{ opacity: 0.3, margin: '0 auto 12px' }} />
                      No replay jobs history found.
                    </td>
                  </tr>
                ) : (
                  jobs.map((job: any) => (
                    <tr key={job.id} style={{ borderBottom: '1px solid rgba(0,68,168,0.05)' }}>
                      <td style={{ padding: '16px', fontWeight: 600, color: '#0a0e27', fontFamily: 'monospace' }}>#{job.id}</td>
                      <td style={{ padding: '16px', color: '#5b6382' }}>All Sources</td>
                      <td style={{ padding: '16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'rgba(0,68,168,0.1)', overflow: 'hidden' }}>
                            <div style={{ width: `${(job.processed_events / Math.max(1, job.total_events)) * 100}%`, height: '100%', background: '#0044A8' }} />
                          </div>
                          <span style={{ fontSize: 11, fontWeight: 600, color: '#0a0e27', width: 40 }}>
                            {Math.round((job.processed_events / Math.max(1, job.total_events)) * 100)}%
                          </span>
                        </div>
                      </td>
                      <td style={{ padding: '16px' }}>
                        <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: job.status === 'completed' ? 'rgba(5,122,85,0.1)' : 'rgba(217,119,6,0.1)', color: job.status === 'completed' ? '#057a55' : '#d97706', textTransform: 'uppercase' }}>
                          {job.status}
                        </span>
                      </td>
                      <td style={{ padding: '16px', textAlign: 'right' }}>
                        {job.status === 'pending' && (
                          <button onClick={() => runJobNow(job.id)} style={{ padding: '4px 12px', borderRadius: 6, background: '#0044A8', color: '#fff', border: 'none', cursor: 'pointer', fontSize: 11, fontWeight: 600 }}>Run Now</button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </GlassCard>
        </div>
      </div>

      <div id="dlq" style={{ scrollMarginTop: 120 }}>
        <h2 style={{ fontSize: 24, fontWeight: 800, color: '#0a0e27', marginBottom: 16 }}>Dead Letter Queue (DLQ)</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <div style={{ display: 'flex', gap: 24 }}>
            <GlassCard style={{ flex: 1 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#5b6382', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Total Failed Events</div>
              <div style={{ fontSize: 32, fontWeight: 700, color: '#c81e1e' }}>{dlqEvents.total.toLocaleString()}</div>
            </GlassCard>
          </div>
          <GlassCard style={{ padding: 0, overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
              <thead>
                <tr style={{ background: 'rgba(0,68,168,0.03)', borderBottom: '1px solid rgba(0,68,168,0.1)', color: '#5b6382' }}>
                  <th style={{ padding: '16px', fontWeight: 600 }}>Event ID</th>
                  <th style={{ padding: '16px', fontWeight: 600 }}>Failure Reason</th>
                  <th style={{ padding: '16px', fontWeight: 600 }}>Timestamp</th>
                  <th style={{ padding: '16px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {dlqEvents.items.length === 0 ? (
                  <tr>
                    <td colSpan={4} style={{ padding: 32, textAlign: 'center', color: '#8999b0' }}>
                      <FileWarning size={32} color="#057a55" style={{ opacity: 0.5, margin: '0 auto 12px' }} />
                      No failed events in DLQ. Everything is processing smoothly.
                    </td>
                  </tr>
                ) : (
                  dlqEvents.items.map((f: any, i: number) => (
                    <tr key={i} style={{ borderBottom: '1px solid rgba(0,68,168,0.05)' }}>
                      <td style={{ padding: '16px', fontWeight: 600, color: '#0a0e27', fontFamily: 'monospace' }}>{f.event_id}</td>
                      <td style={{ padding: '16px' }}>
                        <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: 'rgba(200,30,30,0.1)', color: '#c81e1e' }}>
                          {f.failure_reason}
                        </span>
                      </td>
                      <td style={{ padding: '16px', color: '#5b6382' }}>{new Date(f.created_at).toLocaleString()}</td>
                      <td style={{ padding: '16px', textAlign: 'right' }}>
                        <button onClick={() => retryDlqEvent(f.id)} style={{ padding: '6px 12px', borderRadius: 6, background: 'transparent', border: '1px solid rgba(0,68,168,0.2)', color: '#0044A8', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>Retry</button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </GlassCard>
        </div>
      </div>

      <div id="audit" style={{ scrollMarginTop: 120 }}>
        <h2 style={{ fontSize: 24, fontWeight: 800, color: '#0a0e27', marginBottom: 16 }}>Audit Logs</h2>
        <GlassCard style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: 16, borderBottom: '1px solid rgba(0,68,168,0.1)', display: 'flex', alignItems: 'center', gap: 12 }}>
            <Search size={16} color="#8999b0" />
            <input
              type="text" placeholder="Search audit logs..." value={auditSearch} onChange={e => setAuditSearch(e.target.value)}
              style={{ border: 'none', background: 'transparent', outline: 'none', fontSize: 14, flex: 1, color: '#0a0e27' }}
            />
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
            <thead>
              <tr style={{ background: 'rgba(0,68,168,0.03)', borderBottom: '1px solid rgba(0,68,168,0.1)', color: '#5b6382' }}>
                <th style={{ padding: '16px', fontWeight: 600 }}>Timestamp</th>
                <th style={{ padding: '16px', fontWeight: 600 }}>User</th>
                <th style={{ padding: '16px', fontWeight: 600 }}>Action</th>
                <th style={{ padding: '16px', fontWeight: 600 }}>Entity</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ padding: 32, textAlign: 'center', color: '#8999b0' }}>
                    {auditSearch ? `No audit log entries match "${auditSearch}".` : 'No audit log entries yet.'}
                  </td>
                </tr>
              ) : (
                logs.map((r: any, i: number) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(0,68,168,0.05)' }}>
                    <td style={{ padding: '16px', color: '#5b6382', fontFamily: 'monospace' }}>{r.timestamp ? new Date(r.timestamp).toLocaleString() : '—'}</td>
                    <td style={{ padding: '16px', fontWeight: 600, color: '#0a0e27' }}>{r.user}</td>
                    <td style={{ padding: '16px' }}>
                      <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: 'rgba(0,68,168,0.1)', color: '#0044A8' }}>
                        {r.action}
                      </span>
                    </td>
                    <td style={{ padding: '16px', color: '#0a0e27', fontFamily: 'monospace' }}>{r.entity_id}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          </GlassCard>
      </div>
    </div>
  )
}
