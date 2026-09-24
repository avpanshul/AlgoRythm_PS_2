import { Globe, Zap, Lock, Shield, Layers, TrendingDown, Flag } from 'lucide-react'

const CARDS = [
  {
    icon: Globe,
    color: 'var(--color-text-primary)',
    title: 'Vendor-Neutral Interoperability',
    tag: 'Vendor-Neutral',
    tagClass: 'tag-neutral',
    body: `India's government infrastructure spans thousands of departments, each running different security tools — Palo Alto, Cisco, Fortinet, open-source IDS, custom Linux servers. ULPF connects all of them through a common schema without forcing replacement of any existing tool.`,
    impact: 'Eliminates vendor lock-in at the log normalization layer.',
  },
  {
    icon: Zap,
    color: '#f59e0b',
    title: 'Faster National Situational Awareness',
    tag: 'Scalable by Design',
    tagClass: 'tag-scale',
    body: `When logs from a Ministry firewall and a PSU intrusion detection system share the same normalized schema, cross-source correlation becomes as simple as a single query. ULPF's common event model is designed to support potential inter-organization correlation pilots.`,
    impact: 'Common schemas reduce detection latency across organizational boundaries.',
  },
  {
    icon: Shield,
    color: 'var(--color-text-primary)',
    title: 'Better Forensic Readiness',
    tag: 'Forensics-Grade',
    tagClass: 'tag-forensics',
    body: `ULPF preserves every raw log byte-for-byte in an immutable vault and computes SHA-256 event hashes with Merkle batch roots. This creates a verifiable chain of custody — making ULPF-produced evidence suitable for formal incident review and regulatory compliance processes.`,
    impact: 'Lossless preservation + tamper-evident hashing strengthens evidence handling.',
  },
  {
    icon: Lock,
    color: '#10b981',
    title: 'Privacy-Aware Data Sharing',
    tag: 'Privacy-Aware',
    tagClass: 'tag-privacy',
    body: `Redaction and pseudonymization policies allow analysts to work with rich, structured security data while reducing unnecessary exposure of IP addresses, user identities, and internal topology. Sensitive fields remain accessible only to authorized forensics officers via audited access channels.`,
    impact: 'Analysts get useful data; sensitive information stays protected by policy.',
  },
  {
    icon: TrendingDown,
    color: 'var(--color-text-primary)',
    title: 'Lower Onboarding Cost',
    tag: 'Extensible',
    tagClass: 'tag-explain',
    body: `The ULPF Parser Registry, auto-format detection, and mapping suggestion tools reduce the cost of onboarding new log sources from days of specialist effort to hours of guided configuration. Parser versioning and replay eliminate the need to re-ingest historical data when parsers improve.`,
    impact: 'Reduces dependency on specialized parser development teams for each new source.',
  },
  {
    icon: Layers,
    color: '#f43f5e',
    title: 'Sustainable Large-Scale Operation',
    tag: 'Scalable by Design',
    tagClass: 'tag-scale',
    body: `Tiered storage (hot in OpenSearch, cold in object storage), data quality scoring, and per-source health dashboards give operators clear visibility into logging costs and data fidelity. Organizations can make informed decisions about retention periods and storage allocation.`,
    impact: 'Data quality visibility and tiered storage help manage large-scale logging economics.',
  },
]

export default function NationalImpact() {
  return (
    <div>
      {/* Hero */}
      <div style={{ marginBottom: 36 }}>
        <div style={{ background: 'linear-gradient(135deg, transparent, transparent)', border: '1px solid transparent', borderRadius: 14, padding: '32px 36px', marginBottom: 28 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
            <div style={{ width: 44, height: 44, borderRadius: 10, background: 'linear-gradient(135deg,transparent,transparent)', border: '1px solid transparent', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Flag size={22} color="var(--color-text-primary)" />
            </div>
            <div>
              <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 2 }}>How ULPF Can Help India</h1>
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                SIH26156 · NTRO · National Cyber Resilience Infrastructure
              </div>
            </div>
          </div>
          <p style={{ fontSize: 14, color: 'var(--color-text-muted)', lineHeight: 1.8, maxWidth: 780 }}>
            ULPF is designed to support potential pilots by ministries, PSUs, sectoral CERTs, and critical-infrastructure operators seeking a vendor-neutral, privacy-aware, forensics-grade log management foundation. The sections below describe specific ways the framework addresses known operational gaps in India's heterogeneous cybersecurity ecosystem.
          </p>
          <div style={{ marginTop: 16, padding: '10px 16px', background: 'transparent', border: '1px solid transparent', borderRadius: 8, fontSize: 12, color: '#fbbf24' }}>
            <strong>Note:</strong> All statements are forward-looking design goals. ULPF does not claim official adoption by any government organization. References to ministries and PSUs describe intended use cases and potential beneficiary profiles.
          </div>
        </div>

        {/* Impact numbers strip */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 8 }}>
          {[
            { val: '50+', label: 'Log source types supportable via pluggable parsers' },
            { val: '100%', label: 'Raw log preservation — zero byte-level loss' },
            { val: 'SHA-256', label: 'Event-level integrity with Merkle batch roots' },
            { val: 'Replay', label: 'Historical re-processing without re-ingestion' },
          ].map(item => (
            <div key={item.val} className="glass-card" style={{ padding: '16px 18px', textAlign: 'center' }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--color-text-primary)', letterSpacing: '-0.5px', marginBottom: 4 }}>{item.val}</div>
              <div style={{ fontSize: 11, color: 'var(--color-text-muted)', lineHeight: 1.4 }}>{item.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Impact cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 18, marginBottom: 36 }}>
        {CARDS.map(card => {
          const Icon = card.icon
          return (
            <div key={card.title} className="impact-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ width: 36, height: 36, borderRadius: 8, background: `${card.color}18`, border: `1px solid ${card.color}40`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Icon size={18} color={card.color} />
                  </div>
                  <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-text-primary)' }}>{card.title}</span>
                </div>
                <span className={`tag-label ${card.tagClass}`}>{card.tag}</span>
              </div>
              <p style={{ fontSize: 13, color: 'var(--color-text-muted)', lineHeight: 1.7, marginBottom: 12 }}>{card.body}</p>
              <div style={{ padding: '8px 12px', background: `${card.color}0a`, border: `1px solid ${card.color}25`, borderRadius: 6, fontSize: 12, color: card.color }}>
                <strong>Key Impact:</strong> {card.impact}
              </div>
            </div>
          )
        })}
      </div>

      <div className="section-divider" />

      {/* Target stakeholders */}
      <div>
        <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 16 }}>Designed for India's Cybersecurity Ecosystem</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
          {[
            { title: 'Ministries & Departments', color: 'var(--color-text-primary)', items: ['Central government IT infrastructure', 'Ministry-level SOC operations', 'Policy enforcement and compliance logging', 'Inter-department log correlation pilots'] },
            { title: 'PSUs & Critical Infrastructure', color: '#10b981', items: ['Power, telecom, banking sector operators', 'Heterogeneous legacy system environments', 'OT/SCADA log normalization', 'Operational continuity and forensics'] },
            { title: 'CERTs & Sectoral SOCs', color: 'var(--color-text-primary)', items: ['CERT-In and sectoral CERT operations', 'Shared threat intelligence normalization', 'Multi-organization correlation readiness', 'Evidence handling for incident response'] },
          ].map(group => (
            <div key={group.title} className="glass-card" style={{ padding: 18 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: group.color, marginBottom: 12 }}>{group.title}</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {group.items.map(item => (
                  <div key={item} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 12, color: 'var(--color-text-muted)' }}>
                    <span style={{ color: group.color, marginTop: 1, flexShrink: 0 }}>›</span>
                    {item}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 20, padding: '16px 20px', background: 'transparent', border: '1px solid transparent', borderRadius: 10 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#10b981', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
            Deployment Philosophy
          </div>
          <div style={{ fontSize: 13, color: 'var(--color-text-muted)', lineHeight: 1.7 }}>
            ULPF is intentionally designed as an on-premise-first system. No logs leave the operator's network boundary. All processing, storage, and analytics run within the organization's own infrastructure. Cloud deployment is supported but never required. This aligns with the data residency and sovereignty requirements typical of Indian government cybersecurity mandates.
          </div>
        </div>
      </div>
    </div>
  )
}
