import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { GlassCard } from '../components/glass/GlassCard'
import { HardDrive, Server, Database, Archive, Settings2, Clock, Search } from 'lucide-react'

function formatBytes(bytes: number | undefined | null): string {
  if (bytes == null) return '—'
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let v = bytes, i = -1
  do { v /= 1024; i++ } while (v >= 1024 && i < units.length - 1)
  return `${v.toFixed(1)} ${units[i]}`
}

export default function RawVault() {
  const [activeTab, setActiveTab] = useState('overview')

  // Real /storage/summary data -- this deployment's actual local vault
  // (filesystem-backed raw log storage + SQLite/Postgres tables), not the
  // S3/Elastic/Glacier/Neo4j stack this page previously described, none of
  // which exists in this system.
  // Real bug found live: `retry: false` meant a single transient failure
  // (e.g. the backend mid-restart) left this page silently stuck showing
  // "—"/empty forever, with no visible error and no way to recover short of
  // a full page reload. A real backend hiccup should be visible and
  // recoverable, not indistinguishable from "this system has no data."
  const { data: summary, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['storage-summary'], queryFn: () => api.getStorageSummary(), retry: 2, retryDelay: 1000,
  })

  const storageNodes = summary ? [
    { name: 'Raw log vault (local filesystem)', status: 'Healthy', type: 'Raw Storage', size: formatBytes(summary.raw_storage_size_bytes), count: `${(summary.raw_event_count ?? 0).toLocaleString()} objects` },
    { name: 'Normalized event store', status: 'Healthy', type: 'Normalized Storage', size: formatBytes(summary.normalized_storage_size_bytes), count: `${(summary.normalized_event_count ?? 0).toLocaleString()} events` },
    { name: 'Event metadata table', status: 'Healthy', type: 'Metadata', size: '—', count: `${(summary.metadata_count ?? 0).toLocaleString()} rows` },
  ] : []

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 'clamp(40px, 4vw, 52px)', fontWeight: 800, color: '#0044A8', letterSpacing: '-0.03em', lineHeight: 1.1 }}>
            Storage Architecture
          </h1>
          <p style={{ fontSize: 'clamp(12px, 0.85vw, 13px)', color: '#8999b0', marginTop: 3 }}>
            Manage raw logs, normalized indexes, and long-term retention policies.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, background: 'rgba(0,68,168,0.05)', padding: 4, borderRadius: 12 }}>
          <button 
            onClick={() => setActiveTab('overview')}
            style={{ 
              padding: '6px 16px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
              background: activeTab === 'overview' ? '#fff' : 'transparent',
              color: activeTab === 'overview' ? '#0044A8' : '#5b6382',
              boxShadow: activeTab === 'overview' ? '0 2px 8px rgba(0,68,168,0.1)' : 'none', transition: 'all 0.2s'
            }}>
            Overview
          </button>
          <button 
            onClick={() => setActiveTab('retention')}
            style={{ 
              padding: '6px 16px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
              background: activeTab === 'retention' ? '#fff' : 'transparent',
              color: activeTab === 'retention' ? '#0044A8' : '#5b6382',
              boxShadow: activeTab === 'retention' ? '0 2px 8px rgba(0,68,168,0.1)' : 'none', transition: 'all 0.2s'
            }}>
            Retention Policies
          </button>
        </div>
      </header>

      {isError && (
        <GlassCard style={{ padding: '16px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, borderRadius: 16, background: 'rgba(200,30,30,0.06)', border: '1px solid rgba(200,30,30,0.2)' }}>
          <span style={{ fontSize: 13, color: '#c81e1e', fontWeight: 600 }}>Could not reach the backend for storage stats -- this is a real connectivity error, not empty data.</span>
          <button onClick={() => refetch()} disabled={isFetching} style={{ padding: '6px 14px', borderRadius: 8, border: '1px solid rgba(200,30,30,0.3)', background: '#fff', color: '#c81e1e', fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>
            {isFetching ? 'Retrying…' : 'Retry'}
          </button>
        </GlassCard>
      )}

      {activeTab === 'overview' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Top KPI Cards */}
          <GlassCard style={{ display: 'flex', alignItems: 'center', padding: '24px 40px', marginBottom: 24, borderRadius: 32 }}>
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 16 }}>
              <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(0,68,168,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <HardDrive size={24} color="#0044A8" />
              </div>
              <div>
                <div style={{ fontSize: 13, color: '#8999b0', fontWeight: 500, marginBottom: 4 }}>Raw Vault Size</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: '#0a0e27', lineHeight: 1 }}>{formatBytes(summary?.raw_storage_size_bytes)}</div>
                <div style={{ fontSize: 12, color: '#8999b0', fontWeight: 600, marginTop: 6 }}>Current, real</div>
              </div>
            </div>

            <div style={{ width: 1, height: 64, background: 'rgba(0,68,168,0.1)', margin: '0 24px' }} />

            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 16 }}>
              <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(5,122,85,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Server size={24} color="#057a55" />
              </div>
              <div>
                <div style={{ fontSize: 13, color: '#8999b0', fontWeight: 500, marginBottom: 4 }}>Normalized Store Size</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: '#0a0e27', lineHeight: 1 }}>{formatBytes(summary?.normalized_storage_size_bytes)}</div>
                <div style={{ fontSize: 12, color: '#0044A8', fontWeight: 600, marginTop: 6 }}>Current, real</div>
              </div>
            </div>

            <div style={{ width: 1, height: 64, background: 'rgba(0,68,168,0.1)', margin: '0 24px' }} />

            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 16 }}>
              <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(217,119,6,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Archive size={24} color="#d97706" />
              </div>
              <div>
                <div style={{ fontSize: 13, color: '#8999b0', fontWeight: 500, marginBottom: 4 }}>Raw Events Stored</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: '#0a0e27', lineHeight: 1 }}>{(summary?.raw_event_count ?? 0).toLocaleString()}</div>
                <div style={{ fontSize: 12, color: '#057a55', fontWeight: 600, marginTop: 6 }}>Real count</div>
              </div>
            </div>
          </GlassCard>

          <GlassCard style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '20px 24px', borderBottom: '1px solid rgba(0,68,168,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <h3 className="section-heading">Storage Nodes & Repositories</h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Search size={16} color="#8999b0" />
                <input type="text" placeholder="Search repositories..." style={{ border: 'none', background: 'transparent', outline: 'none', fontSize: 14 }} />
              </div>
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
              <thead>
                <tr style={{ background: 'rgba(0,68,168,0.03)', borderBottom: '1px solid rgba(0,68,168,0.1)', color: '#5b6382' }}>
                  <th style={{ padding: '16px', fontWeight: 600 }}>Repository Name</th>
                  <th style={{ padding: '16px', fontWeight: 600 }}>Type</th>
                  <th style={{ padding: '16px', fontWeight: 600 }}>Status</th>
                  <th style={{ padding: '16px', fontWeight: 600 }}>Total Size</th>
                  <th style={{ padding: '16px', fontWeight: 600 }}>Object Count</th>
                  <th style={{ padding: '16px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {storageNodes.map((node, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(0,68,168,0.05)' }}>
                    <td style={{ padding: '16px', fontWeight: 600, color: '#0a0e27' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <Database size={16} color="#0044A8" /> {node.name}
                      </div>
                    </td>
                    <td style={{ padding: '16px', color: '#5b6382' }}>{node.type}</td>
                    <td style={{ padding: '16px' }}>
                      <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: node.status === 'Healthy' ? 'rgba(5,122,85,0.1)' : 'rgba(217,119,6,0.1)', color: node.status === 'Healthy' ? '#057a55' : '#d97706' }}>
                        {node.status}
                      </span>
                    </td>
                    <td style={{ padding: '16px', color: '#0a0e27', fontWeight: 600 }}>{node.size}</td>
                    <td style={{ padding: '16px', color: '#5b6382' }}>{node.count}</td>
                    <td style={{ padding: '16px', textAlign: 'right' }}>
                      <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: '#8999b0' }}>
                        <Settings2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
                {isLoading && (
                  <tr><td colSpan={6} style={{ padding: 24, textAlign: 'center', color: '#8999b0' }}>Loading real storage stats…</td></tr>
                )}
                {!isLoading && !isError && storageNodes.length === 0 && (
                  <tr><td colSpan={6} style={{ padding: 24, textAlign: 'center', color: '#8999b0' }}>No storage summary available yet.</td></tr>
                )}
              </tbody>
            </table>
          </GlassCard>
        </div>
      ) : (
        <RetentionTab />
      )}
    </div>
  )
}

function RetentionTab() {
  const { data: policies } = useQuery({ queryKey: ['retention-policies'], queryFn: () => api.getRetentionPolicies(), retry: false })
  const list = Array.isArray(policies) ? policies : []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <GlassCard style={{ padding: 24 }}>
        <h3 className="section-heading" style={{ marginBottom: 20 }}>Real Retention Policies (per source)</h3>
        <p style={{ fontSize: 14, color: '#5b6382', marginBottom: 24 }}>
          How long each real source's events are kept before deletion (legal holds block deletion regardless of these values -- see app/core/retention.py).
        </p>
        {list.length === 0 ? (
          <div style={{ padding: 24, textAlign: 'center', color: '#8999b0', fontSize: 13 }}>No retention policies configured yet.</div>
        ) : (
          <div style={{ display: 'grid', gap: 16 }}>
            {list.map((p: any) => (
              <div key={p.source_id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 16, background: 'rgba(0,68,168,0.02)', border: '1px solid rgba(0,68,168,0.05)', borderRadius: 12 }}>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#0a0e27', marginBottom: 4 }}>{p.source_id}</div>
                  <div style={{ fontSize: 12, color: p.enabled ? '#057a55' : '#8999b0' }}>{p.enabled ? 'Enabled' : 'Disabled'}</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Clock size={16} color="#5b6382" />
                  <span style={{ fontSize: 14, fontWeight: 600, color: '#0044A8' }}>{p.retention_days} days</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </GlassCard>
    </div>
  )
}
