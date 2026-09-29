import { useState } from 'react'
import { HelpCircle, X } from 'lucide-react'

const SECTIONS = [
  {
    title: 'Getting started',
    items: [
      'Log in with your account, or ask an admin to invite you from Administration → Users.',
      'Register a log source under Data Sources, or use the Add Source wizard to detect its format and field mapping from a real pasted sample.',
      'Once events are flowing, Dashboard and Log Explorer show real ingestion/parse/risk numbers -- an empty widget means no real data exists yet for that view, not a bug.',
    ],
  },
  {
    title: 'Core pipeline',
    items: [
      'Data Sources -- register and manage log sources.',
      'Parser Lab -- write, test, and publish the YAML source-pack a source uses to normalize its real fields.',
      'Log Explorer -- search and inspect normalized events, including raw payload, Merkle proof, and processing history per event.',
      'Integrity & Replay -- verify an event’s Merkle inclusion proof, re-run processing against stored raw logs, and manage the dead-letter queue for failed parses.',
    ],
  },
  {
    title: 'Detection & investigation',
    items: [
      'Correlation -- cross-source rule matches; "Run Evaluation" re-checks all rules against currently stored events.',
      'Entity Behavior -- per-IP/user behavioral baselines and anomaly reasons.',
      'Incident Cases -- manually opened or auto-opened by the live correlation cycle; Notify requires at least one on-call contact to be configured.',
      'Entity Graph, Attack Path, Timeline -- relationship and chronological views for one entity or one correlated incident.',
      'Threat Hunting -- save and re-run a query against normalized events.',
    ],
  },
  {
    title: 'Administration',
    items: [
      'Administration -- users, roles, organizations, and privacy policies.',
      'SIEM / Data Lake -- outbound integrations; Test runs a real connectivity check against the configured endpoint.',
      'Threat Intelligence -- add and search real indicators of compromise.',
      'Multi-CSE Supervisory -- aggregate-only rollup across organizations; assign sources to an organization to populate it.',
      'Settings -- platform name, timezone, and session timeout (session timeout genuinely changes how long a new login lasts).',
    ],
  },
]

export default function HelpButton() {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button
        onClick={() => setOpen(o => !o)}
        aria-label="Help"
        style={{
          position: 'fixed', bottom: 24, right: 24, zIndex: 150,
          width: 48, height: 48, borderRadius: '50%', border: 'none', cursor: 'pointer',
          background: 'linear-gradient(135deg, #0044A8, #0088FF)', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 6px 20px rgba(0,68,168,0.35)',
          transition: 'transform 0.15s ease',
        }}
        onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.transform = 'scale(1.08)' }}
        onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.transform = 'scale(1)' }}
      >
        <HelpCircle size={24} />
      </button>

      {open && (
        <>
          <div onClick={() => setOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 149, background: 'rgba(0,15,46,0.25)' }} />
          <div style={{
            position: 'fixed', bottom: 84, right: 24, zIndex: 151,
            width: 380, maxWidth: 'calc(100vw - 48px)', maxHeight: '70vh', overflowY: 'auto',
            background: '#fff', borderRadius: 16, boxShadow: '0 16px 48px rgba(0,15,92,0.25)',
            border: '1px solid rgba(0,68,168,0.1)', padding: 24,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <h2 style={{ fontSize: 17, fontWeight: 800, color: '#0a0e27', margin: 0 }}>Help & Guidelines</h2>
              <button onClick={() => setOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#8999b0' }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
              {SECTIONS.map(section => (
                <div key={section.title}>
                  <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#0044A8', marginBottom: 8 }}>
                    {section.title}
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {section.items.map((item, i) => (
                      <li key={i} style={{ fontSize: 12.5, color: '#334155', lineHeight: 1.5 }}>{item}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </>
  )
}
