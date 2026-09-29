import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { Save, Play, FileText, CheckCircle2, AlertTriangle, ShieldCheck, UploadCloud, Terminal, Server, Send, Plus, Search, Download, Upload, X } from 'lucide-react'
import { GlassCard } from '../components/glass/GlassCard'
import { anonymizedVendorLabel } from '../utils/anonymize'

export default function MappingRegistryPage() {
  const qc = useQueryClient()
  const { data: parsers, isLoading: parsersLoading, isError: parsersError } = useQuery({ queryKey: ['parsers'], queryFn: () => api.getParsers() })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [yamlDraft, setYamlDraft] = useState('')
  const [sampleLog, setSampleLog] = useState('')
  const [testResult, setTestResult] = useState<any>(null)
  const [testing, setTesting] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [publishError, setPublishError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [showImport, setShowImport] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)

  const parserList: any[] = Array.isArray(parsers) ? parsers : []
  const filteredList = search.trim()
    ? parserList.filter(p =>
        (p.name || '').toLowerCase().includes(search.toLowerCase()) ||
        (p.id || '').toLowerCase().includes(search.toLowerCase()) ||
        (p.format_type || '').toLowerCase().includes(search.toLowerCase()) ||
        (p.vendor || '').toLowerCase().includes(search.toLowerCase())
      )
    : parserList
  const selected = filteredList.find(p => p.id === selectedId) || parserList.find(p => p.id === selectedId) || filteredList[0]

  const exportSelected = () => {
    if (!selected) return
    setExportError(null)
    api.exportParser(selected.id)
      .then((bundle: any) => {
        const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${selected.id}.signed-bundle.json`
        a.click()
        URL.revokeObjectURL(url)
      })
      .catch((e: any) => setExportError(e?.response?.data?.detail || e?.message || 'Could not export this parser.'))
  }

  useEffect(() => {
    if (selected) {
      setYamlDraft(selected.config_yaml || '')
      setSampleLog(selected.sample_log || '')
      setTestResult(null)
      setPublishError(null)
    }
  }, [selected?.id])

  const runTest = () => {
    if (!selected) return
    setTesting(true)
    api.testParser(selected.id, { sample_log: sampleLog, config_yaml: yamlDraft })
      .then(setTestResult)
      .catch(e => setTestResult({ status: 'error', error: e?.message || 'request failed' }))
      .finally(() => setTesting(false))
  }

  const publish = () => {
    if (!selected) return
    setPublishing(true)
    setPublishError(null)
    api.publishParser(selected.id)
      .then(() => qc.invalidateQueries({ queryKey: ['parsers'] }))
      .catch((e: any) => setPublishError(e?.response?.data?.detail || e?.message || 'Could not publish this parser.'))
      .finally(() => setPublishing(false))
  }

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 24, paddingBottom: 40 }}>
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 'clamp(40px, 4vw, 52px)', fontWeight: 800, color: '#0044A8', letterSpacing: '-0.03em', lineHeight: 1.1 }}>
            Parser Lab
          </h1>
          <p style={{ fontSize: 'clamp(12px, 0.85vw, 13px)', color: '#8999b0', marginTop: 3 }}>
            Develop, test, and publish YAML source-pack parsers.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Search size={14} color="#8999b0" style={{ position: 'absolute', left: 10 }} />
            <input
              type="text" placeholder="Search parsers…" value={search} onChange={e => setSearch(e.target.value)}
              style={{
                padding: '8px 12px 8px 32px', borderRadius: 10, border: '1px solid rgba(0,68,168,0.2)',
                background: 'rgba(255,255,255,0.7)', fontSize: 13, outline: 'none', color: '#0a0e27', width: 160,
              }}
            />
          </div>
          <select
            value={selected?.id || ''}
            onChange={e => setSelectedId(e.target.value)}
            style={{
              padding: '8px 16px', borderRadius: 10, border: '1px solid rgba(0,68,168,0.2)',
              background: 'rgba(255,255,255,0.7)', fontSize: 13, outline: 'none', color: '#0a0e27', fontWeight: 600
            }}
          >
            {filteredList.map(p => <option key={p.id} value={p.id}>{p.name} ({p.id})</option>)}
          </select>
          <button onClick={() => setShowCreate(true)} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 10, background: '#fff', border: '1px solid rgba(0,68,168,0.2)', color: '#0044A8', fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>
            <Plus size={14} /> Create Parser
          </button>
          <button onClick={() => setShowImport(true)} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 10, background: '#fff', border: '1px solid rgba(0,68,168,0.2)', color: '#0044A8', fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>
            <Upload size={14} /> Import
          </button>
          <button onClick={exportSelected} disabled={!selected} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 10, background: '#fff', border: '1px solid rgba(0,68,168,0.2)', color: !selected ? '#b0bace' : '#0044A8', fontWeight: 600, fontSize: 13, cursor: !selected ? 'not-allowed' : 'pointer' }}>
            <Download size={14} /> Export
          </button>
          <button
            onClick={publish}
            disabled={!selected || selected.status === 'published' || publishing}
            style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', borderRadius: 10,
              background: 'linear-gradient(135deg, #057a55, #046c4e)', border: 'none',
              color: '#fff', fontWeight: 600, fontSize: 13, cursor: !selected || selected.status === 'published' || publishing ? 'not-allowed' : 'pointer',
              boxShadow: '0 4px 12px rgba(5,122,85,0.2)', opacity: !selected || selected.status === 'published' || publishing ? 0.6 : 1,
            }}
          >
            <Send size={14} /> {publishing ? 'Publishing…' : selected?.status === 'published' ? 'Already Published' : 'Publish Parser'}
          </button>
        </div>
      </header>

      {publishError && (
        <div style={{ padding: '10px 16px', borderRadius: 10, background: 'rgba(200,30,30,0.08)', color: '#c81e1e', fontSize: 12 }}>
          {publishError}
        </div>
      )}
      {exportError && (
        <div style={{ padding: '10px 16px', borderRadius: 10, background: 'rgba(200,30,30,0.08)', color: '#c81e1e', fontSize: 12 }}>
          {exportError}
        </div>
      )}

      {parsersLoading && (
        <div style={{ padding: 24, textAlign: 'center', color: '#8999b0', fontSize: 13 }}>Loading parsers…</div>
      )}
      {parsersError && (
        <div style={{ padding: '10px 16px', borderRadius: 10, background: 'rgba(200,30,30,0.08)', color: '#c81e1e', fontSize: 12 }}>
          Could not reach the backend to load parsers.
        </div>
      )}
      {!parsersLoading && !parsersError && parserList.length === 0 && (
        <div style={{ padding: 40, textAlign: 'center', color: '#8999b0', fontSize: 13 }}>
          No parsers yet. Create one, or import a signed bundle from another deployment.
        </div>
      )}
      {!parsersLoading && !parsersError && parserList.length > 0 && filteredList.length === 0 && (
        <div style={{ padding: 24, textAlign: 'center', color: '#8999b0', fontSize: 13 }}>No parsers match "{search}".</div>
      )}

      {selected ? (
        <>
          {/* Parser Meta */}
          <div style={{ display: 'flex', gap: 24 }}>
            <GlassCard style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 24, padding: '16px 24px' }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#5b6382', textTransform: 'uppercase', marginBottom: 4 }}>Format Type</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: '#0a0e27', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Terminal size={16} color="#0044A8" /> {selected.format_type || 'Unknown'}
                </div>
              </div>
              <div style={{ width: 1, height: 40, background: 'rgba(0,68,168,0.1)' }} />
              <div>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#5b6382', textTransform: 'uppercase', marginBottom: 4 }}>Vendor</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: '#0a0e27', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Server size={16} color="#0044A8" /> {selected.vendor ? anonymizedVendorLabel(selected.id) : 'Generic'}
                </div>
              </div>
              <div style={{ width: 1, height: 40, background: 'rgba(0,68,168,0.1)' }} />
              <div>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#5b6382', textTransform: 'uppercase', marginBottom: 4 }}>Coverage</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: selected.coverage_status === 'verified' ? '#057a55' : '#8a6d00', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <ShieldCheck size={16} /> {selected.coverage_status ? selected.coverage_status[0].toUpperCase() + selected.coverage_status.slice(1) : 'Fixture'}
                </div>
              </div>
              <div style={{ width: 1, height: 40, background: 'rgba(0,68,168,0.1)' }} />
              <div>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#5b6382', textTransform: 'uppercase', marginBottom: 4 }}>Status</div>
                <span style={{ padding: '4px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600, background: 'rgba(5,122,85,0.1)', color: '#057a55', display: 'inline-block', marginTop: 2 }}>
                  {selected.status?.toUpperCase() || 'PUBLISHED'}
                </span>
              </div>
            </GlassCard>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 24 }}>
            {/* Sample Log */}
            <GlassCard style={{ padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              <div style={{ padding: '16px 20px', borderBottom: '1px solid rgba(0,68,168,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(255,255,255,0.4)' }}>
                <div className="section-heading" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <FileText size={16} color="#0044A8" /> Raw Sample Log (Fixture)
                </div>
                <button style={{ background: 'transparent', border: 'none', color: '#0044A8', fontSize: 12, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <UploadCloud size={14} /> Paste New
                </button>
              </div>
              <textarea 
                value={sampleLog}
                onChange={e => setSampleLog(e.target.value)}
                style={{
                  width: '100%', height: 200, border: 'none', background: 'transparent', padding: 20,
                  fontSize: 13, fontFamily: 'monospace', color: '#334155', resize: 'vertical', outline: 'none'
                }}
              />
            </GlassCard>

            {/* YAML Editor */}
            <GlassCard style={{ padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              <div style={{ padding: '16px 20px', borderBottom: '1px solid rgba(0,68,168,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(255,255,255,0.4)' }}>
                <div className="section-heading" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Terminal size={16} color="#0044A8" /> Source Pack Configuration
                </div>
                <span style={{ fontSize: 11, fontWeight: 600, color: '#0044A8', background: 'rgba(0,68,168,0.1)', padding: '2px 8px', borderRadius: 10 }}>YAML</span>
              </div>
              <textarea 
                value={yamlDraft}
                onChange={e => setYamlDraft(e.target.value)}
                style={{
                  width: '100%', height: 400, border: 'none', background: 'rgba(0,15,46,0.03)', padding: 20,
                  fontSize: 13, fontFamily: 'monospace', color: '#0a0e27', resize: 'vertical', outline: 'none'
                }}
              />
            </GlassCard>
          </div>

          <GlassCard style={{ padding: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: testResult ? 24 : 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                {testResult ? (
                  testResult.status === 'success' ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#057a55', fontWeight: 600, fontSize: 14 }}>
                      <CheckCircle2 size={20} /> Fixture test passed ({testResult.mapping_method})
                    </div>
                  ) : testResult.status === 'warning' ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#d97706', fontWeight: 600, fontSize: 14 }}>
                      <AlertTriangle size={20} /> Passed with missing required fields: {testResult.missing_required_fields?.join(', ')}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#c81e1e', fontWeight: 600, fontSize: 14 }}>
                      <AlertTriangle size={20} /> Failed: {testResult.error}
                    </div>
                  )
                ) : (
                  <span style={{ color: '#8999b0', fontSize: 14, fontWeight: 500 }}>Run a test to validate mapping rules and preview output.</span>
                )}
              </div>
              <button 
                onClick={runTest}
                disabled={testing}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '10px 24px', borderRadius: 10,
                  background: '#0044A8', border: 'none',
                  color: '#fff', fontWeight: 600, fontSize: 14, cursor: 'pointer', boxShadow: '0 4px 12px rgba(0,68,168,0.2)'
                }}
              >
                <Play size={16} /> {testing ? 'Testing...' : 'Run Parser Test'}
              </button>
            </div>

            {testResult?.normalized_ecs && (
              <div style={{ background: 'rgba(255,255,255,0.7)', borderRadius: 12, padding: 20, border: '1px solid rgba(0,68,168,0.1)' }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#5b6382', textTransform: 'uppercase', marginBottom: 12 }}>Normalized Output (JSON)</div>
                <pre style={{ fontSize: 12, fontFamily: 'monospace', color: '#0a0e27', whiteSpace: 'pre-wrap', maxHeight: 300, overflowY: 'auto' }}>
                  {JSON.stringify(testResult.normalized_ecs, null, 2)}
                </pre>
              </div>
            )}
          </GlassCard>
        </>
      ) : (
        <GlassCard style={{ padding: 64, textAlign: 'center' }}>
          <FileText size={48} color="#0044A8" style={{ opacity: 0.3, margin: '0 auto 16px' }} />
          <h3 className="section-heading" style={{ marginBottom: 8 }}>No Parsers Found</h3>
          <p style={{ color: '#5b6382' }}>Upload or define a new source pack to get started.</p>
        </GlassCard>
      )}

      {showCreate && (
        <CreateParserModal
          onClose={() => setShowCreate(false)}
          onCreated={(id: string) => { setShowCreate(false); setSearch(''); setSelectedId(id); qc.invalidateQueries({ queryKey: ['parsers'] }) }}
        />
      )}
      {showImport && (
        <ImportParserModal
          onClose={() => setShowImport(false)}
          onImported={(id: string) => { setShowImport(false); setSearch(''); setSelectedId(id); qc.invalidateQueries({ queryKey: ['parsers'] }) }}
        />
      )}
    </div>
  )
}

function CreateParserModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const [id, setId] = useState('')
  const [name, setName] = useState('')
  const [formatType, setFormatType] = useState('KeyValue')
  const [configYaml, setConfigYaml] = useState('field_mappings: []\nstatic:\n  event_data:\n    category: unknown\n')
  const [sampleLog, setSampleLog] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const submit = () => {
    if (!id.trim() || !name.trim()) {
      setError('Parser ID and name are required.')
      return
    }
    setCreating(true)
    setError(null)
    api.createParser({ id: id.trim(), name: name.trim(), format_type: formatType, config_yaml: configYaml, sample_log: sampleLog || undefined })
      .then((p: any) => onCreated(p.id))
      .catch((e: any) => setError(e?.response?.data?.detail || e?.message || 'Could not create this parser.'))
      .finally(() => setCreating(false))
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,15,46,0.4)', backdropFilter: 'blur(8px)' }}>
      <div style={{ width: '90%', maxWidth: 520, background: '#fff', borderRadius: 16, padding: 28, position: 'relative', boxShadow: '0 16px 48px rgba(0,15,92,0.2)' }}>
        <button onClick={onClose} style={{ position: 'absolute', top: 16, right: 16, background: 'none', border: 'none', cursor: 'pointer' }}><X size={18} color="#8999b0" /></button>
        <h2 style={{ fontSize: 18, fontWeight: 800, color: '#0a0e27', marginBottom: 20 }}>Create Parser</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <input className="glass-input" value={id} onChange={e => setId(e.target.value)} placeholder="Parser ID (e.g. syslog_myvendor)" />
          <input className="glass-input" value={name} onChange={e => setName(e.target.value)} placeholder="Display name" />
          <select className="glass-input" value={formatType} onChange={e => setFormatType(e.target.value)}>
            <option value="KeyValue">KeyValue</option>
            <option value="JSON">JSON</option>
            <option value="CSV">CSV</option>
            <option value="Syslog">Syslog</option>
            <option value="XML">XML</option>
            <option value="CEF">CEF</option>
          </select>
          <textarea className="glass-input" value={configYaml} onChange={e => setConfigYaml(e.target.value)} placeholder="field_mappings YAML" style={{ height: 100, fontFamily: 'monospace', fontSize: 12 }} />
          <textarea className="glass-input" value={sampleLog} onChange={e => setSampleLog(e.target.value)} placeholder="Sample raw log (used for the fixture test before publish)" style={{ height: 60, fontFamily: 'monospace', fontSize: 12 }} />
          {error && <div style={{ color: '#c81e1e', fontSize: 12 }}>{error}</div>}
          <button onClick={submit} disabled={creating} className="btn-primary" style={{ justifyContent: 'center', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Plus size={14} /> {creating ? 'Creating…' : 'Create Parser'}
          </button>
        </div>
      </div>
    </div>
  )
}

function ImportParserModal({ onClose, onImported }: { onClose: () => void; onImported: (id: string) => void }) {
  const [bundleText, setBundleText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<any>(null)
  const [importing, setImporting] = useState(false)

  const onFile = (file: File) => {
    file.text().then(setBundleText).catch(() => setError('Could not read that file.'))
  }

  const submit = () => {
    let parsed: any
    try {
      parsed = JSON.parse(bundleText)
    } catch {
      setError('Not valid JSON -- paste the exact signed bundle downloaded from Export.')
      return
    }
    setImporting(true)
    setError(null)
    setResult(null)
    api.importParser(parsed)
      .then((res: any) => { setResult(res); onImported(res.parser_id) })
      .catch((e: any) => setError(e?.response?.data?.detail?.message || e?.response?.data?.detail || e?.message || 'Import failed -- signature verification or fixture test did not pass.'))
      .finally(() => setImporting(false))
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,15,46,0.4)', backdropFilter: 'blur(8px)' }}>
      <div style={{ width: '90%', maxWidth: 560, background: '#fff', borderRadius: 16, padding: 28, position: 'relative', boxShadow: '0 16px 48px rgba(0,15,92,0.2)' }}>
        <button onClick={onClose} style={{ position: 'absolute', top: 16, right: 16, background: 'none', border: 'none', cursor: 'pointer' }}><X size={18} color="#8999b0" /></button>
        <h2 style={{ fontSize: 18, fontWeight: 800, color: '#0a0e27', marginBottom: 8 }}>Import Signed Parser Bundle</h2>
        <p style={{ fontSize: 12, color: '#8999b0', marginBottom: 16 }}>
          A real Ed25519 signature check runs first (a tampered or unsigned bundle is rejected outright), then a real sandboxed fixture test before it's saved as a draft -- never a bypass of the normal review gate.
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderRadius: 10, border: '1px dashed rgba(0,68,168,0.3)', cursor: 'pointer', fontSize: 13, color: '#0044A8', fontWeight: 600 }}>
            <Upload size={14} /> Choose bundle .json file
            <input type="file" accept=".json,application/json" style={{ display: 'none' }} onChange={e => e.target.files?.[0] && onFile(e.target.files[0])} />
          </label>
          <textarea className="glass-input" value={bundleText} onChange={e => setBundleText(e.target.value)} placeholder='Or paste the bundle JSON here: {"bundle": {...}, "signature": "...", "public_key": "..."}' style={{ height: 140, fontFamily: 'monospace', fontSize: 11 }} />
          {error && <div style={{ color: '#c81e1e', fontSize: 12 }}>{error}</div>}
          {result && <div style={{ color: '#057a55', fontSize: 12 }}>Imported as draft: {result.parser_id}</div>}
          <button onClick={submit} disabled={importing || !bundleText.trim()} className="btn-primary" style={{ justifyContent: 'center', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Upload size={14} /> {importing ? 'Verifying & importing…' : 'Import'}
          </button>
        </div>
      </div>
    </div>
  )
}
