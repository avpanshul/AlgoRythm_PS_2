import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Check, ChevronRight, Upload, Database, Lock, Play, ShieldAlert, Activity, AlertTriangle } from 'lucide-react'
import { api } from '../api/client'

const STEPS = [
  'Source Information',
  'Sample Logs',
  'Format Detection',
  'Field Mapping',
  'Privacy Policy',
  'Test & Activate',
]

const MAX_SAMPLE_BYTES = 5 * 1024 * 1024
const ALLOWED_EXTENSIONS = ['.txt', '.log', '.csv', '.json']

export default function AddLogSourceWizard() {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  // Monotonic run id for the step-2 sample analysis: going Back mid-analysis
  // invalidates the in-flight request so a late response can never overwrite
  // state (or re-enable the spinner) after the user has already moved on.
  const analysisRunRef = useRef(0)
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [fileName, setFileName] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sourceData, setSourceData] = useState({
    name: '',
    org: '',
    type: '',
    vendor: '',
    format: '',
    sample: '',
  })
  const [analysis, setAnalysis] = useState<any>(null)
  const [matchedParser, setMatchedParser] = useState<any>(null)
  const [selectedPolicyId, setSelectedPolicyId] = useState<number | 'default' | null>('default')

  const { data: orgsData } = useQuery({
    queryKey: ['organizations'],
    queryFn: () => api.getOrganizations(),
    retry: false,
  })
  const { data: policiesData } = useQuery({
    queryKey: ['privacy-policies'],
    queryFn: () => api.getPrivacyPolicies(),
    retry: false,
  })

  const organizations: any[] = Array.isArray(orgsData) ? orgsData : (orgsData?.items || [])
  const privacyPolicies: any[] = Array.isArray(policiesData) ? policiesData : (policiesData?.items || [])

  useEffect(() => {
    if (organizations.length && !sourceData.org) {
      setSourceData((s) => ({ ...s, org: organizations[0].id }))
    }
  }, [organizations, sourceData.org])

  const loadSampleFromFile = async (file: File) => {
    setError(null)
    const lower = file.name.toLowerCase()
    const okExt = ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext))
    if (!okExt) {
      setError(`Unsupported file type. Use ${ALLOWED_EXTENSIONS.join(', ')}.`)
      return
    }
    if (file.size > MAX_SAMPLE_BYTES) {
      setError('File exceeds the 5MB sample limit.')
      return
    }
    try {
      const text = await file.text()
      if (!text.trim()) {
        setError('The selected file is empty.')
        return
      }
      setFileName(file.name)
      setSourceData((s) => ({ ...s, sample: text }))
    } catch (e: any) {
      setError(e?.message || 'Could not read that file.')
    }
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) void loadSampleFromFile(file)
  }

  const nextStep = () => {
    if (step === 1) {
      if (!sourceData.name.trim()) {
        setError('Source name is required.')
        return
      }
      setError(null)
      setStep(2)
      return
    }

    if (step === 2) {
      if (!sourceData.sample.trim()) {
        setError('Paste or upload a real sample log before detecting format.')
        return
      }
      // Move to step 3 immediately so the analyzing UI is visible while the
      // real detector + LLM classifier runs (previously loading stayed on
      // step 2 with no spinner, which looked like Detect Format was broken).
      const runId = ++analysisRunRef.current
      setLoading(true)
      setError(null)
      setAnalysis(null)
      setMatchedParser(null)
      setStep(3)
      api.analyzeSample({
        sample: sourceData.sample,
        vendor: sourceData.vendor || undefined,
        device_type: sourceData.type || undefined,
      }).then(async (result: any) => {
        if (runId !== analysisRunRef.current) return
        setAnalysis(result)
        const detectedFormat = result.format_type && result.format_type !== 'Unknown'
          ? result.format_type
          : sourceData.format
        if (detectedFormat) {
          setSourceData((s) => ({ ...s, format: detectedFormat }))
        }
        try {
          const parsers = await api.getParsers()
          const list = Array.isArray(parsers) ? parsers : []
          setMatchedParser(
            list.find((p: any) => p.status === 'published' && p.format_type === detectedFormat) || null,
          )
        } catch {
          setMatchedParser(null)
        }
        setLoading(false)
      }).catch((e: any) => {
        if (runId !== analysisRunRef.current) return
        setLoading(false)
        setError(e?.response?.data?.detail || e?.message || 'Could not analyze this sample.')
      })
      return
    }

    if (step < 6) {
      setError(null)
      setStep(step + 1)
      return
    }

    setError(null)
    setLoading(true)
    const id = (sourceData.name || 'source')
      .toUpperCase().replace(/[^A-Z0-9]+/g, '-').replace(/(^-|-$)/g, '')
      .slice(0, 24) + '-' + Math.random().toString(36).slice(2, 6).toUpperCase()
    api.createSource({
      id,
      name: sourceData.name.trim(),
      vendor: sourceData.vendor || undefined,
      device_type: sourceData.type || undefined,
      organization_id: sourceData.org || undefined,
      enabled: true,
    }).then(() => {
      setLoading(false)
      navigate('/sources')
    }).catch((e: any) => {
      setLoading(false)
      setError(e?.response?.data?.detail || e?.message || 'Could not create the source.')
    })
  }

  const prevStep = () => {
    // Back was effectively dead on step 3: it stayed disabled for the whole
    // (minutes-long, on CPU) analysis, with no way to cancel. Back now
    // invalidates the in-flight analysis and returns to step 2 immediately;
    // the stale response is ignored when it eventually arrives.
    if (step === 3 && loading) {
      analysisRunRef.current += 1
      setLoading(false)
      setError(null)
      setStep(2)
      return
    }
    setError(null)
    setStep((s) => (s > 1 ? s - 1 : 1))
  }

  const canAdvance =
    !loading &&
    (step !== 1 || !!sourceData.name.trim()) &&
    (step !== 2 || !!sourceData.sample.trim())

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 1000, margin: '0 auto', paddingBottom: 40 }}>

      <div style={{ paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>
        <h1 className="page-title">Add log source</h1>
        <p className="page-subtitle" style={{ margin: 0 }}>Configure a new log ingestion source and parser pipeline.</p>
      </div>

      <div style={{ display: 'flex', gap: 4, fontSize: 13, flexWrap: 'wrap' }}>
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
                }}
              >
                {num}. {s}
              </span>
              {num < STEPS.length && <span style={{ color: '#d1d5db', margin: '0 8px' }}>›</span>}
            </span>
          )
        })}
      </div>

      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 28, minHeight: 400 }}>
        {step === 1 && (
          <div style={{ maxWidth: 600 }}>
            <h2 style={{ fontSize: 18, color: 'var(--color-text-primary)', marginBottom: 24 }}>Source Information</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <label style={{ display: 'block', fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 8 }}>Organization</label>
                {organizations.length > 0 ? (
                  <select
                    className="cyber-input"
                    style={{ width: '100%' }}
                    value={sourceData.org}
                    onChange={(e) => setSourceData({ ...sourceData, org: e.target.value })}
                  >
                    {organizations.map((o: any) => (
                      <option key={o.id} value={o.id}>{o.name || o.id}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    className="cyber-input"
                    style={{ width: '100%' }}
                    placeholder="Organization id (optional — none registered yet)"
                    value={sourceData.org}
                    onChange={(e) => setSourceData({ ...sourceData, org: e.target.value })}
                  />
                )}
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 8 }}>Source Name</label>
                <input
                  className="cyber-input"
                  style={{ width: '100%' }}
                  placeholder="e.g. Data Center Firewall"
                  value={sourceData.name}
                  onChange={(e) => setSourceData({ ...sourceData, name: e.target.value })}
                />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div>
                  <label style={{ display: 'block', fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 8 }}>Source Type</label>
                  <input
                    className="cyber-input"
                    style={{ width: '100%' }}
                    placeholder="e.g. Firewall, IDS/IPS, Web Server"
                    value={sourceData.type}
                    onChange={(e) => setSourceData({ ...sourceData, type: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 8 }}>Vendor / Product</label>
                  <input
                    className="cyber-input"
                    style={{ width: '100%' }}
                    placeholder="e.g. Palo Alto, Cisco, Fortinet"
                    value={sourceData.vendor}
                    onChange={(e) => setSourceData({ ...sourceData, vendor: e.target.value })}
                  />
                </div>
              </div>
              {error && <p style={{ color: '#c81e1e', fontSize: 13, margin: 0 }}>{error}</p>}
            </div>
          </div>
        )}

        {step === 2 && (
          <div>
            <h2 style={{ fontSize: 18, color: 'var(--color-text-primary)', marginBottom: 16 }}>Upload Sample Logs</h2>
            <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 24 }}>
              Provide a real sample of raw logs for format detection and field mapping. Nothing is pre-filled.
            </p>

            <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
              <div
                style={{
                  flex: 1,
                  minWidth: 240,
                  border: `2px dashed ${dragOver ? '#1a56db' : 'var(--color-border)'}`,
                  borderRadius: 8,
                  padding: 40,
                  textAlign: 'center',
                  background: dragOver ? 'rgba(26,86,219,0.04)' : 'transparent',
                }}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={onDrop}
              >
                <Upload size={32} color="var(--color-text-muted)" style={{ margin: '0 auto 16px' }} />
                <div style={{ color: 'var(--color-text-primary)', fontWeight: 500, marginBottom: 8 }}>Drag & drop log file here</div>
                <div style={{ color: 'var(--color-text-muted)', fontSize: 12, marginBottom: 24 }}>.txt, .log, .csv, .json (max 5MB)</div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".txt,.log,.csv,.json,text/plain,application/json,text/csv"
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) void loadSampleFromFile(file)
                    e.target.value = ''
                  }}
                />
                <button type="button" className="btn-secondary" onClick={() => fileInputRef.current?.click()}>
                  Browse Files
                </button>
                {fileName && (
                  <div style={{ marginTop: 12, fontSize: 12, color: '#057a55' }}>Loaded: {fileName}</div>
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', color: 'var(--color-text-muted)', fontWeight: 600 }}>OR</div>
              <div style={{ flex: 1, minWidth: 240, display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>Paste Raw Text</span>
                  {sourceData.sample && (
                    <button
                      type="button"
                      className="btn-secondary"
                      style={{ padding: '2px 8px', fontSize: 11 }}
                      onClick={() => { setSourceData({ ...sourceData, sample: '' }); setFileName(null) }}
                    >
                      Clear
                    </button>
                  )}
                </div>
                <textarea
                  className="cyber-input"
                  style={{ flex: 1, minHeight: 200, fontFamily: 'monospace', fontSize: 12, whiteSpace: 'pre-wrap' }}
                  placeholder="Paste raw log lines here…"
                  value={sourceData.sample}
                  onChange={(e) => { setFileName(null); setSourceData({ ...sourceData, sample: e.target.value }) }}
                />
              </div>
            </div>
            {error && <p style={{ color: '#c81e1e', fontSize: 13, marginTop: 16 }}>{error}</p>}
          </div>
        )}

        {step === 3 && (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            {loading ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>
                <div className="pulse-dot" style={{ width: 40, height: 40, background: 'var(--color-text-primary)' }} />
                <div style={{ color: 'var(--color-text-primary)', fontSize: 16 }}>Analyzing your sample…</div>
                <div style={{ color: 'var(--color-text-muted)', fontSize: 13, maxWidth: 480 }}>
                  Running the real format detector, then classifying each field with the local LLM one at a time — this can take a few minutes on CPU for samples with several fields.
                </div>
              </div>
            ) : error ? (
              <div style={{ maxWidth: 500, margin: '0 auto', textAlign: 'left' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
                  <AlertTriangle size={24} color="#c81e1e" />
                  <h2 style={{ fontSize: 18, color: 'var(--color-text-primary)', margin: 0 }}>Analysis Failed</h2>
                </div>
                <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>{error}</p>
              </div>
            ) : !analysis || analysis.status !== 'classified' ? (
              <div style={{ maxWidth: 500, margin: '0 auto', textAlign: 'left' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
                  <AlertTriangle size={24} color="#f59e0b" />
                  <h2 style={{ fontSize: 18, color: 'var(--color-text-primary)', margin: 0 }}>
                    {analysis?.status === 'undetectable_format' ? 'Format Not Recognized' : 'Could Not Parse Sample'}
                  </h2>
                </div>
                <p style={{ fontSize: 13, color: 'var(--color-text-muted)', lineHeight: 1.5 }}>
                  {analysis?.detail || 'The real detector could not confidently classify this sample.'} You can still create this source now — a real parser can be drafted from real production traffic later in Parser Lab.
                </p>
              </div>
            ) : (
              <div style={{ maxWidth: 500, margin: '0 auto', textAlign: 'left' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
                  <div style={{ width: 48, height: 48, borderRadius: 24, background: 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Check size={24} color="#10b981" />
                  </div>
                  <div>
                    <h2 style={{ fontSize: 18, color: 'var(--color-text-primary)', margin: 0 }}>Format Detected: {analysis.format_type}</h2>
                    <p style={{ fontSize: 13, color: 'var(--color-text-muted)', margin: 0 }}>
                      Real detector confidence: {Math.round((analysis.format_confidence || 0) * 100)}% — run against the sample you provided
                    </p>
                  </div>
                </div>

                <div style={{ background: 'var(--color-bg-primary)', padding: 20, borderRadius: 8, border: '1px solid var(--color-border)', marginBottom: 24 }}>
                  <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 8, textTransform: 'uppercase' }}>Existing Published Parser</div>
                  {matchedParser ? (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ fontSize: 16, color: 'var(--color-text-primary)', fontWeight: 500 }}>{matchedParser.name || matchedParser.id}</div>
                      <span className="badge-info" style={{ padding: '4px 8px', borderRadius: 4, fontSize: 11 }}>v{matchedParser.version}</span>
                    </div>
                  ) : (
                    <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
                      No published parser matches {analysis.format_type} yet — one can be drafted in Parser Lab.
                    </div>
                  )}
                </div>

                <p style={{ fontSize: 13, color: 'var(--color-text-muted)', lineHeight: 1.5 }}>
                  The real deterministic {analysis.format_type} parser found {analysis.total_fields_seen} field{analysis.total_fields_seen === 1 ? '' : 's'} in this sample; the local LLM classified {analysis.mapped_field_count} of them to a canonical field with reasonable confidence. Proceed to review the mapping.
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
                <p style={{ fontSize: 13, color: 'var(--color-text-muted)', margin: 0 }}>
                  Real field classifications from the local LLM, run against your sample. Mappings are not saved to a parser yet — finalize in Parser Lab after this source is created.
                </p>
              </div>
            </div>

            {!analysis?.field_classifications?.length ? (
              <div style={{ padding: '32px 0', textAlign: 'center', color: 'var(--color-text-muted)', fontSize: 13 }}>
                No fields were classified for this sample. You can still create the source and map fields later in Parser Lab.
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr><th>Raw Source Field</th><th>Sample Value</th><th>Canonical Target</th><th>Confidence</th></tr>
                </thead>
                <tbody>
                  {analysis.field_classifications.map((c: any, i: number) => {
                    const unknown = c.selected_field === 'UNKNOWN'
                    const pct = Math.round((c.confidence || 0) * 100)
                    return (
                      <tr key={i}>
                        <td style={{ fontFamily: 'monospace', color: 'var(--color-text-muted)' }}>{c.raw_field}</td>
                        <td style={{ fontFamily: 'monospace', color: 'var(--color-text-primary)' }}>{c.sample_value}</td>
                        <td style={{ fontWeight: 600, color: unknown ? 'var(--color-text-muted)' : 'var(--color-text-primary)' }} title={c.reason || ''}>
                          {unknown ? 'Unmapped' : c.selected_field}
                        </td>
                        <td><span style={{ color: unknown ? '#8994b2' : pct >= 90 ? '#10b981' : pct >= 50 ? '#f59e0b' : '#c81e1e' }}>{pct}%</span></td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}

        {step === 5 && (
          <div style={{ maxWidth: 800 }}>
            <h2 style={{ fontSize: 18, color: 'var(--color-text-primary)', marginBottom: 8 }}>Privacy & Redaction Policy</h2>
            <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 24 }}>
              Choose a registered privacy policy, or keep the pipeline default (email / Aadhaar / phone / PAN regex redaction that always runs on normalized messages).
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              <div
                role="button"
                tabIndex={0}
                onClick={() => setSelectedPolicyId('default')}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setSelectedPolicyId('default') }}
                style={{
                  border: selectedPolicyId === 'default' ? '2px solid var(--color-text-primary)' : '1px solid var(--color-border)',
                  borderRadius: 8,
                  padding: 20,
                  cursor: 'pointer',
                  position: 'relative',
                }}
              >
                {selectedPolicyId === 'default' && (
                  <div style={{ position: 'absolute', top: 20, right: 20 }}><Check color="var(--color-text-primary)" size={20} /></div>
                )}
                <h3 style={{ fontSize: 14, color: 'var(--color-text-primary)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Lock size={16} /> Pipeline default PII redaction
                </h3>
                <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 16 }}>
                  Always-on regex redaction of email, Aadhaar-shaped, Indian mobile, and PAN-shaped strings on the normalized message.
                </p>
              </div>

              {privacyPolicies.filter((p: any) => p.enabled !== false).map((p: any) => (
                <div
                  key={p.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedPolicyId(p.id)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setSelectedPolicyId(p.id) }}
                  style={{
                    border: selectedPolicyId === p.id ? '2px solid var(--color-text-primary)' : '1px solid var(--color-border)',
                    borderRadius: 8,
                    padding: 20,
                    cursor: 'pointer',
                    position: 'relative',
                  }}
                >
                  {selectedPolicyId === p.id && (
                    <div style={{ position: 'absolute', top: 20, right: 20 }}><Check color="var(--color-text-primary)" size={20} /></div>
                  )}
                  <h3 style={{ fontSize: 14, color: 'var(--color-text-primary)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <ShieldAlert size={16} /> {p.name}
                  </h3>
                  <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 16 }}>
                    {p.description || 'No description provided.'}
                  </p>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {(Array.isArray(p.rules) ? p.rules : []).slice(0, 6).map((r: any, i: number) => (
                      <span key={i} className="badge-info" style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4 }}>
                        {r.pattern || r.field_types || r.replacement || `rule-${i + 1}`}
                      </span>
                    ))}
                    {!p.rules?.length && (
                      <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>No rules listed</span>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {privacyPolicies.length === 0 && (
              <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 16 }}>
                No custom privacy policies are registered yet. You can add them under Privacy Policies; the pipeline default still applies.
              </p>
            )}
          </div>
        )}

        {step === 6 && (
          <div style={{ textAlign: 'center', padding: '40px 0', maxWidth: 600, margin: '0 auto' }}>
            <div style={{ width: 64, height: 64, borderRadius: 32, background: 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px' }}>
              <Play size={32} color="#10b981" />
            </div>
            <h2 style={{ fontSize: 24, color: 'var(--color-text-primary)', marginBottom: 12 }}>Ready to Activate</h2>
            <p style={{ fontSize: 14, color: 'var(--color-text-muted)', marginBottom: 32, lineHeight: 1.5 }}>
              Source <strong>{sourceData.name || 'New Source'}</strong> will be registered as a real source. It ingests via this deployment&apos;s normal HTTP/syslog endpoints; real format/quality checks run on its first actual ingested event, not only on this wizard&apos;s preview.
            </p>

            {error && <div style={{ color: '#c81e1e', fontSize: 13, marginBottom: 16, textAlign: 'left' }}>{error}</div>}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, textAlign: 'left', marginBottom: 32 }}>
              <div style={{ background: 'var(--color-bg-primary)', padding: 16, borderRadius: 8, border: '1px solid var(--color-border)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, color: 'var(--color-text-muted)', fontSize: 12, textTransform: 'uppercase' }}><Database size={14} /> Source Type</div>
                <div style={{ fontSize: 18, color: 'var(--color-text-primary)', fontWeight: 600 }}>{sourceData.type || 'Unspecified'}</div>
                <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{sourceData.vendor || 'Generic'}{sourceData.format ? ` · ${sourceData.format}` : ''}</div>
              </div>
              <div style={{ background: 'var(--color-bg-primary)', padding: 16, borderRadius: 8, border: '1px solid var(--color-border)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, color: 'var(--color-text-muted)', fontSize: 12, textTransform: 'uppercase' }}><Activity size={14} /> Status</div>
                <div style={{ fontSize: 18, color: '#10b981', fontWeight: 600 }}>{loading ? 'Creating…' : 'Ready'}</div>
                <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>Registers a real Source row</div>
              </div>
            </div>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <button type="button" className="btn-secondary" disabled={step === 1 || (loading && step !== 3)} onClick={prevStep}>
          Back
        </button>
        <button
          type="button"
          className="btn-primary"
          style={{ display: 'flex', alignItems: 'center', gap: 8 }}
          onClick={nextStep}
          disabled={!canAdvance}
        >
          {loading && step === 6 ? 'Creating…' : step === 6 ? 'Activate Source' : step === 2 ? 'Detect Format' : 'Next Step'}
          {step !== 6 && !loading && <ChevronRight size={16} />}
        </button>
      </div>
    </div>
  )
}
