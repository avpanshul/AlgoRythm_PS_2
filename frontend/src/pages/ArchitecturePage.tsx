import { ExternalLink, Server, Cpu, Database, ArrowRight, Shield, Eye, Layers, Package } from 'lucide-react'

interface LayerProps {
  title: string
  color: string
  bg: string
  nodes: string[]
}

function ArchLayer({ title, color, bg, nodes }: LayerProps) {
  return (
    <div className="arch-layer" style={{ background: bg, border: `1px solid ${color}40`, minWidth: 170 }}>
      <div className="arch-layer-header" style={{ background: `${color}22`, color }}>
        {title}
      </div>
      <div className="arch-layer-body">
        {nodes.map(n => (
          <div key={n} className="arch-node" style={{ borderLeftColor: color }}>
            {n}
          </div>
        ))}
      </div>
    </div>
  )
}

const LAYERS: LayerProps[] = [
  {
    title: 'Log Sources',
    color: 'var(--color-text-primary)',
    bg: 'transparent',
    nodes: ['Firewalls / IDS / IPS', 'Linux / Windows Servers', 'Cloud & SaaS APIs', 'Proxy / VPN / NetFlow', 'Applications & DBs', 'OT / SCADA Devices'],
  },
  {
    title: 'Collectors',
    color: 'var(--color-text-primary)',
    bg: 'transparent',
    nodes: ['rsyslog / syslog-ng', 'Custom Go/Python Agent', 'API Pull Connector', 'File Upload Endpoint', 'Beats / Fluentd shim'],
  },
  {
    title: 'Streaming Ingestion',
    color: '#f59e0b',
    bg: 'transparent',
    nodes: ['Kafka / Redpanda', 'raw_logs topic', 'retry topic', 'dead-letter topic', 'Schema registry'],
  },
  {
    title: 'ULPF Core',
    color: 'var(--color-text-primary)',
    bg: 'transparent',
    nodes: [
      'Parser Engine',
      'Parser Registry',
      'ECS-like Schema Normalizer',
      'Privacy & Redaction Engine',
      'Integrity Service (SHA-256 + Merkle)',
      'Data Quality Engine',
      'Correlation & Anomaly Engine',
      'Lineage & Metadata Service',
      'Replay Service',
    ],
  },
  {
    title: 'Storage',
    color: '#10b981',
    bg: 'transparent',
    nodes: ['Raw Event Vault (MinIO / S3)', 'Normalized Store (OpenSearch)', 'Metadata & Policies (PostgreSQL)', 'Correlation State (Redis)', 'Parquet / Data Lake'],
  },
  {
    title: 'Outputs',
    color: 'var(--color-text-primary)',
    bg: 'transparent',
    nodes: ['ULPF Web Console', 'SIEM Integration', 'Data Lake / Parquet Export', 'REST / gRPC APIs', 'Evidence Export Package', 'Grafana Dashboards'],
  },
]

const RESOURCES = [
  { title: 'Elastic Common Schema (ECS)', url: 'https://www.elastic.co/guide/en/ecs/current/index.html', desc: 'The reference schema ULPF models its normalized event structure after. ECS provides standardized field names across all log types.' },
  { title: 'Open Cybersecurity Schema Framework (OCSF)', url: 'https://schema.ocsf.io/', desc: 'Alternative vendor-neutral security schema specification from AWS, Splunk, IBM and others. Used as a secondary reference.' },
  { title: 'SIH 2026 Problem Statement PS26156', url: 'https://sih.gov.in/', desc: 'The official problem statement from NTRO for Smart India Hackathon 2026 that motivated this framework design.' },
  { title: 'Apache Kafka Documentation', url: 'https://kafka.apache.org/documentation/', desc: 'Core streaming platform used for log ingestion pipeline — raw_logs, retry, and dead-letter topics.' },
  { title: 'OpenSearch Documentation', url: 'https://opensearch.org/docs/latest/', desc: 'Normalized event storage and search backend for the Event Explorer and SOC query interface.' },
  { title: 'MITRE ATT&CK Framework', url: 'https://attack.mitre.org/', desc: 'Adversary tactic and technique taxonomy used by the ULPF Correlation Engine for tagging detected behaviors.' },
  { title: 'Hyperledger Fabric', url: 'https://hyperledger-fabric.readthedocs.io/', desc: 'Optional future feature: batch Merkle root anchoring on a permissioned blockchain for tamper-proof audit trails.' },
  { title: 'MinIO Object Storage', url: 'https://min.io/', desc: 'S3-compatible object storage used for the Raw Event Vault — lossless, compressed, lifecycle-managed.' },
]

export default function ArchitecturePage() {
  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <Layers size={20} color="var(--color-text-primary)" />
          <h1>Architecture & Documentation</h1>
        </div>
        <p>
          ULPF is a modular, vendor-neutral log pre-processing pipeline designed for India's defence, intelligence, and critical infrastructure operators. The architecture separates concerns across six logical layers, enabling independent scaling, replacement, and auditability of each component.
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
          {['Forensics-Grade','Privacy-Aware','Vendor-Neutral','Replayable','Explainable','Audit-Ready','Scalable by Design'].map(t => {
            const cls = t === 'Forensics-Grade' ? 'tag-forensics' : t === 'Privacy-Aware' ? 'tag-privacy' : t === 'Audit-Ready' ? 'tag-audit' : t === 'Replayable' ? 'tag-replay' : t === 'Explainable' ? 'tag-explain' : t === 'Scalable by Design' ? 'tag-scale' : 'tag-neutral'
            return <span key={t} className={`tag-label ${cls}`}>{t}</span>
          })}
        </div>
      </div>

      {/* Main Architecture Diagram */}
      <div className="glass-card" style={{ padding: 24, marginBottom: 24, overflow: 'hidden' }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-text-muted)', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Server size={14} />
          System Architecture — Left to Right Pipeline
        </div>
        <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 20 }}>
          Each layer is independently deployable. The ULPF Core (blue) is the primary innovation zone.
        </div>
        <div className="arch-wrapper">
          {LAYERS.map((layer, i) => (
            <div key={layer.title} style={{ display: 'flex', alignItems: 'flex-start' }}>
              <ArchLayer {...layer} />
              {i < LAYERS.length - 1 && (
                <div className="arch-arrow">
                  <ArrowRight size={20} color="var(--color-border)" />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Supporting layers */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        {/* Observability */}
        <div className="glass-card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Eye size={16} color="var(--color-text-primary)" />
            <span style={{ fontWeight: 700, color: 'var(--color-text-primary)', fontSize: 14 }}>Observability Layer</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {['Prometheus — metrics scraping', 'Grafana — dashboards & alerts', 'OpenTelemetry — distributed tracing', 'Structured JSON logs (ECS format)', 'Self-monitoring / loss detection'].map(item => (
              <div key={item} style={{ fontSize: 12, color: 'var(--color-text-muted)', display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                <span style={{ color: 'var(--color-text-primary)', marginTop: 2 }}>•</span>{item}
              </div>
            ))}
          </div>
        </div>

        {/* Security */}
        <div className="glass-card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Shield size={16} color="#10b981" />
            <span style={{ fontWeight: 700, color: 'var(--color-text-primary)', fontSize: 14 }}>Security Layer</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {['RBAC — role-based access control', 'mTLS between services', 'Encryption at rest (AES-256)', 'Secrets management (Vault)', 'Immutable audit logs', 'Privacy policy enforcement'].map(item => (
              <div key={item} style={{ fontSize: 12, color: 'var(--color-text-muted)', display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                <span style={{ color: '#10b981', marginTop: 2 }}>•</span>{item}
              </div>
            ))}
          </div>
        </div>

        {/* Deployment */}
        <div className="glass-card" style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Package size={16} color="var(--color-text-primary)" />
            <span style={{ fontWeight: 700, color: 'var(--color-text-primary)', fontSize: 14 }}>Deployment Layer</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {['Docker Compose (prototype / demo)', 'Kubernetes (production scale-out)', 'Helm charts for each service', 'Horizontal pod autoscaling', 'Configurable retention policies'].map(item => (
              <div key={item} style={{ fontSize: 12, color: 'var(--color-text-muted)', display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                <span style={{ color: 'var(--color-text-primary)', marginTop: 2 }}>•</span>{item}
              </div>
            ))}
          </div>
          <div style={{ marginTop: 14, padding: '8px 12px', background: 'transparent', borderRadius: 6, border: '1px solid transparent', fontSize: 11, color: 'var(--color-text-primary)' }}>
            Optional Future: Hyperledger Fabric anchoring of batch Merkle roots for immutable public auditability.
          </div>
        </div>
      </div>

      {/* Technology Table */}
      <div className="glass-card" style={{ padding: 24, marginBottom: 24 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Cpu size={14} />
          Technology Stack Reference
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Component</th>
              <th>Technology Choice</th>
              <th>Alternative</th>
              <th>Role</th>
            </tr>
          </thead>
          <tbody>
            {[
              ['Streaming Ingestion', 'Apache Kafka', 'Redpanda', 'Log transport & fan-out'],
              ['Parser Engine', 'Python (FastAPI)', 'Go', 'Field extraction & format detection'],
              ['Normalized Store', 'OpenSearch', 'ClickHouse', 'SOC search & analytics'],
              ['Raw Vault', 'MinIO (S3-compatible)', 'AWS S3 / GCS', 'Lossless raw log preservation'],
              ['Metadata / Policy DB', 'PostgreSQL', 'CockroachDB', 'Parsers, policies, audit log'],
              ['Correlation State', 'Redis', 'Valkey', 'In-flight window aggregation'],
              ['Web Console', 'React + Vite', 'Next.js', 'SOC analyst interface'],
              ['Integrity Hashing', 'SHA-256 + Merkle tree', 'SHA-3', 'Tamper-evidence'],
              ['Observability', 'Prometheus + Grafana', 'Datadog', 'Platform health monitoring'],
              ['Container Orchestration', 'Docker Compose / K8s', 'Nomad', 'Service lifecycle management'],
            ].map(([comp, tech, alt, role]) => (
              <tr key={comp}>
                <td style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>{comp}</td>
                <td style={{ color: 'var(--color-text-primary)' }}>{tech}</td>
                <td style={{ color: 'var(--color-text-muted)' }}>{alt}</td>
                <td>{role}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-divider" />

      {/* Data Flow */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 6 }}>Data Flow — Raw Log to Analyst</div>
        <div style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 20 }}>Every log follows this deterministic, auditable path from intake to investigation.</div>
        <div style={{ display: 'flex', overflowX: 'auto', gap: 0, paddingBottom: 8 }}>
          {[
            { n: '1', label: 'Collect', desc: 'syslog-ng / agent receives raw log', color: 'var(--color-text-primary)' },
            { n: '2', label: 'Store Raw', desc: 'MinIO vault + SHA-256 computed', color: 'var(--color-text-primary)' },
            { n: '3', label: 'Publish', desc: 'Kafka raw_logs topic', color: '#f59e0b' },
            { n: '4', label: 'Parse', desc: 'Format detect → field extraction', color: 'var(--color-text-primary)' },
            { n: '5', label: 'Normalize', desc: 'ECS-like schema mapping', color: 'var(--color-text-primary)' },
            { n: '6', label: 'Redact', desc: 'Privacy policy enforcement', color: 'var(--color-text-primary)' },
            { n: '7', label: 'Hash & Batch', desc: 'Merkle root computed', color: '#10b981' },
            { n: '8', label: 'Index', desc: 'OpenSearch / ClickHouse', color: '#10b981' },
            { n: '9', label: 'Correlate', desc: 'Rule engine + risk scoring', color: '#ef4444' },
            { n: '10', label: 'Serve', desc: 'Console / SIEM / API', color: 'var(--color-text-primary)' },
          ].map((step, i, arr) => (
            <div key={step.n} style={{ display: 'flex', alignItems: 'center' }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, minWidth: 90 }}>
                <div style={{ width: 36, height: 36, borderRadius: '50%', background: `${step.color}20`, border: `2px solid ${step.color}60`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700, color: step.color }}>
                  {step.n}
                </div>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-text-primary)', textAlign: 'center' }}>{step.label}</div>
                <div style={{ fontSize: 10, color: 'var(--color-text-muted)', textAlign: 'center', lineHeight: 1.3 }}>{step.desc}</div>
              </div>
              {i < arr.length - 1 && (
                <div style={{ padding: '0 4px', marginBottom: 28 }}>
                  <ArrowRight size={14} color="var(--color-border)" />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="section-divider" />

      {/* Resources */}
      <div>
        <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 4 }}>Reference Resources</div>
        <div style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 20 }}>Educational and research references used in the design of ULPF. External links are provided for reference only.</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 14 }}>
          {RESOURCES.map(r => (
            <a key={r.title} href={r.url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'none' }}>
              <div className="glass-card" style={{ padding: 16, cursor: 'pointer', transition: 'border-color 0.2s', borderColor: 'var(--color-border)' }}
                onMouseEnter={e => (e.currentTarget.style.borderColor = 'transparent')}
                onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-primary)' }}>{r.title}</span>
                  <ExternalLink size={12} color="var(--color-text-muted)" style={{ flexShrink: 0, marginTop: 2 }} />
                </div>
                <p style={{ fontSize: 12, color: 'var(--color-text-muted)', lineHeight: 1.5 }}>{r.desc}</p>
              </div>
            </a>
          ))}
        </div>
      </div>
    </div>
  )
}
