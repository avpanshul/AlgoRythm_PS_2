import { useQuery } from '@tanstack/react-query'
import { useParams, Link } from 'react-router-dom'
import { api } from '../api/client'
import { useState } from 'react'
import { GlassCard } from '../components/glass/GlassCard'
import { anonymizedVendorLabel } from '../utils/anonymize'
import {
  ShieldCheck, ArrowLeft, Lock, FileCode, CheckCircle2,
  Clock, Server, Eye, Download, RefreshCw, Key, Shield
} from 'lucide-react'

export default function EventDetail() {
  const { id } = useParams<{ id: string }>()
  const [activeTab, setActiveTab] = useState<'overview' | 'raw' | 'normalized' | 'provenance' | 'integrity'>('overview')

  const { data: event, isLoading: eventLoading } = useQuery({
    queryKey: ['event', id],
    queryFn: () => api.getEvent(id!),
    enabled: !!id,
  })

  const { data: trace } = useQuery({
    queryKey: ['eventTrace', id],
    queryFn: () => api.getEventTrace(id!),
    enabled: !!id,
    retry: false,
  })

  const { data: proof } = useQuery({
    queryKey: ['eventProof', id],
    queryFn: () => api.getEventProof(id!),
    enabled: !!id,
    retry: false,
  })

  const { data: rawEvent } = useQuery({
    queryKey: ['eventRaw', id],
    queryFn: () => api.getRawEvent(id!),
    enabled: !!id,
    retry: false,
  })

  if (eventLoading) {
    return (
      <div style={{ padding: 40, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ height: 24, width: 200, borderRadius: 8, background: 'rgba(0,68,168,0.08)', animation: 'shimmer 1.5s infinite' }} />
        <div style={{ height: 200, borderRadius: 16, background: 'rgba(0,68,168,0.06)', animation: 'shimmer 1.5s infinite' }} />
      </div>
    )
  }

  if (!event) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <h2 className="section-heading">Event Not Found</h2>
        <p style={{ fontSize: 13, color: '#8999b0', margin: '8px 0 16px' }}>Event ID: {id}</p>
        <Link to="/sources" style={{ fontSize: 12, color: '#0044A8', fontWeight: 600 }}>← Back to Data Sources</Link>
      </div>
    )
  }

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'raw', label: 'Raw Payload' },
    { id: 'normalized', label: 'Normalized ECS' },
    { id: 'provenance', label: 'Provenance Trace' },
    { id: 'integrity', label: 'Merkle Integrity' },
  ] as const

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <Link to="/sources" style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#0044A8', fontWeight: 600 }}>
          <ArrowLeft size={14} /> Back to Data Sources
        </Link>
      </div>

      <GlassCard variant="ultra" size="none" style={{ padding: 'clamp(20px, 2.5vw, 28px)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{
              width: 48, height: 48, borderRadius: 14,
              background: 'linear-gradient(135deg, #0044A8, #0066DD)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 4px 16px rgba(0,68,168,0.3)',
            }}>
              <Shield size={24} color="#fff" />
            </div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#8999b0' }}>
                Event Investigation
              </div>
              <h1 style={{ fontSize: 'clamp(36px, 3.6vw, 44px)', fontWeight: 800, color: '#0a0e27', letterSpacing: '-0.02em', marginTop: 2 }}>
                {event.event?.category || event.event?.type || 'Canonical Log Event'}
              </h1>
              <div style={{ fontSize: 11, color: '#8999b0', marginTop: 4, fontFamily: 'monospace' }}>
                ID: {event.event_id}
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <a href={api.getEvidenceBundleUrl(event.event_id)} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>
              <GlassCard variant="base" size="none" style={{
                padding: '8px 16px', background: 'linear-gradient(135deg, #0044A8, #0066DD)',
                border: '1px solid rgba(0,68,168,0.4)', color: '#fff', fontSize: 12, fontWeight: 600,
                display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer',
              }}>
                <Download size={14} /> Download Evidence Bundle
              </GlassCard>
            </a>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, borderBottom: '1px solid rgba(0,68,168,0.1)', marginTop: 24, paddingBottom: 2, overflowX: 'auto' }}>
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '8px 16px', borderRadius: '10px 10px 0 0',
                fontSize: 12, fontWeight: activeTab === tab.id ? 700 : 500,
                color: activeTab === tab.id ? '#0044A8' : '#8999b0',
                background: activeTab === tab.id ? 'rgba(0,68,168,0.08)' : 'transparent',
                border: 'none', borderBottom: activeTab === tab.id ? '2px solid #0044A8' : '2px solid transparent',
                cursor: 'pointer', transition: 'all 0.2s ease', whiteSpace: 'nowrap',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </GlassCard>

      {activeTab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
          {[
            { label: 'Timestamp', value: event.timestamp ? new Date(event.timestamp).toLocaleString() : '—' },
            { label: 'Parser', value: event.parser?.parser_id || '—' },
            { label: 'Device Vendor', value: event.device?.vendor ? anonymizedVendorLabel(event.device.vendor) : '—' },
            { label: 'Source IP', value: event.source?.ip || '—' },
            { label: 'Destination IP', value: event.destination?.ip || '—' },
            { label: 'Risk Level', value: event.risk?.level || 'LOW' },
          ].map(item => (
            <GlassCard key={item.label} variant="elevated" size="md">
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#8999b0', marginBottom: 4 }}>
                {item.label}
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#0a0e27' }}>
                {item.value}
              </div>
            </GlassCard>
          ))}
        </div>
      )}

      {activeTab === 'raw' && (
        <GlassCard variant="elevated" size="none" style={{ padding: 20 }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#8999b0', marginBottom: 12 }}>
            Raw Unaltered Payload
          </div>
          <pre style={{
            fontFamily: 'monospace', fontSize: 12, padding: 16, borderRadius: 12,
            background: 'rgba(240,246,255,0.8)', border: '1px solid rgba(0,68,168,0.12)',
            color: '#0a0e27', overflowX: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          }}>
            {rawEvent?.raw_content || 'Raw payload unavailable -- it may have been retired from the raw vault under a retention policy.'}
          </pre>
        </GlassCard>
      )}

      {activeTab === 'normalized' && (
        <GlassCard variant="elevated" size="none" style={{ padding: 20 }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#8999b0', marginBottom: 12 }}>
            Canonical OCSF / ECS Normalized JSON
          </div>
          <pre style={{
            fontFamily: 'monospace', fontSize: 12, padding: 16, borderRadius: 12,
            background: 'rgba(240,246,255,0.8)', border: '1px solid rgba(0,68,168,0.12)',
            color: '#0a0e27', overflowX: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          }}>
            {JSON.stringify(event.normalized || event, null, 2)}
          </pre>
        </GlassCard>
      )}

      {activeTab === 'provenance' && (
        <GlassCard variant="elevated" size="none" style={{ padding: 20 }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#8999b0', marginBottom: 16 }}>
            End-to-End Lineage & Provenance Trace
          </div>
          {trace ? (
            <pre style={{ fontFamily: 'monospace', fontSize: 12, padding: 16, borderRadius: 12, background: 'rgba(240,246,255,0.8)', color: '#0a0e27' }}>
              {JSON.stringify(trace, null, 2)}
            </pre>
          ) : (
            <div style={{ padding: 24, textAlign: 'center', color: '#8999b0', fontSize: 12 }}>
              No lineage trace available for this event yet.
            </div>
          )}
        </GlassCard>
      )}

      {activeTab === 'integrity' && (
        <GlassCard variant="elevated" size="none" style={{ padding: 20 }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#8999b0', marginBottom: 16 }}>
            Cryptographic Merkle Proof
          </div>
          {proof ? (
            <pre style={{ fontFamily: 'monospace', fontSize: 12, padding: 16, borderRadius: 12, background: 'rgba(240,246,255,0.8)', color: '#0a0e27' }}>
              {JSON.stringify(proof, null, 2)}
            </pre>
          ) : (
            <div style={{ padding: 24, textAlign: 'center', color: '#8999b0', fontSize: 12 }}>
              No Merkle proof available yet -- this event hasn't been included in a signed integrity checkpoint.
            </div>
          )}
        </GlassCard>
      )}
    </div>
  )
}
