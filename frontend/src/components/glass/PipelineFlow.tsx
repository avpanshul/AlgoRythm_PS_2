import { useState, useEffect } from 'react'

interface Stage {
  id: string
  label: string
  color: string
  status?: 'healthy' | 'warning' | 'error' | 'inactive'
  metric?: string
  latency?: string
}

interface PipelineFlowProps {
  stages?: Stage[]
  compact?: boolean
  onNodeClick?: (stage: Stage) => void
}

const DEFAULT_STAGES: Stage[] = [
  { id: 'source', label: 'Source', color: '#0044A8', status: 'healthy', metric: '45k EPS', latency: '2ms' },
  { id: 'ingest', label: 'Ingestion', color: '#0066DD', status: 'healthy', metric: '45k EPS', latency: '5ms' },
  { id: 'parse', label: 'Parsing', color: '#0088FF', status: 'healthy', metric: '98% parsed', latency: '12ms' },
  { id: 'normalize', label: 'Normalization', color: '#00A8E8', status: 'warning', metric: '92% mapped', latency: '8ms' },
  { id: 'privacy', label: 'Privacy', color: '#057a55', status: 'healthy', metric: '100% redacted', latency: '1ms' },
  { id: 'integrity', label: 'Integrity', color: '#0044A8', status: 'healthy', metric: 'Hashes valid', latency: '4ms' },
  { id: 'storage', label: 'Storage', color: '#0029BB', status: 'healthy', metric: '4.2TB', latency: '15ms' },
]

export function PipelineFlow({ stages = DEFAULT_STAGES, compact = false, onNodeClick }: PipelineFlowProps) {
  const [hoveredStage, setHoveredStage] = useState<string | null>(null)
  
  // Create an array of particles for animation
  const [particles, setParticles] = useState<Array<{ id: number, segment: number, offset: number, speed: number }>>([])

  useEffect(() => {
    // Generate particles
    const newParticles = Array.from({ length: 30 }).map((_, i) => ({
      id: i,
      segment: Math.floor(Math.random() * (stages.length - 1)),
      offset: Math.random(),
      speed: 0.002 + Math.random() * 0.003
    }))
    setParticles(newParticles)

    let animationFrame: number
    let lastTime = performance.now()
    
    const animate = (time: number) => {
      const dt = time - lastTime
      lastTime = time
      
      setParticles(prev => prev.map(p => {
        let newOffset = p.offset + (p.speed * dt * 0.1)
        let newSegment = p.segment
        if (newOffset >= 1) {
          newOffset = 0
          newSegment = (newSegment + 1) % (stages.length - 1)
        }
        return { ...p, offset: newOffset, segment: newSegment }
      }))
      animationFrame = requestAnimationFrame(animate)
    }
    
    animationFrame = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(animationFrame)
  }, [stages.length])

  // The node block is a circle (36px) + 8px margin + a label line below it,
  // so its visual center is above the container's flex-centered midpoint --
  // that mismatch is what put the dashed connector line below the circles
  // instead of through them. Fixed by anchoring nodes to a flex-start with
  // an explicit top offset, and drawing the line at that same fixed pixel
  // Y (the real circle center), not a guessed "50%".
  const topOffset = compact ? 16 : 28
  const circleCenterY = topOffset + 18

  return (
    <div style={{ position: 'relative', width: '100%', height: compact ? 100 : 160, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', padding: `${topOffset}px 20px 0` }}>
      {/* SVG layer for connections and particles */}
      <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 0 }}>
        {stages.map((stage, i) => {
          if (i === stages.length - 1) return null
          const nextStage = stages[i + 1]
          const isWarning = stage.status === 'warning' || nextStage.status === 'warning'
          const isError = stage.status === 'error' || nextStage.status === 'error'

          let strokeColor = 'rgba(0,136,255,0.3)'
          if (isError) strokeColor = 'rgba(239,68,68,0.4)'
          else if (isWarning) strokeColor = 'rgba(245,158,11,0.4)'

          // Calculate positions
          const x1 = `calc(${(i / (stages.length - 1)) * 100}% + 20px)`
          const x2 = `calc(${((i + 1) / (stages.length - 1)) * 100}% - 20px)`

          return (
            <g key={`connection-${i}`}>
              <line
                x1={x1} y1={circleCenterY} x2={x2} y2={circleCenterY}
                stroke={strokeColor} strokeWidth="2" strokeDasharray="4 4"
              />
              {/* Particles for this segment */}
              {particles.filter(p => p.segment === i).map(p => {
                return (
                  <circle
                    key={p.id}
                    cx={`calc(${x1} + (${x2} - ${x1}) * ${p.offset})`}
                    cy={circleCenterY}
                    r="2.5"
                    fill={stage.color}
                    style={{
                      filter: `drop-shadow(0 0 4px ${stage.color}) drop-shadow(0 0 8px ${stage.color})`,
                      opacity: Math.sin(p.offset * Math.PI) * 0.8 + 0.2 // fade in/out at edges
                    }}
                  />
                )
              })}
            </g>
          )
        })}
      </svg>

      {/* HTML layer for interactive nodes */}
      {stages.map((stage, i) => {
        const isHovered = hoveredStage === stage.id
        const isPulse = stage.status !== 'inactive'
        
        let ringColor = stage.color
        if (stage.status === 'error') ringColor = '#ef4444'
        if (stage.status === 'warning') ringColor = '#f59e0b'
        
        return (
          <div 
            key={stage.id}
            style={{ 
              position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
              cursor: onNodeClick ? 'pointer' : 'default',
              transform: isHovered ? 'scale(1.1)' : 'scale(1)',
              transition: 'transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)'
            }}
            onMouseEnter={() => setHoveredStage(stage.id)}
            onMouseLeave={() => setHoveredStage(null)}
            onClick={() => onNodeClick?.(stage)}
          >
            {/* Circle + pulse ring share this 36px box so "centered on the
                node" means centered on the actual circle, not on the taller
                block that also includes the label below it -- that mismatch
                is what put the pulse ring visibly off-center from the circle. */}
            <div style={{ position: 'relative', width: 36, height: 36, marginBottom: 8 }}>
              {isPulse && (
                <div style={{
                  position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
                  width: 48, height: 48, borderRadius: '50%',
                  border: `1px solid ${ringColor}`,
                  opacity: 0,
                  animation: 'pulse-ring 2s cubic-bezier(0.215, 0.61, 0.355, 1) infinite',
                }} />
              )}

              {/* Glass Node */}
              <div style={{
                width: 36, height: 36, borderRadius: '50%',
                background: `linear-gradient(135deg, ${stage.color}20, ${stage.color}40)`,
                border: `1.5px solid ${ringColor}80`,
                backdropFilter: 'blur(8px)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: `0 4px 12px ${ringColor}30, inset 0 2px 4px rgba(255,255,255,0.4)`,
              }}>
                <div style={{
                  width: 12, height: 12, borderRadius: '50%',
                  background: `linear-gradient(135deg, ${stage.color}, ${ringColor})`,
                  boxShadow: `0 0 10px ${ringColor}80`
                }} />
              </div>
            </div>

            {/* Label */}
            <div style={{
              fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em',
              color: isHovered ? stage.color : '#5b6382',
              transition: 'color 0.2s'
            }}>
              {stage.label}
            </div>

            {/* Tooltip */}
            <div style={{
              position: 'absolute', top: -70,
              opacity: isHovered ? 1 : 0, transform: isHovered ? 'translateY(0) scale(1)' : 'translateY(10px) scale(0.95)',
              pointerEvents: isHovered ? 'auto' : 'none',
              background: 'rgba(255,255,255,0.95)', backdropFilter: 'blur(12px)',
              padding: '8px 12px', borderRadius: 8,
              boxShadow: '0 8px 24px rgba(0,68,168,0.15)',
              border: '1px solid rgba(0,68,168,0.1)',
              whiteSpace: 'nowrap', zIndex: 10,
              transition: 'all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)'
            }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#0a0e27', marginBottom: 2 }}>{stage.label}</div>
              <div style={{ fontSize: 10, color: '#5b6382' }}>Status: <span style={{ color: stage.status === 'healthy' ? '#057a55' : stage.status === 'warning' ? '#d97706' : '#ef4444', fontWeight: 600 }}>{stage.status?.toUpperCase()}</span></div>
              {stage.metric && <div style={{ fontSize: 10, color: '#5b6382' }}>Metric: {stage.metric}</div>}
              {stage.latency && <div style={{ fontSize: 10, color: '#5b6382' }}>Latency: {stage.latency}</div>}
              {onNodeClick && <div style={{ fontSize: 9, color: stage.color, marginTop: 4, fontWeight: 600 }}>Click to manage &rarr;</div>}
            </div>
          </div>
        )
      })}
      <style>{`
        @keyframes pulse-ring {
          0% { transform: translate(-50%, -50%) scale(0.8); opacity: 0.8; }
          100% { transform: translate(-50%, -50%) scale(1.5); opacity: 0; }
        }
      `}</style>
    </div>
  )
}
