import { useState } from 'react'
import { Shield, Search, PenTool, FileSearch } from 'lucide-react'

interface FlowStep {
  title: string
  detail: string
  system?: string
  tag?: string
  tagClass?: string
}

interface Flow {
  id: string
  title: string
  subtitle: string
  color: string
  icon: React.ElementType
  role: string
  steps: FlowStep[]
}

const FLOWS: Flow[] = [
  {
    id: 'admin',
    title: 'Security Admin — Onboarding a Log Source',
    subtitle: 'From raw connector setup to live production log feed in 10 steps.',
    color: 'var(--color-text-primary)',
    icon: Shield,
    role: 'Security Admin',
    steps: [
      { title: 'Add Log Source', detail: 'Navigate to Log Sources → Add Source. Provide a name, vendor, and choose format hint (CEF, JSON, Syslog, etc.).', system: 'ULPF Web Console' },
      { title: 'Upload Sample Logs', detail: 'Upload 3–5 representative raw log files or paste a sample. ULPF accepts CEF, JSON, CSV, Syslog, and custom formats.', system: 'Parser Studio' },
      { title: 'Auto-Detect Format', detail: 'ULPF Parser Engine analyses the sample and reports format confidence score, detected fields, and potential delimiter patterns.', system: 'Parser Engine', tag: 'Vendor-Neutral', tagClass: 'tag-neutral' },
      { title: 'Review Mapping Suggestions', detail: 'The system proposes ECS-like field mappings (e.g., src → source.ip, act → event.outcome). Admin reviews and edits each mapping in the visual YAML editor.', system: 'Parser Studio', tag: 'Explainable', tagClass: 'tag-explain' },
      { title: 'Select Privacy Policy', detail: 'Choose from existing privacy policies (e.g., MHA-Policy-01) or create a new one specifying which fields to redact, pseudonymize, or pass through.', system: 'Privacy Policies', tag: 'Privacy-Aware', tagClass: 'tag-privacy' },
      { title: 'Test Parser', detail: 'Run the draft parser against the uploaded sample. Inspect normalized output, missing fields, and quality score before committing.', system: 'Parser Studio' },
      { title: 'Validate Schema', detail: 'ULPF validates all required ECS-like fields are mapped and that data types conform to the schema version.', system: 'Schema Validator' },
      { title: 'Activate Source', detail: 'Publish parser to registry. Activate the source connector. ULPF begins accepting live logs on the designated syslog port or API endpoint.', system: 'Parser Registry', tag: 'Audit-Ready', tagClass: 'tag-audit' },
      { title: 'Send Live Logs', detail: 'Configure the source device (firewall, server, IDS) to forward logs to the ULPF collector endpoint. First live events appear in Event Explorer within seconds.', system: 'External Device' },
      { title: 'Monitor Source Health', detail: 'Platform Health dashboard shows per-source ingestion rate, last-seen timestamp, DLQ count, and normalization success rate.', system: 'Platform Health', tag: 'Scalable by Design', tagClass: 'tag-scale' },
    ],
  },
  {
    id: 'analyst',
    title: 'SOC Analyst — Incident Investigation',
    subtitle: 'From initial triage to chain-of-custody evidence export in 9 steps.',
    color: '#ef4444',
    icon: Search,
    role: 'SOC Analyst',
    steps: [
      { title: 'Open Event Explorer', detail: 'Navigate to Event Explorer. Use the search bar to query by IP, port, event type, or rule name. Full-text and structured search supported.', system: 'Event Explorer' },
      { title: 'Filter Suspicious Events', detail: 'Apply filters: time range, severity ≥ HIGH, source = PA-FW-MH-01. Sort by risk score descending to surface critical events first.', system: 'Event Explorer' },
      { title: 'Open Event Detail', detail: 'Click any event row to open the full Event Detail view — normalized fields, redacted analyst-safe values, and full lineage.', system: 'Event Detail', tag: 'Explainable', tagClass: 'tag-explain' },
      { title: 'Review Risk & Redaction', detail: 'Inspect the risk score breakdown, correlation rule explanation, and which fields were redacted under the active privacy policy.', system: 'Event Detail', tag: 'Privacy-Aware', tagClass: 'tag-privacy' },
      { title: 'View Incident Timeline', detail: 'Open the correlated incident. See the full event chain: brute-force → port scan → successful login, with timestamps and MITRE ATT&CK tags.', system: 'Incident Center', tag: 'Explainable', tagClass: 'tag-explain' },
      { title: 'Check Event Lineage', detail: 'Review the lineage trace: which raw source, which parser version, which privacy policy was applied, and when each transformation occurred.', system: 'Event Detail', tag: 'Audit-Ready', tagClass: 'tag-audit' },
      { title: 'Verify Integrity', detail: 'Click Verify Integrity. ULPF computes the event hash and validates it against the stored value and the batch Merkle root. Result: VERIFIED.', system: 'Integrity Service', tag: 'Forensics-Grade', tagClass: 'tag-forensics' },
      { title: 'Request Raw Evidence', detail: 'If authorized as Forensics Officer: request raw vault access. ULPF logs the access request and provides the original byte-for-byte log.', system: 'Raw Vault', tag: 'Forensics-Grade', tagClass: 'tag-forensics' },
      { title: 'Export Evidence Package', detail: 'Generate a signed evidence package including normalized event, raw reference, hash verification report, and audit log of all access events.', system: 'Evidence Export', tag: 'Forensics-Grade', tagClass: 'tag-forensics' },
    ],
  },
  {
    id: 'parser',
    title: 'Parser Developer — Build & Improve a Parser',
    subtitle: 'From raw log sample to published, approved, versioned parser in 9 steps.',
    color: 'var(--color-text-primary)',
    icon: PenTool,
    role: 'Parser Developer',
    steps: [
      { title: 'Upload New Logs', detail: 'Open Parser Studio. Upload sample logs from the new source (e.g., Cisco ASA syslog). Provide metadata: vendor, version, format family.', system: 'Parser Studio' },
      { title: 'Auto-Detect Format', detail: 'ULPF analyses delimiters, key-value pairs, timestamps, and field patterns. Reports: "Syslog-structured with KV pairs, confidence 0.91."', system: 'Parser Engine', tag: 'Vendor-Neutral', tagClass: 'tag-neutral' },
      { title: 'Review Mapping Suggestions', detail: 'ULPF suggests ECS field mappings based on field name similarity and value patterns. Developer accepts, rejects, or overrides each suggestion.', system: 'Parser Studio', tag: 'Explainable', tagClass: 'tag-explain' },
      { title: 'Edit YAML / JSON Parser Definition', detail: 'Fine-tune the parser definition: add regex patterns for custom fields, define timestamp formats, configure conditional extraction rules.', system: 'Parser Studio (YAML editor)' },
      { title: 'Test Parser', detail: 'Run the parser against the uploaded sample set. Inspect field-by-field extraction results, highlight missing or mismatched fields.', system: 'Parser Studio' },
      { title: 'Validate Schema', detail: 'Schema Validator checks: all required ECS fields present, types correct, no schema version conflicts. Validation score ≥ 90 required to publish.', system: 'Schema Validator' },
      { title: 'Publish Parser Version', detail: 'Submit parser v1.0 to the registry. Status moves to PENDING_APPROVAL. Semantic versioning enforced (1.0 → 1.1 → 2.0).', system: 'Parser Registry', tag: 'Audit-Ready', tagClass: 'tag-audit' },
      { title: 'Admin Approval', detail: 'Security Admin reviews the parser definition, test results, and schema validation report. Approves → status moves to ACTIVE.', system: 'Parser Registry' },
      { title: 'Replay Historical Raw Logs', detail: 'Trigger a Replay Job: re-process the last N days of raw logs through the new parser. Improved extraction applied to historical data without any data loss.', system: 'Replay Center', tag: 'Replayable', tagClass: 'tag-replay' },
    ],
  },
  {
    id: 'auditor',
    title: 'Auditor / Forensics Officer — Evidence Verification',
    subtitle: 'From event selection to signed, chain-of-custody evidence package in 7 steps.',
    color: '#10b981',
    icon: FileSearch,
    role: 'Forensics Officer',
    steps: [
      { title: 'Open Suspicious Event', detail: 'Navigate to Event Explorer or Incident Center. Identify the event(s) requiring forensic examination and open the Event Detail view.', system: 'Event Explorer / Incident Center' },
      { title: 'Access Raw Log Reference', detail: 'In Event Detail, click "Request Raw Access." Role check: Forensics Officer required. Request is logged to the audit trail before access is granted.', system: 'Raw Vault', tag: 'Forensics-Grade', tagClass: 'tag-forensics' },
      { title: 'Verify SHA-256 Event Hash', detail: 'ULPF computes the current SHA-256 hash of the stored normalized event and compares it to the hash recorded at normalization time.', system: 'Integrity Service', tag: 'Forensics-Grade', tagClass: 'tag-forensics' },
      { title: 'Validate Batch Merkle Root', detail: 'Verify the event\'s leaf hash appears in the stored Merkle tree for its batch. The batch root hash proves the entire batch is unmodified.', system: 'Integrity Service', tag: 'Forensics-Grade', tagClass: 'tag-forensics' },
      { title: 'Review Verification Result', detail: 'Verification report shows: event hash MATCHED, batch root MATCHED, chain of custody timestamps, and lineage of all transformations applied.', system: 'Integrity Report', tag: 'Audit-Ready', tagClass: 'tag-audit' },
      { title: 'Audit Entry Auto-Created', detail: 'ULPF automatically creates an immutable audit log entry: who requested, when, which event, which raw log was accessed, and verification outcome.', system: 'Audit Logs', tag: 'Audit-Ready', tagClass: 'tag-audit' },
      { title: 'Export Chain-of-Custody Package', detail: 'Generate a signed evidence package: normalized event, original raw log, SHA-256 verification report, Merkle proof, full audit trail of all access events. Suitable for legal and regulatory use.', system: 'Evidence Export', tag: 'Forensics-Grade', tagClass: 'tag-forensics' },
    ],
  },
]

export default function UserFlows() {
  const [activeFlow, setActiveFlow] = useState('admin')
  const flow = FLOWS.find(f => f.id === activeFlow)!
  const Icon = flow.icon

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <FileSearch size={20} color="var(--color-text-primary)" />
          <h1>User Flows & Role Guides</h1>
        </div>
        <p>
          Step-by-step operational workflows for each ULPF user role. These flows illustrate how the system supports real-world security operations from source onboarding to forensic evidence export.
        </p>
      </div>

      {/* Role tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 28, flexWrap: 'wrap' }}>
        {FLOWS.map(f => {
          const FIcon = f.icon
          const isActive = f.id === activeFlow
          return (
            <button
              key={f.id}
              onClick={() => setActiveFlow(f.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '10px 18px', borderRadius: 8,
                border: `1px solid ${isActive ? f.color : 'var(--color-border)'}`,
                background: isActive ? `${f.color}18` : 'var(--color-bg-card)',
                color: isActive ? f.color : 'var(--color-text-muted)', cursor: 'pointer', fontSize: 13, fontWeight: 600,
                transition: 'all 0.2s'
              }}
            >
              <FIcon size={15} />
              {f.role}
            </button>
          )
        })}
      </div>

      {/* Flow header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <div style={{ width: 36, height: 36, borderRadius: 8, background: `${flow.color}20`, border: `1px solid ${flow.color}40`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Icon size={18} color={flow.color} />
          </div>
          <div>
            <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--color-text-primary)' }}>{flow.title}</div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>{flow.subtitle}</div>
          </div>
        </div>
      </div>

      {/* Steps */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 0 }}>
        {flow.steps.map((step, i) => (
          <div key={i} className="flow-step-card" style={{ position: 'relative', display: 'flex', gap: 14, padding: '0 16px 0 0', marginBottom: 4 }}>
            {/* Connector line */}
            {i < flow.steps.length - 1 && i % 2 === 0 && (
              <div style={{ position: 'absolute', left: 14, top: 30, width: 2, height: 'calc(100% + 4px)', background: `${flow.color}30`, zIndex: 0 }} />
            )}
            {i < flow.steps.length - 1 && i % 2 === 1 && (
              <div style={{ position: 'absolute', left: 14, top: 30, width: 2, height: 'calc(100% + 4px)', background: `${flow.color}30`, zIndex: 0 }} />
            )}
            {/* Number */}
            <div className="flow-step-num" style={{ background: `${flow.color}20`, color: flow.color, border: `2px solid ${flow.color}50`, zIndex: 1 }}>
              {i + 1}
            </div>
            {/* Content */}
            <div className="flow-step-body" style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6, gap: 8 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-text-primary)' }}>{step.title}</div>
                {step.tag && <span className={`tag-label ${step.tagClass}`} style={{ flexShrink: 0 }}>{step.tag}</span>}
              </div>
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)', lineHeight: 1.6, marginBottom: 6 }}>{step.detail}</div>
              {step.system && (
                <div style={{ fontSize: 10, color: 'var(--color-border)', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                  System: {step.system}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Outcome summary */}
      <div style={{ marginTop: 24, padding: '16px 20px', background: `${flow.color}0a`, border: `1px solid ${flow.color}30`, borderRadius: 10 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: flow.color, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          Outcome
        </div>
        <div style={{ fontSize: 13, color: 'var(--color-text-muted)', lineHeight: 1.6 }}>
          {flow.id === 'admin' && 'A new log source is live, normalized, and feeding the SOC with structured, privacy-compliant, integrity-verified security telemetry.'}
          {flow.id === 'analyst' && 'The SOC analyst has a complete, explainable, privacy-respecting picture of the incident with a forensically sound evidence package ready for escalation.'}
          {flow.id === 'parser' && 'A new parser is versioned, approved, and active. Historical data has been retroactively improved using the Replay Service without any data loss.'}
          {flow.id === 'auditor' && 'A signed, chain-of-custody evidence package is ready for legal, regulatory, or audit use — with full integrity verification and immutable access records.'}
        </div>
      </div>
    </div>
  )
}
