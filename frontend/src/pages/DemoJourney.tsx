import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  UploadCloud, Cpu, ShieldOff, ShieldCheck, AlertTriangle,
  Search, RotateCcw, ChevronLeft, ChevronRight, X, CheckCircle2
} from 'lucide-react'

const STEPS = [
  {
    id: 1,
    iconName: 'UploadCloud',
    color: 'var(--color-text-primary)',
    title: 'Step 1 — Ingest',
    subtitle: 'A new firewall log arrives via CEF connector',
    narrative: `A Palo Alto firewall running at a ministry perimeter submits a raw CEF log via the ULPF syslog-ng collector. ULPF acknowledges receipt, stores the immutable raw copy in the Raw Vault, and publishes it to the raw_logs Kafka topic for downstream processing.\n\nNo data is discarded. The original log is preserved byte-for-byte with a SHA-256 hash computed at intake.`,
    tags: ['Vendor-Neutral', 'Forensics-Grade', 'Lossless'],
    artifact: `# Raw CEF Log — Received at Collector

CEF:0|Palo Alto Networks|PAN-OS|10.2.3|threat/vulnerability|
HIGH|rt=Sep 23 2026 14:22:10 IST
src=192.168.12.44 dst=10.0.0.1 spt=52341 dpt=22
proto=TCP act=reset-both cs1Label=Rule cs1=Block-SSH-Brute
msg="SSH brute-force detected - 47 attempts in 60s"
deviceExternalId=PA-FW-MH-01 app=ssh

# ULPF Intake Record
raw_id        : evt-9f3c2a-20260923-1422
source_id     : src-pa-fw-001
received_at   : 2026-09-23T14:22:10.341Z
sha256        : a3f84c91d0b2e57f3a6c81...d91c2  COMPUTED
raw_vault_ref : s3://ulpf-raw/2026/09/23/evt-9f3c2a.gz
topic         : raw_logs
status        : PUBLISHED`,
  },
  {
    id: 2,
    iconName: 'Cpu',
    color: 'var(--color-text-primary)',
    title: 'Step 2 — Parse & Normalize',
    subtitle: 'Parser engine extracts fields and maps to common ECS-like schema',
    narrative: `The ULPF Parser Engine auto-detects the CEF format, selects the registered Palo Alto Networks parser (v1.1), and extracts 22 fields. The ECS-like Schema Normalizer maps each extracted field to the ULPF Common Security Schema.\n\nThis makes the event comparable with logs from Cisco ASA, Suricata, Windows Event Viewer, or any other registered source. Normalization quality score: 94/100.`,
    tags: ['Vendor-Neutral', 'Extensible', 'Scalable by Design'],
    artifact: `# Parser: pan-panos-cef-v1.1
# Format auto-detected: CEF (confidence 0.98)
# Extraction: 22/22 fields

EXTRACTED FIELDS
src_ip      : 192.168.12.44
dst_ip      : 10.0.0.1
src_port    : 52341
dst_port    : 22
protocol    : TCP
action      : reset-both
severity    : HIGH
rule_name   : Block-SSH-Brute
app         : ssh
attempt_ct  : 47
device_id   : PA-FW-MH-01

ECS-LIKE NORMALIZED EVENT
@timestamp         : 2026-09-23T14:22:10Z
event.category     : network
event.type         : denied
event.outcome      : failure
source.ip          : 192.168.12.44
destination.ip     : 10.0.0.1
destination.port   : 22
network.protocol   : tcp
network.application: ssh
threat.indicator   : brute-force
device.vendor      : Palo Alto Networks
ulpf.schema_ver    : 1.0
ulpf.quality_score : 94`,
  },
  {
    id: 3,
    iconName: 'ShieldOff',
    color: '#f59e0b',
    title: 'Step 3 — Protect Privacy',
    subtitle: 'Sensitive fields are redacted before analytics exposure',
    narrative: `The active Privacy Policy (MHA-Policy-01) identifies source.ip as a sensitive field. ULPF applies pseudonymization — replacing it with a deterministic token that preserves analytical utility while protecting network topology.\n\nOnly authorized forensics officers with Raw Vault Access permission can retrieve the original field. Every access is logged in the audit trail.`,
    tags: ['Privacy-Aware', 'Audit-Ready', 'Forensics-Grade'],
    artifact: `# Privacy Policy: MHA-Policy-01
# Redaction Engine v1.0

RAW EVENT (Raw Vault only — restricted)
source.ip          : 192.168.12.44   SENSITIVE
destination.ip     : 10.0.0.1
network.application: ssh
attempt_count      : 47

ANALYST VIEW (Safe for SOC / SIEM)
source.ip          : ████████████████  REDACTED
source.ip.token    : host-token-7f3a   pseudonym
destination.ip     : 10.0.0.1
network.application: ssh
attempt_count      : 47

REDACTION LOG ENTRY
event_id    : evt-9f3c2a-20260923-1422
policy      : MHA-Policy-01
fields      : [source.ip]
method      : PSEUDONYMIZE
actor       : ulpf-privacy-engine
logged_at   : 2026-09-23T14:22:11.012Z`,
  },
  {
    id: 4,
    iconName: 'ShieldCheck',
    color: '#10b981',
    title: 'Step 4 — Prove Integrity',
    subtitle: 'SHA-256 hash chain and Merkle batch root verified',
    narrative: `Every normalized event carries a SHA-256 event hash. At the end of each 60-second batch window, all event hashes are combined into a Merkle tree and the batch root hash is persisted.\n\nAny post-hoc modification — even a single character — breaks verification. ULPF-produced events can serve as forensically sound evidence with a clear chain of custody from intake to investigation.`,
    tags: ['Forensics-Grade', 'Audit-Ready'],
    artifact: `# Integrity Verification Report

EVENT HASH VERIFICATION
event_id    : evt-9f3c2a-20260923-1422
algorithm   : SHA-256
event_hash  : a3f84c91d0b2e57f3a6c81...d91c2
stored_hash : a3f84c91d0b2e57f3a6c81...d91c2
match       : VERIFIED — No tampering detected

BATCH ROOT VERIFICATION
batch_id    : batch-20260923-1422
events      : 312
merkle_root : 7b3e1c...fa902d
stored_root : 7b3e1c...fa902d
verified_at : 2026-09-23T14:23:00Z
match       : VERIFIED

CHAIN OF CUSTODY
intake   → collector   : raw_hash VERIFIED
raw_hash → normalized  : transform_hash VERIFIED
batch_12 → batch_13    : prev_root_ref VERIFIED

INTEGRITY STATUS:  FORENSICALLY SOUND`,
  },
  {
    id: 5,
    iconName: 'AlertTriangle',
    color: '#ef4444',
    title: 'Step 5 — Detect Incident',
    subtitle: 'Correlated alert: SSH brute-force → port scan → successful access',
    narrative: `The ULPF Correlation Rule Engine matches three events from the same source IP token within a 5-minute window: SSH brute-force attempts, a follow-up port scan of internal services, and finally a successful authentication from a new geo-region.\n\nNo single event is suspicious in isolation. ULPF correlates them into Incident INC-092-A and scores it CRITICAL (risk score 95/100).`,
    tags: ['Explainable', 'Vendor-Neutral'],
    artifact: `# Incident INC-092-A — CRITICAL
# Rule: SSH-BRUTEFORCE-THEN-ACCESS-v2

TIMELINE (all times IST, 2026-09-23)
14:22:10  HIGH    SSH brute-force — 47 attempts
            src: host-token-7f3a -> dst: 10.0.0.1:22
            Source: PA-FW-MH-01 (Firewall)

14:24:33  MEDIUM  Port scan — 18 ports probed
            src: host-token-7f3a -> dst: 10.0.0.0/24
            Source: Suricata-IDS-01

14:27:51  CRITICAL  Successful SSH login — new geo
            auth_method: password | new_country: CN
            Source: Linux-Auth-Log-Server-01

CORRELATION RULE
Rule      : SSH-BRUTEFORCE-THEN-ACCESS-v2
Logic     : brute_force AND port_scan AND success
            within 600s, same src_token
Risk Score: 95 / 100  ->  CRITICAL
MITRE ATT&CK:
  T1110 Brute Force
  T1046 Network Service Scanning
  T1078 Valid Accounts`,
  },
  {
    id: 6,
    iconName: 'Search',
    color: 'var(--color-text-primary)',
    title: 'Step 6 — Investigate',
    subtitle: 'Lineage, risk reasons, data quality, and evidence access',
    narrative: `A SOC Analyst opens the Event Detail view. ULPF presents full event lineage (parser version, privacy policy applied), risk explanation (which rule fired and why each condition matched), a data quality score with missing-field breakdown, and a controlled Raw Vault evidence request button.\n\nEvery analyst action is written to the immutable audit log with timestamp, user identity, and action type.`,
    tags: ['Explainable', 'Forensics-Grade', 'Audit-Ready'],
    artifact: `# Event Detail — evt-9f3c2a-20260923-1422

LINEAGE
raw_source   : PA-FW-MH-01 (Palo Alto, CEF)
parser       : pan-panos-cef-v1.1 (approved 2026-09-10)
privacy_pol  : MHA-Policy-01
normalizer   : ulpf-ecs-v1.0
schema_ver   : 1.0

DATA QUALITY SCORE  94 / 100
Required fields present  : 18/18
Timestamps valid         : yes
geo_ip enrichment        : MISSING (-3)
asset_owner lookup       : MISSING (-3)
Schema validation        : PASSED

RISK EXPLANATION
Rule triggered : SSH-BRUTEFORCE-THEN-ACCESS-v2
Reason 1       : 47 failed logins in 60s window
Reason 2       : Port scan within 2 min of brute-force
Reason 3       : Successful login from new country (CN)
Confidence     : HIGH  |  Score: 95/100

RAW EVIDENCE ACCESS
[Request Raw Access] <- Requires Forensics Officer role
Audit entry auto-created on access request`,
  },
  {
    id: 7,
    iconName: 'RotateCcw',
    color: '#10b981',
    title: 'Step 7 — Improve',
    subtitle: 'Update parser v1.0 → v1.1 and replay historical raw logs',
    narrative: `A Parser Developer notices that the Palo Alto CEF parser v1.0 was missing the attempt_count field, causing 3% of events to lose that enrichment. They update the YAML definition, publish parser v1.1, and trigger a replay of the last 7 days of raw logs through the new parser.\n\nAll historical events are re-normalized with improved extraction — without discarding the originals. This is only possible because ULPF preserves every raw log in the Raw Vault.`,
    tags: ['Replayable', 'Extensible', 'Vendor-Neutral'],
    artifact: `# Parser Registry — pan-panos-cef

VERSION HISTORY
v1.0  Published: 2026-09-10  Status: DEPRECATED
      Fields: 21  |  Missing: attempt_count
      Normalization rate: 91.2%

v1.1  Published: 2026-09-23  Status: ACTIVE
      Fields: 22  |  Added: attempt_count
      Normalization rate: 94.1%  (+2.9%)
      Approved by: Jane Smith (Security Admin)

REPLAY JOB — rjob-20260923-pa-v11
Target parser : pan-panos-cef-v1.1
Date range    : 2026-09-16 to 2026-09-23
Raw events    : 182,443
Re-normalized : 182,443 / 182,443  (100%)
Improved      : 5,473 events gained attempt_count
Duration      : 4m 12s
Status        : COMPLETED

RESULT
Historical data improved without data loss.
Original raw logs unchanged in Raw Vault.
Audit log records replay job and approver.`,
  },
]

const ICON_MAP: Record<string, React.ElementType> = {
  UploadCloud, Cpu, ShieldOff, ShieldCheck, AlertTriangle, Search, RotateCcw
}

function getTagClass(t: string) {
  if (t === 'Forensics-Grade') return 'tag-forensics'
  if (t === 'Privacy-Aware') return 'tag-privacy'
  if (t === 'Audit-Ready') return 'tag-audit'
  if (t === 'Replayable') return 'tag-replay'
  if (t === 'Explainable') return 'tag-explain'
  if (t === 'Scalable by Design') return 'tag-scale'
  return 'tag-neutral'
}

function colorLine(line: string, i: number) {
  if (line.includes('VERIFIED') || line.includes('COMPLETED') || line.includes('FORENSICALLY SOUND') || line.includes('PASSED')) {
    return <span key={i} style={{ color: '#10b981', fontWeight: 700 }}>{line}{'\n'}</span>
  }
  if (line.includes('REDACTED') || line.includes('████') || line.includes('SENSITIVE')) {
    return <span key={i} style={{ color: '#f87171' }}>{line}{'\n'}</span>
  }
  if (line.startsWith('#')) {
    return <span key={i} style={{ color: 'var(--color-text-muted)' }}>{line}{'\n'}</span>
  }
  if (line.match(/^[-─]+$/)) {
    return <span key={i} style={{ color: 'var(--color-border)' }}>{line}{'\n'}</span>
  }
  if (line.includes('CRITICAL') || line.includes('HIGH    ')) {
    return <span key={i} style={{ color: '#f87171' }}>{line}{'\n'}</span>
  }
  if (line.includes('MEDIUM  ')) {
    return <span key={i} style={{ color: '#fbbf24' }}>{line}{'\n'}</span>
  }
  if (line.includes('ACTIVE') || line.includes('PUBLISHED')) {
    return <span key={i} style={{ color: 'var(--color-success)' }}>{line}{'\n'}</span>
  }
  if (line.includes('DEPRECATED')) {
    return <span key={i} style={{ color: '#f87171' }}>{line}{'\n'}</span>
  }
  if (line.includes(':') && !line.startsWith(' ')) {
    const idx = line.indexOf(':')
    return (
      <span key={i}>
        <span style={{ color: 'var(--color-text-primary)' }}>{line.slice(0, idx + 1)}</span>
        <span>{line.slice(idx + 1)}</span>
        {'\n'}
      </span>
    )
  }
  return <span key={i}>{line}{'\n'}</span>
}

export default function DemoJourney() {
  const [step, setStep] = useState(0)
  const navigate = useNavigate()
  const current = STEPS[step]
  const Icon = ICON_MAP[current.iconName]

  return (
    <div style={{ minHeight: 'calc(100vh - 48px)', display: 'flex', flexDirection: 'column', margin: '-24px -32px', background: 'var(--color-bg-primary)' }}>
      {/* Top bar */}
      <div style={{ background: 'var(--color-bg-secondary)', borderBottom: '1px solid var(--color-border)', padding: '12px 28px', display: 'flex', alignItems: 'center', gap: 16 }}>
        <button className="btn-ghost" style={{ padding: '6px 12px', fontSize: 12 }} onClick={() => navigate('/')}>
          <X size={14} style={{ display: 'inline', marginRight: 6 }} />
          Exit Journey
        </button>
        <div style={{ flex: 1 }}>
          <div className="demo-progress-bar">
            <div className="demo-progress-fill" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
          </div>
        </div>
        <span style={{ fontSize: 12, color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>Step {step + 1} of {STEPS.length}</span>
      </div>

      {/* Step indicators */}
      <div style={{ background: 'var(--color-bg-primary)', padding: '12px 28px', borderBottom: '1px solid var(--color-border)' }}>
        <div className="demo-step-indicator">
          {STEPS.map((s, i) => (
            <div key={s.id} style={{ display: 'flex', alignItems: 'center', flex: i < STEPS.length - 1 ? 1 : 'none' }}>
              <button
                onClick={() => setStep(i)}
                title={s.title}
                className={`demo-step-dot ${i < step ? 'done' : i === step ? 'active' : 'pending'}`}
                style={{ cursor: 'pointer', border: 'none' }}
              >
                {i < step ? '✓' : s.id}
              </button>
              {i < STEPS.length - 1 && <div className={`demo-step-line ${i < step ? 'done' : ''}`} />}
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', marginTop: 6 }}>
          {STEPS.map((s, i) => (
            <div key={s.id} style={{ flex: 1, fontSize: 9, color: i === step ? 'var(--color-text-primary)' : 'var(--color-border)', fontWeight: i === step ? 700 : 400, textAlign: 'center', overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis', padding: '0 2px', transition: 'color 0.2s' }}>
              {s.title.split(' — ')[0]}
            </div>
          ))}
        </div>
      </div>

      {/* Main content */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr', minHeight: 0 }}>
        {/* Left narrative */}
        <div style={{ padding: '32px 40px', borderRight: '1px solid var(--color-border)', display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 16 }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 10, background: `${current.color}18`, border: `1px solid ${current.color}40`, borderRadius: 8, padding: '8px 14px', width: 'fit-content' }}>
            <Icon size={18} color={current.color} />
            <span style={{ fontSize: 13, fontWeight: 700, color: current.color }}>{current.title}</span>
          </div>
          <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-text-primary)', lineHeight: 1.3 }}>{current.subtitle}</h2>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {current.tags.map(t => (
              <span key={t} className={`tag-label ${getTagClass(t)}`}>{t}</span>
            ))}
          </div>
          <p style={{ fontSize: 13, color: 'var(--color-text-muted)', lineHeight: 1.8, borderLeft: `3px solid ${current.color}40`, paddingLeft: 16, whiteSpace: 'pre-line' }}>
            {current.narrative}
          </p>
          <div style={{ padding: '12px 16px', background: 'transparent', borderRadius: 8, border: '1px solid transparent' }}>
            <div style={{ fontSize: 10, color: 'var(--color-text-primary)', fontWeight: 700, letterSpacing: '0.07em', marginBottom: 4, textTransform: 'uppercase' }}>ULPF Product Story</div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', lineHeight: 1.6 }}>
              India-first · Vendor-neutral · Privacy-aware · Forensics-grade framework for converting heterogeneous logs into trustworthy, normalized, analytics-ready security telemetry.
            </div>
          </div>
        </div>

        {/* Right artifact */}
        <div style={{ padding: '32px 40px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <div style={{ fontSize: 11, color: 'var(--color-text-muted)', fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', marginBottom: 10 }}>
            Live Artifact — What ULPF produces at this step
          </div>
          <pre className="demo-artifact" style={{ flex: 1, maxHeight: 460 }}>
            {current.artifact.split('\n').map((line, i) => colorLine(line, i))}
          </pre>
        </div>
      </div>

      {/* Bottom nav */}
      <div style={{ background: 'var(--color-bg-secondary)', borderTop: '1px solid var(--color-border)', padding: '12px 28px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button className="btn-ghost" onClick={() => setStep(s => Math.max(0, s - 1))} disabled={step === 0} style={{ opacity: step === 0 ? 0.3 : 1 }}>
          <ChevronLeft size={16} style={{ display: 'inline', marginRight: 4 }} />
          Previous
        </button>
        <div style={{ display: 'flex', gap: 6 }}>
          {STEPS.map((_, i) => (
            <div key={i} onClick={() => setStep(i)} style={{ width: i === step ? 20 : 6, height: 6, borderRadius: 3, background: i === step ? 'var(--color-text-primary)' : i < step ? '#10b981' : 'var(--color-border)', cursor: 'pointer', transition: 'all 0.3s' }} />
          ))}
        </div>
        {step < STEPS.length - 1 ? (
          <button className="btn-primary" onClick={() => setStep(s => s + 1)}>
            Next Step <ChevronRight size={16} style={{ display: 'inline', marginLeft: 4 }} />
          </button>
        ) : (
          <button className="btn-primary" style={{ background: 'linear-gradient(135deg,#059669,#10b981)' }} onClick={() => navigate('/')}>
            <CheckCircle2 size={16} style={{ display: 'inline', marginRight: 6 }} />
            Demo Complete — Return to Dashboard
          </button>
        )}
      </div>
    </div>
  )
}
