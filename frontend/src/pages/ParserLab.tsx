import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from '../api/client'
import { useState } from 'react'
import { GlassCard } from '../components/glass/GlassCard'
import { Upload, Cpu, Map, Settings, FlaskConical, CheckSquare, Send, Check, X, Play, FileText, Plus } from 'lucide-react'
import { anonymizedVendorLabel } from '../utils/anonymize'

const WIZARD_STEPS = [
  { id: 'upload', label: 'Upload', icon: Upload },
  { id: 'detect', label: 'Detect', icon: Cpu },
  { id: 'map', label: 'Map', icon: Map },
  { id: 'config', label: 'Configure', icon: Settings },
  { id: 'test', label: 'Test', icon: FlaskConical },
  { id: 'validate', label: 'Validate', icon: CheckSquare },
  { id: 'publish', label: 'Publish', icon: Send },
]

function StepIndicator({ currentStep }: { currentStep: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', overflowX: 'auto', paddingBottom: 4 }}>
      {WIZARD_STEPS.map((step, i) => {
        const Icon = step.icon
        const done = i < currentStep
        const active = i === currentStep
        return (
          <div key={step.id} style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, minWidth: 70 }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, background: done ? '#0044A8' : active ? 'rgba(0,68,168,0.1)' : 'rgba(0,68,168,0.04)', border: `2px solid ${done ? '#0044A8' : active ? '#0044A8' : 'rgba(0,68,168,0.15)'}`, display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all 0.3s ease', boxShadow: active ? '0 4px 12px rgba(0,68,168,0.25)' : 'none' }}>
                {done ? <Check size={16} color="#fff" /> : <Icon size={16} color={active ? '#0044A8' : '#c0cde3'} />}
              </div>
              <div style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', textAlign: 'center', color: active ? '#0044A8' : done ? '#057a55' : '#8999b0' }}>{step.label}</div>
            </div>
            {i < WIZARD_STEPS.length - 1 && <div style={{ width: 32, height: 2, borderRadius: 1, background: done ? '#0044A8' : 'rgba(0,68,168,0.12)', marginBottom: 20, flexShrink: 0, transition: 'background 0.5s ease' }} />}
          </div>
        )
      })}
    </div>
  )
}

function TestModal({ parserId, onClose }: { parserId: string; onClose: () => void }) {
  const [input, setInput] = useState('')
  const [result, setResult] = useState<any>(null)
  const mutation = useMutation({ mutationFn: () => api.testParser(parserId, { raw_log: input }), onSuccess: setResult })
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,15,46,0.4)', backdropFilter: 'blur(8px)' }}>
      <GlassCard variant="ultra" size="none" style={{ width: '90%', maxWidth: 700, padding: 28, position: 'relative' }}>
        <button onClick={onClose} style={{ position: 'absolute', top: 16, right: 16, background: 'none', border: 'none', cursor: 'pointer' }}><X size={18} color="#8999b0" /></button>
        <div style={{ fontSize: 16, fontWeight: 800, color: '#0a0e27', marginBottom: 4 }}>Test Parser</div>
        <div style={{ fontSize: 12, color: '#8999b0', marginBottom: 20, fontFamily: 'monospace' }}>{parserId}</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <textarea value={input} onChange={e => setInput(e.target.value)} rows={5} placeholder="Paste a raw log line here"
            style={{ width: '100%', padding: '10px 14px', borderRadius: 12, border: '1px solid rgba(0,68,168,0.15)', background: 'rgba(248,252,255,0.8)', fontFamily: 'monospace', fontSize: 12, color: '#0a0e27', resize: 'vertical', outline: 'none' }} />
          <button onClick={() => mutation.mutate()} disabled={!input || mutation.isPending} style={{ padding: '10px 20px', borderRadius: 10, background: '#0044A8', color: '#fff', border: 'none', fontSize: 13, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, alignSelf: 'flex-start', opacity: !input || mutation.isPending ? 0.6 : 1 }}>
            <Play size={14} /> {mutation.isPending ? 'Running...' : 'Run Parser'}
          </button>
          {result && (<GlassCard variant="frosted" size="none" style={{ padding: 14 }}><pre style={{ fontFamily: 'monospace', fontSize: 11, color: '#334155', margin: 0, whiteSpace: 'pre-wrap', maxHeight: 240, overflowY: 'auto' }}>{JSON.stringify(result, null, 2)}</pre></GlassCard>)}
          {mutation.isError && <div style={{ fontSize: 12, color: '#c81e1e', padding: '10px 14px', borderRadius: 10, background: 'rgba(200,30,30,0.08)' }}>Parser test failed.</div>}
        </div>
      </GlassCard>
    </div>
  )
}

export default function ParserLab() {
  const { data: parsers, isLoading } = useQuery({ queryKey: ['parsers'], queryFn: () => api.getParsers() })
  const [wizardStep, setWizardStep] = useState(0)
  const [testingParser, setTestingParser] = useState<string | null>(null)
  const parserList: any[] = Array.isArray(parsers) ? parsers : []

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 'clamp(36px, 3.6vw, 48px)', fontWeight: 800, color: '#0a0e27', letterSpacing: '-0.03em' }}>Parser Lab</h1>
          <p style={{ fontSize: 12, color: '#8999b0', marginTop: 3 }}>{parserList.length > 0 ? `${parserList.length} parsers deployed` : 'Develop, test and publish log parsers'}</p>
        </div>
        <GlassCard variant="base" size="none" style={{ padding: '8px 16px', background: 'linear-gradient(135deg, #0044A8, #0066DD)', border: '1px solid rgba(0,68,168,0.4)', display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
          <Plus size={14} color="#fff" /><span style={{ fontSize: 12, fontWeight: 600, color: '#fff' }}>New Parser</span>
        </GlassCard>
      </div>
      <GlassCard variant="elevated" size="none" style={{ padding: 'clamp(18px, 2vw, 28px)' }}>
        <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#8999b0', marginBottom: 20 }}>Parser Workflow</div>
        <StepIndicator currentStep={wizardStep} />
        <div style={{ marginTop: 20, display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          {wizardStep > 0 && <button onClick={() => setWizardStep(s => s - 1)} style={{ padding: '8px 16px', borderRadius: 10, background: 'rgba(0,68,168,0.06)', border: '1px solid rgba(0,68,168,0.15)', color: '#0044A8', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>← Back</button>}
          {wizardStep < WIZARD_STEPS.length - 1 ? (
            <button onClick={() => setWizardStep(s => s + 1)} style={{ padding: '8px 16px', borderRadius: 10, background: '#0044A8', border: 'none', color: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>Next →</button>
          ) : (
            <button onClick={() => setWizardStep(0)} style={{ padding: '8px 16px', borderRadius: 10, background: '#057a55', border: 'none', color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}><Send size={13} /> Publish Parser</button>
          )}
        </div>
      </GlassCard>
      <div>
        <div style={{ fontSize: 14, fontWeight: 700, color: '#0a0e27', marginBottom: 12 }}>Deployed Parsers</div>
        {isLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {Array.from({ length: 4 }).map((_, i) => <GlassCard key={i} variant="elevated" size="none" style={{ padding: '14px 18px', height: 68 }}><div style={{ height: 12, width: '40%', borderRadius: 6, background: 'rgba(0,68,168,0.08)' }} /></GlassCard>)}
          </div>
        ) : parserList.length === 0 ? (
          <GlassCard variant="elevated" size="lg" style={{ textAlign: 'center' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(0,68,168,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><FileText size={24} color="#0044A8" style={{ opacity: 0.35 }} /></div>
              <p style={{ fontSize: 13, color: '#8999b0', fontWeight: 500 }}>No parsers deployed yet</p>
              <p style={{ fontSize: 12, color: '#b0bace' }}>Use the workflow above to create and publish parsers</p>
            </div>
          </GlassCard>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {parserList.map((parser: any) => (
              <GlassCard key={parser.id} variant="elevated" size="none" hover style={{ padding: '14px 18px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{ width: 36, height: 36, borderRadius: 10, flexShrink: 0, background: 'linear-gradient(135deg, rgba(0,68,168,0.1), rgba(0,136,255,0.08))', border: '1px solid rgba(0,68,168,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><FileText size={16} color="#0044A8" /></div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#0a0e27', marginBottom: 2 }}>{parser.name || parser.id}</div>
                    <div style={{ fontSize: 11, color: '#8999b0' }}>{parser.vendor && <span>{anonymizedVendorLabel(parser.id)} · </span>}<span className="mono" style={{ fontSize: 10 }}>{parser.id}</span></div>
                  </div>
                  <button onClick={() => setTestingParser(parser.id)} style={{ padding: '5px 14px', borderRadius: 8, fontSize: 11, fontWeight: 600, background: '#0044A8', color: '#fff', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5 }}><Play size={10} /> Test</button>
                </div>
              </GlassCard>
            ))}
          </div>
        )}
      </div>
      {testingParser && <TestModal parserId={testingParser} onClose={() => setTestingParser(null)} />}
    </div>
  )
}
