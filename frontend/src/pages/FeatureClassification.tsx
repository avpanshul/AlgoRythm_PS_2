import { useState } from 'react'
import { CheckSquare, PlusSquare, Star, ChevronDown, ChevronRight, Layers } from 'lucide-react'

const MINISTRY = [
  { name: 'Multi-source ingestion', desc: 'Accept logs from firewalls, IDS/IPS, servers, cloud platforms, applications, and proxies simultaneously.' },
  { name: 'Multi-format support', desc: 'Handle CEF, JSON, Syslog, W3C, LEEF, CSV, and custom delimited formats without reconfiguration.' },
  { name: 'Lossless raw preservation', desc: 'Store every raw log byte-for-byte in the Raw Vault before any transformation is applied.' },
  { name: 'Parsing and field extraction', desc: 'Deterministic and AI-assisted extraction of structured fields from unstructured log lines.' },
  { name: 'Common-schema normalization', desc: 'Map extracted fields to a single ECS-like Common Security Schema across all source types.' },
  { name: 'End-to-end traceability', desc: 'Every normalized event carries a lineage reference to its raw source, parser, version, and policies.' },
  { name: 'Extensible parser architecture', desc: 'Add new source formats via YAML/JSON parser definitions without modifying the core engine.' },
  { name: 'Horizontal scalability', desc: 'Kafka-based streaming and stateless parser workers scale independently per ingestion volume.' },
  { name: 'Analytics and SIEM integration', desc: 'REST/gRPC APIs and OpenSearch compatibility enable direct integration with downstream SIEM tools.' },
]

const PRACTICAL = [
  { name: 'Parser registry', desc: 'Centralized catalog of all parsers with versioning, author, approval status, and usage statistics.' },
  { name: 'In-browser parser testing', desc: 'Upload sample logs, run the parser, and inspect field-level extraction results before publishing.' },
  { name: 'Auto format detection', desc: 'Statistical analysis of sample logs determines format type (CEF/JSON/Syslog) with confidence score.' },
  { name: 'Mapping suggestions', desc: 'Field name similarity and value pattern matching generates ECS field mapping recommendations.' },
  { name: 'Schema validation', desc: 'Validate normalized events against the schema version — check required fields, types, and ranges.' },
  { name: 'Dead-letter queue', desc: 'Failed events are routed to the DLQ with error reason, raw log reference, and manual review queue.' },
  { name: 'Parser versioning', desc: 'Semantic versioning (1.0 → 1.1 → 2.0) with approval workflow and rollback capability.' },
  { name: 'Replay service', desc: 'Re-process historical raw logs through an updated parser without any data loss or re-ingestion.' },
  { name: 'Role-based access control', desc: 'Security Admin, SOC Analyst, Parser Developer, and Forensics Officer roles with enforced permission boundaries.' },
  { name: 'Immutable audit logs', desc: 'Every user action, parser change, access request, and policy update is recorded with timestamp and actor identity.' },
  { name: 'Platform health dashboard', desc: 'Per-source ingestion rate, DLQ count, normalization success rate, and service latency metrics.' },
  { name: 'Data quality scoring', desc: 'Per-event and per-source quality scores based on required field presence, type validity, and enrichment coverage.' },
]

const NOVELTY = [
  {
    name: 'SHA-256 event integrity + batch Merkle hash chain',
    tagClass: 'tag-forensics',
    tag: 'Forensics-Grade',
    what: 'Every normalized event is SHA-256 hashed at write time. At the end of each time window, all event hashes form a Merkle tree. The batch root hash is stored and verifiable on demand.',
    why: 'Proves that no event was modified, deleted, or inserted after normalization. Creates a forensically sound chain of custody for regulatory and legal proceedings.',
    feasibility: 'High — standard cryptographic operations; no specialized hardware required.',
    tech: 'Python hashlib / Go crypto/sha256, PostgreSQL for batch roots, optional Hyperledger Fabric anchoring.',
    demo: 'Click "Verify Integrity" on any event. Show VERIFIED result with hash comparison and batch Merkle root validation report.',
  },
  {
    name: 'Raw vault + privacy-redacted analytics twin',
    tagClass: 'tag-privacy',
    tag: 'Privacy-Aware',
    what: 'Two views of every event: the original raw log (restricted access, Raw Vault) and a privacy-compliant analyst view with sensitive fields pseudonymized or redacted per active policy.',
    why: 'Allows analytics and SOC operations on safe data while preserving original evidence for authorized forensic access. Reduces unnecessary exposure of PII and network topology.',
    feasibility: 'High — deterministic field-level tokenization with policy engine is well-understood.',
    tech: 'PostgreSQL for policies, Python privacy engine, MinIO for raw vault, Redis for token lookup cache.',
    demo: 'Toggle between raw and analyst view in Event Detail. Show masked source.ip and the deterministic token in the analyst view.',
  },
  {
    name: 'Version-aware replayable processing',
    tagClass: 'tag-replay',
    tag: 'Replayable',
    what: 'Raw logs in the vault can be re-processed through any registered parser version at any time. Historical events can be improved retroactively when parsers are updated.',
    why: 'Eliminates the need to re-ingest data after parser improvements. Historical data quality improves continuously without operational disruption.',
    feasibility: 'High — raw vault + Kafka replay mechanism is a standard log pipeline pattern.',
    tech: 'MinIO raw vault, Kafka replay topic, parser versioning in PostgreSQL, async job queue.',
    demo: 'Show parser v1.0 → v1.1 update in Parser Registry. Trigger a replay job. Show improvement in field coverage for historical events.',
  },
  {
    name: 'Human-approved AI-assisted parser generation',
    tagClass: 'tag-explain',
    tag: 'Explainable',
    what: 'An LLM or rule-based system suggests parser YAML definitions and field mappings from sample logs. A human expert reviews, edits, and approves before activation.',
    why: 'Dramatically reduces the time to onboard new log sources while keeping a human in the loop for accuracy and security control.',
    feasibility: 'Medium — LLM suggestion quality varies; needs test coverage to validate.',
    tech: 'OpenAI API / local LLM, structured output prompting, human approval workflow in web console.',
    demo: 'Upload a new log format. Show the auto-generated YAML parser and field mapping suggestions. Edit one field. Approve and test.',
  },
  {
    name: 'Explainable correlation and anomaly detection',
    tagClass: 'tag-explain',
    tag: 'Explainable',
    what: 'Each correlated incident includes a plain-language explanation: which rule fired, which events matched, which MITRE ATT&CK tactics were involved, and what the confidence level is.',
    why: 'SOC analysts can understand and act on alerts without treating the system as a black box. Explainability is critical for trust in high-stakes government security operations.',
    feasibility: 'High — rule-based explanation is deterministic; ML-based anomaly explanation is harder but tractable.',
    tech: 'Rule YAML with explanation templates, MITRE ATT&CK taxonomy, Python correlation engine.',
    demo: 'Open Incident INC-092-A. Show the rule explanation, matched events, MITRE tags, and risk score breakdown.',
  },
  {
    name: 'Self-monitoring and log loss detection',
    tagClass: 'tag-scale',
    tag: 'Scalable by Design',
    what: 'ULPF tracks expected vs actual event rate per source. Sudden drops trigger a "log gap" alert, helping operators detect when a source has stopped sending logs — which can indicate network failure or an active attack suppressing evidence.',
    why: 'Silent log loss is as dangerous as detected attacks. This feature provides operational assurance that the telemetry pipeline is intact.',
    feasibility: 'Medium — requires baseline learning period; statistical anomaly detection on per-source rates.',
    tech: 'Prometheus metrics, Grafana alerting, Redis rate window counters, threshold-based alerting.',
    demo: 'Platform Health dashboard shows per-source event rate graphs. Point to a simulated drop and the auto-generated gap alert.',
  },
  {
    name: 'Privacy-preserving cross-organization correlation tokens',
    tagClass: 'tag-privacy',
    tag: 'Privacy-Aware',
    what: 'Deterministic pseudonymization tokens derived from sensitive fields (e.g., source IP) allow correlation of events across organizations without sharing the original sensitive value.',
    why: 'Two organizations can correlate activity from the same threat actor using shared tokens, without revealing internal IP addresses or user identities to each other.',
    feasibility: 'Medium — requires agreed-upon keying scheme and governance framework between organizations.',
    tech: 'HMAC-SHA256 pseudonymization, shared key management, token exchange protocol.',
    demo: 'Show source.ip.token in the analyst view. Explain how two orgs using the same HMAC key can correlate events without sharing raw IPs.',
  },
  {
    name: 'Optional distributed ledger batch-root anchoring',
    tagClass: 'tag-forensics',
    tag: 'Forensics-Grade',
    what: 'Batch Merkle root hashes can optionally be anchored to a permissioned Hyperledger Fabric blockchain, providing a tamper-evident public record of log integrity at the batch level.',
    why: 'Provides an externally verifiable integrity proof that cannot be repudiated even if ULPF\'s own database is compromised.',
    feasibility: 'Low-Medium — Hyperledger Fabric setup is non-trivial; suitable as a future production enhancement.',
    tech: 'Hyperledger Fabric, Fabric SDK for Python/Go, on-chain batch root storage.',
    demo: 'Show the batch root hash in the Integrity Report. Explain how it would be written to a blockchain transaction for external verifiability.',
  },
]

export default function FeatureClassification() {
  const [expandedNovelty, setExpandedNovelty] = useState<number | null>(0)

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <Layers size={20} color="var(--color-text-primary)" />
          <h1>Feature Classification</h1>
        </div>
        <p>
          ULPF features are classified into three tiers: ministry-required baseline capabilities, practical operational enhancements, and novel high-impact differentiators. This taxonomy helps judges and stakeholders understand what the framework delivers beyond the minimum specification.
        </p>
      </div>

      {/* Tier A & B side by side */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 28 }}>
        {/* Tier A */}
        <div>
          <div className="feature-tier">
            <div className="feature-tier-header" style={{ background: 'transparent', color: 'var(--color-text-primary)' }}>
              <CheckSquare size={16} />
              Tier A — Ministry-Required Features
              <span style={{ marginLeft: 'auto', fontSize: 11, background: 'transparent', padding: '2px 8px', borderRadius: 10 }}>{MINISTRY.length}</span>
            </div>
            {MINISTRY.map(f => (
              <div key={f.name} className="feature-item">
                <span style={{ color: 'var(--color-text-primary)', marginTop: 1, flexShrink: 0 }}>✓</span>
                <div>
                  <div style={{ color: 'var(--color-text-primary)', fontWeight: 600, marginBottom: 2 }}>{f.name}</div>
                  <div style={{ color: 'var(--color-text-muted)', fontSize: 11, lineHeight: 1.4 }}>{f.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Tier B */}
        <div>
          <div className="feature-tier">
            <div className="feature-tier-header" style={{ background: 'transparent', color: 'var(--color-success)' }}>
              <PlusSquare size={16} />
              Tier B — Added Practical Features
              <span style={{ marginLeft: 'auto', fontSize: 11, background: 'transparent', padding: '2px 8px', borderRadius: 10 }}>{PRACTICAL.length}</span>
            </div>
            {PRACTICAL.map(f => (
              <div key={f.name} className="feature-item">
                <span style={{ color: '#10b981', marginTop: 1, flexShrink: 0 }}>+</span>
                <div>
                  <div style={{ color: 'var(--color-text-primary)', fontWeight: 600, marginBottom: 2 }}>{f.name}</div>
                  <div style={{ color: 'var(--color-text-muted)', fontSize: 11, lineHeight: 1.4 }}>{f.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tier C */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <Star size={18} color="var(--color-text-primary)" />
          <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--color-text-primary)' }}>
            Tier C — Novelty / High-Impact Features
          </div>
          <span style={{ background: 'transparent', color: 'var(--color-text-primary)', fontSize: 11, padding: '2px 10px', borderRadius: 10, border: '1px solid transparent' }}>
            {NOVELTY.length} features
          </span>
        </div>
        <div style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 20 }}>
          These features go beyond the problem statement requirements and represent the most differentiated aspects of the ULPF design. Click any feature to see its full specification.
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {NOVELTY.map((f, i) => (
            <div key={f.name} className="novelty-card" style={{ borderColor: expandedNovelty === i ? 'transparent' : 'transparent' }}>
              <button
                onClick={() => setExpandedNovelty(expandedNovelty === i ? null : i)}
                style={{ width: '100%', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', padding: 0, display: 'flex', alignItems: 'center', gap: 12 }}
              >
                <div style={{ width: 28, height: 28, borderRadius: 6, background: 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 800, color: 'var(--color-text-primary)', flexShrink: 0 }}>
                  C{i + 1}
                </div>
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-text-primary)' }}>{f.name}</span>
                  <span className={`tag-label ${f.tagClass}`}>{f.tag}</span>
                </div>
                {expandedNovelty === i ? <ChevronDown size={16} color="var(--color-text-muted)" /> : <ChevronRight size={16} color="var(--color-text-muted)" />}
              </button>

              {expandedNovelty === i && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ fontSize: 13, color: 'var(--color-text-muted)', lineHeight: 1.7, marginBottom: 14, borderLeft: '3px solid transparent', paddingLeft: 14 }}>
                    {f.what}
                  </div>
                  <div className="novelty-row">
                    <div className="novelty-cell">
                      <div className="novelty-cell-label">Why It Matters</div>
                      <div className="novelty-cell-val">{f.why}</div>
                    </div>
                    <div className="novelty-cell">
                      <div className="novelty-cell-label">Feasibility</div>
                      <div className="novelty-cell-val">{f.feasibility}</div>
                    </div>
                    <div className="novelty-cell">
                      <div className="novelty-cell-label">Technology</div>
                      <div className="novelty-cell-val">{f.tech}</div>
                    </div>
                    <div className="novelty-cell">
                      <div className="novelty-cell-label">How to Demo</div>
                      <div className="novelty-cell-val">{f.demo}</div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="section-divider" />

      {/* Summary table */}
      <div>
        <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 16 }}>Feature Count Summary</div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Tier</th>
              <th>Category</th>
              <th>Feature Count</th>
              <th>Status in ULPF</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={{ color: 'var(--color-text-primary)', fontWeight: 700 }}>A</td>
              <td>Ministry-Required</td>
              <td style={{ color: 'var(--color-text-primary)', fontWeight: 700 }}>{MINISTRY.length}</td>
              <td><span className="tag-label tag-explain">All Implemented</span></td>
            </tr>
            <tr>
              <td style={{ color: 'var(--color-success)', fontWeight: 700 }}>B</td>
              <td>Added Practical</td>
              <td style={{ color: 'var(--color-success)', fontWeight: 700 }}>{PRACTICAL.length}</td>
              <td><span className="tag-label tag-explain">All Implemented</span></td>
            </tr>
            <tr>
              <td style={{ color: 'var(--color-text-primary)', fontWeight: 700 }}>C</td>
              <td>Novelty / High-Impact</td>
              <td style={{ color: 'var(--color-text-primary)', fontWeight: 700 }}>{NOVELTY.length}</td>
              <td><span className="tag-label tag-forensics">6 Implemented, 2 Prototype</span></td>
            </tr>
            <tr>
              <td style={{ color: 'var(--color-text-primary)', fontWeight: 800 }}>—</td>
              <td style={{ fontWeight: 700, color: 'var(--color-text-primary)' }}>Total</td>
              <td style={{ fontWeight: 800, color: 'var(--color-text-primary)' }}>{MINISTRY.length + PRACTICAL.length + NOVELTY.length}</td>
              <td></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
