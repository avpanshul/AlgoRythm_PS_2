import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, ChevronRight, Upload, Database, Lock, Play, ShieldAlert, Activity } from 'lucide-react'

const STEPS = [
  'Source Information',
  'Sample Logs',
  'Format Detection',
  'Field Mapping',
  'Privacy Policy',
  'Test & Activate'
]

export default function AddLogSourceWizard() {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [sourceData, setSourceData] = useState({
    name: '', org: 'ORG-PSU-001', type: 'Firewall', vendor: 'Palo Alto', format: 'CEF',
    sample: '', detected: false,
  })

  const nextStep = () => {
    if (step === 2) {
      setLoading(true)
      setTimeout(() => {
        setSourceData(s => ({ ...s, detected: true, format: 'CEF' }))
        setLoading(false)
        setStep(3)
      }, 1500)
    } else if (step < 6) {
      setStep(step + 1)
    } else {
      navigate('/sources')
    }
  }

  const prevStep = () => setStep(step > 1 ? step - 1 : 1)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 1000, margin: '0 auto', paddingBottom: 40 }}>

      {/* Wizard Header */}
      <div style={{ paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <h1 className="page-title">Add log source</h1>
        <p className="page-subtitle" style={{ margin: 0 }}>Configure a new log ingestion source and parser pipeline.</p>
      </div>

      {/* Stepper */}
      <div style={{ display: 'flex', gap: 4, fontSize: 13 }}>
        {STEPS.map((s, i) => {
          const num = i + 1
          const active = step === num
          const done = step > num
          return (
            <span key={s} style={{ display: 'flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap' }}>
              <span
                style={{
                  fontWeight: active ? 600 : 400,
                  color: active ? '#1a56db' : done ? '#057a55' : '#9ca3af',
                  borderBottom: active ? '2px solid #1a56db' : '2px solid transparent',
                  paddingBottom: 4,
                }}>
                {num}. {s}
              </span>
              {num < STEPS.length && <span style={{ color: '#d1d5db', margin: '0 8px' }}>›</span>}
            </span>
          )
        })}
      </div>

      {/* Step Content */}
      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 28, minHeight: 400 }}>
        {step === 1 && (
          <div style={{ maxWidth: 600 }}>
            <h2 style={{ fontSize: 18, color: 'var(--color-text-primary)', marginBottom: 24 }}>Source Information</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <label style={{ display: 'block', fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 8 }}>Organization</label>
                <select className="cyber-input" style={{ width: '100%' }} value={sourceData.org} onChange={e => setSourceData({...sourceData, org: e.target.value})}>
                  <option>ORG-PSU-001</option>
                  <option>ORG-DEF-002</option>
                  <option>ORG-FIN-003</option>
                </select>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 8 }}>Source Name</label>
                <input className="cyber-input" style={{ width: '100%' }} placeholder="e.g. Data Center Firewall" value={sourceData.name} onChange={e => setSourceData({...sourceData, name: e.target.value})} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div>
                  <label style={{ display: 'block', fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 8 }}>Source Type</label>
                  <select className="cyber-input" style={{ width: '100%' }} value={sourceData.type} onChange={e => setSourceData({...sourceData, type: e.target.value})}>
                    <option>Firewall</option>
                    <option>IDS/IPS</option>
                    <option>Linux Auth</option>
                    <option>Web Server</option>
                    <option>Cloud Audit</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 8 }}>Vendor / Product</label>
                  <input className="cyber-input" style={{ width: '100%' }} placeholder="e.g. Palo Alto, Cisco" value={sourceData.vendor} onChange={e => setSourceData({...sourceData, vendor: e.target.value})} />
                </div>
              </div>
            </div>
          </div>
        )}

        {step === 2 && (
          <div>
            <h2 style={{ fontSize: 18, color: 'var(--color-text-primary)', marginBottom: 16 }}>Upload Sample Logs</h2>
            <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 24 }}>Provide a sample of raw logs for format detection and parser generation.</p>
            
            <div style={{ display: 'flex', gap: 20 }}>
              <div style={{ flex: 1, border: '2px dashed var(--color-border)', borderRadius: 8, padding: 40, textAlign: 'center', background: 'transparent' }}>
                <Upload size={32} color="var(--color-text-muted)" style={{ margin: '0 auto 16px' }} />
                <div style={{ color: 'var(--color-text-primary)', fontWeight: 500, marginBottom: 8 }}>Drag & drop log file here</div>
                <div style={{ color: 'var(--color-text-muted)', fontSize: 12, marginBottom: 24 }}>.txt, .log, .csv, .json (max 5MB)</div>
                <button className="btn-secondary">Browse Files</button>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', color: 'var(--color-text-muted)', fontWeight: 600 }}>OR</div>
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>Paste Raw Text</span>
                  <button className="btn-secondary" style={{ padding: '2px 8px', fontSize: 11 }} onClick={() => setSourceData({...sourceData, sample: 'CEF:0|Security|threat|1.0|100|suspicious|7|src=10.0.0.1 dst=192.168.1.1 spt=443 dpt=80 user=admin'})}>Use Sample</button>
                </div>
                <textarea 
                  className="cyber-input" 
                  style={{ flex: 1, minHeight: 200, fontFamily: 'monospace', fontSize: 12, whiteSpace: 'pre-wrap' }} 
                  placeholder="Paste raw log lines here..."
                  value={sourceData.sample}
                  onChange={e => setSourceData({...sourceData, sample: e.target.value})}
                />
              </div>
            </div>
          </div>
        )}

        {step === 3 && (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            {loading ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>
                <div className="pulse-dot" style={{ width: 40, height: 40, background: 'var(--color-text-primary)' }} />
                <div style={{ color: 'var(--color-text-primary)', fontSize: 16 }}>Analyzing Log Format...</div>
                <div style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>Detecting delimiters, schemas, and timestamps</div>
              </div>
            ) : (
              <div style={{ maxWidth: 500, margin: '0 auto', textAlign: 'left' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
                  <div style={{ width: 48, height: 48, borderRadius: 24, background: 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Check size={24} color="#10b981" />
                  </div>
                  <div>
                    <h2 style={{ fontSize: 18, color: 'var(--color-text-primary)', margin: 0 }}>Format Detected: {sourceData.format}</h2>
                    <p style={{ fontSize: 13, color: 'var(--color-text-muted)', margin: 0 }}>High confidence match (98%)</p>
                  </div>
                </div>

                <div style={{ background: 'var(--color-bg-primary)', padding: 20, borderRadius: 8, border: '1px solid var(--color-border)', marginBottom: 24 }}>
                  <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 8, textTransform: 'uppercase' }}>Detected Parser Standard</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ fontSize: 16, color: 'var(--color-text-primary)', fontWeight: 500 }}>firewall-cef-parser</div>
                    <span className="badge-info" style={{ padding: '4px 8px', borderRadius: 4, fontSize: 11 }}>v1.2.0</span>
                  </div>
                </div>

                <p style={{ fontSize: 13, color: 'var(--color-text-muted)', lineHeight: 1.5 }}>
                  The system successfully detected the Common Event Format (CEF) structure and has matched it with the existing `firewall-cef-parser`. Proceed to verify field mappings.
                </p>
              </div>
            )}
          </div>
        )}

        {step === 4 && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 20 }}>
              <div>
                <h2 style={{ fontSize: 18, color: 'var(--color-text-primary)', marginBottom: 8 }}>Field Mapping</h2>
                <p style={{ fontSize: 13, color: 'var(--color-text-muted)', margin: 0 }}>Review automatically mapped fields against the ULPF Canonical Schema.</p>
              </div>
              <button className="btn-secondary" style={{ fontSize: 12 }}>Edit Mappings</button>
            </div>
            
            <table className="data-table">
              <thead>
                <tr><th>Raw Source Field</th><th>Sample Value</th><th>Canonical Target</th><th>Confidence</th></tr>
              </thead>
              <tbody>
                <tr>
                  <td style={{ fontFamily: 'monospace', color: 'var(--color-text-muted)' }}>src</td>
                  <td style={{ fontFamily: 'monospace', color: 'var(--color-text-primary)' }}>10.0.0.1</td>
                  <td style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>source.ip</td>
                  <td><span style={{ color: '#10b981' }}>100%</span></td>
                </tr>
                <tr>
                  <td style={{ fontFamily: 'monospace', color: 'var(--color-text-muted)' }}>dst</td>
                  <td style={{ fontFamily: 'monospace', color: 'var(--color-text-primary)' }}>192.168.1.1</td>
                  <td style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>destination.ip</td>
                  <td><span style={{ color: '#10b981' }}>100%</span></td>
                </tr>
                <tr>
                  <td style={{ fontFamily: 'monospace', color: 'var(--color-text-muted)' }}>user</td>
                  <td style={{ fontFamily: 'monospace', color: 'var(--color-text-primary)' }}>admin</td>
                  <td style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>user.name</td>
                  <td><span style={{ color: '#10b981' }}>98%</span></td>
                </tr>
                <tr>
                  <td style={{ fontFamily: 'monospace', color: 'var(--color-text-muted)' }}>act</td>
                  <td style={{ fontFamily: 'monospace', color: 'var(--color-text-primary)' }}>suspicious</td>
                  <td style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>event.action</td>
                  <td><span style={{ color: '#f59e0b' }}>85%</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        )}

        {step === 5 && (
          <div style={{ maxWidth: 800 }}>
            <h2 style={{ fontSize: 18, color: 'var(--color-text-primary)', marginBottom: 8 }}>Privacy & Redaction Policy</h2>
            <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 24 }}>Select a privacy policy to apply to events ingested from this source. Redacted fields are masked for Analyst roles.</p>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              <div style={{ border: '2px solid var(--color-text-primary)', borderRadius: 8, padding: 20, background: 'transparent', position: 'relative' }}>
                <div style={{ position: 'absolute', top: 20, right: 20 }}><Check color="var(--color-text-primary)" size={20} /></div>
                <h3 style={{ fontSize: 14, color: 'var(--color-text-primary)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}><ShieldAlert size={16} color="var(--color-text-primary)" /> Govt Critical Infrastructure</h3>
                <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 16 }}>Strict masking of all IPs, usernames, and hostnames.</p>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <span className="badge-info" style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4 }}>source.ip</span>
                  <span className="badge-info" style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4 }}>destination.ip</span>
                  <span className="badge-info" style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4 }}>user.name</span>
                </div>
              </div>

              <div style={{ border: '1px solid var(--color-border)', borderRadius: 8, padding: 20, cursor: 'pointer' }}>
                <h3 style={{ fontSize: 14, color: 'var(--color-text-primary)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}><Lock size={16} color="var(--color-text-muted)" /> Default Analytics Policy</h3>
                <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 16 }}>Basic PII protection (Emails, Phone, Aadhaar, PAN).</p>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <span className="badge-info" style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: 'var(--color-border)', color: 'var(--color-text-muted)' }}>user.email</span>
                  <span className="badge-info" style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: 'var(--color-border)', color: 'var(--color-text-muted)' }}>user.phone</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {step === 6 && (
          <div style={{ textAlign: 'center', padding: '40px 0', maxWidth: 600, margin: '0 auto' }}>
            <div style={{ width: 64, height: 64, borderRadius: 32, background: 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px' }}>
              <Play size={32} color="#10b981" />
            </div>
            <h2 style={{ fontSize: 24, color: 'var(--color-text-primary)', marginBottom: 12 }}>Ready to Activate</h2>
            <p style={{ fontSize: 14, color: 'var(--color-text-muted)', marginBottom: 32, lineHeight: 1.5 }}>
              Source <strong>{sourceData.name || 'New Source'}</strong> has been configured with the <strong>{sourceData.format}</strong> parser and <strong>Govt Critical Infrastructure</strong> privacy policy.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, textAlign: 'left', marginBottom: 32 }}>
              <div style={{ background: 'var(--color-bg-primary)', padding: 16, borderRadius: 8, border: '1px solid var(--color-border)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, color: 'var(--color-text-muted)', fontSize: 12, textTransform: 'uppercase' }}><Database size={14} /> Expected Ingestion</div>
                <div style={{ fontSize: 18, color: 'var(--color-text-primary)', fontWeight: 600 }}>Streaming Kafka Topic</div>
                <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>ulpf.raw.firewall</div>
              </div>
              <div style={{ background: 'var(--color-bg-primary)', padding: 16, borderRadius: 8, border: '1px solid var(--color-border)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, color: 'var(--color-text-muted)', fontSize: 12, textTransform: 'uppercase' }}><Activity size={14} /> Validation Score</div>
                <div style={{ fontSize: 18, color: '#10b981', fontWeight: 600 }}>98/100 Quality</div>
                <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>Passed schema checks</div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Footer Navigation */}
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <button className="btn-secondary" disabled={step === 1} onClick={prevStep}>
          Back
        </button>
        <button className="btn-primary" style={{ display: 'flex', alignItems: 'center', gap: 8 }} onClick={nextStep} disabled={loading || (step === 2 && !sourceData.sample)}>
          {step === 6 ? 'Activate Source' : step === 2 ? 'Detect Format' : 'Next Step'} 
          {step !== 6 && <ChevronRight size={16} />}
        </button>
      </div>

    </div>
  )
}
