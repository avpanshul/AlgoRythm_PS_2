import { useRef, useEffect, useState } from 'react'

type GlassVariant = 'base' | 'elevated' | 'deep' | 'ultra' | 'frosted' | 'thin'
type GlassSize = 'sm' | 'md' | 'lg' | 'none'

interface GlassCardProps {
  children: React.ReactNode
  variant?: GlassVariant
  size?: GlassSize
  className?: string
  style?: React.CSSProperties
  hover?: boolean
  glow?: boolean
  glowColor?: string
  magnetic?: boolean
  onClick?: () => void
  as?: 'div' | 'section' | 'article'
}

const variantStyles: Record<GlassVariant, React.CSSProperties> = {
  base: {
    background: 'rgba(255,255,255,0.72)',
    backdropFilter: 'blur(20px) saturate(1.6)',
    WebkitBackdropFilter: 'blur(20px) saturate(1.6)',
    border: '1px solid rgba(255,255,255,0.55)',
    boxShadow: '0 4px 24px rgba(0,68,168,0.07), 0 1px 0 rgba(255,255,255,0.8) inset',
  },
  elevated: {
    background: 'rgba(255,255,255,0.82)',
    backdropFilter: 'blur(32px) saturate(1.8)',
    WebkitBackdropFilter: 'blur(32px) saturate(1.8)',
    border: '1px solid rgba(255,255,255,0.7)',
    boxShadow: '0 8px 40px rgba(0,68,168,0.10), 0 2px 0 rgba(255,255,255,0.9) inset, 0 -1px 0 rgba(0,68,168,0.06) inset',
  },
  deep: {
    background: 'rgba(240,246,255,0.65)',
    backdropFilter: 'blur(40px) saturate(1.4)',
    WebkitBackdropFilter: 'blur(40px) saturate(1.4)',
    border: '1px solid rgba(0,68,168,0.12)',
    boxShadow: '0 12px 48px rgba(0,68,168,0.12), 0 2px 0 rgba(255,255,255,0.7) inset',
  },
  ultra: {
    background: 'rgba(255,255,255,0.92)',
    backdropFilter: 'blur(60px) saturate(2)',
    WebkitBackdropFilter: 'blur(60px) saturate(2)',
    border: '1.5px solid rgba(255,255,255,0.85)',
    boxShadow: '0 20px 60px rgba(0,68,168,0.14), 0 3px 0 rgba(255,255,255,1) inset, 0 -1px 0 rgba(0,68,168,0.08) inset',
  },
  frosted: {
    background: 'rgba(248,252,255,0.6)',
    backdropFilter: 'blur(24px) saturate(1.5) brightness(1.05)',
    WebkitBackdropFilter: 'blur(24px) saturate(1.5) brightness(1.05)',
    border: '1px solid rgba(255,255,255,0.5)',
    boxShadow: '0 6px 32px rgba(0,68,168,0.08), 0 1px 0 rgba(255,255,255,0.75) inset',
  },
  thin: {
    background: 'rgba(255,255,255,0.45)',
    backdropFilter: 'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
    border: '1px solid rgba(255,255,255,0.4)',
    boxShadow: '0 2px 16px rgba(0,68,168,0.05)',
  },
}

const sizeStyles: Record<GlassSize, React.CSSProperties> = {
  sm: { borderRadius: 12, padding: '12px 16px' },
  md: { borderRadius: 16, padding: '20px 24px' },
  lg: { borderRadius: 24, padding: '28px 32px' },
  none: { borderRadius: 16, padding: 0 },
}

export function GlassCard({
  children, variant = 'base', size = 'md', className = '',
  style = {}, hover = true, glow = false, glowColor = 'rgba(0,68,168,0.18)',
  magnetic = false, onClick, as: Tag = 'div',
}: GlassCardProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [isHovered, setIsHovered] = useState(false)
  const [mousePos, setMousePos] = useState({ x: 0.5, y: 0.5 })

  useEffect(() => {
    if (!magnetic || !ref.current) return
    const el = ref.current
    const handleMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect()
      setMousePos({
        x: (e.clientX - rect.left) / rect.width,
        y: (e.clientY - rect.top) / rect.height,
      })
    }
    el.addEventListener('mousemove', handleMove)
    return () => el.removeEventListener('mousemove', handleMove)
  }, [magnetic])

  const hoverStyle: React.CSSProperties = hover && isHovered ? {
    transform: magnetic
      ? `translateY(-3px) perspective(600px) rotateX(${(mousePos.y - 0.5) * -4}deg) rotateY(${(mousePos.x - 0.5) * 4}deg)`
      : 'translateY(-3px)',
    boxShadow: glow
      ? `0 16px 48px ${glowColor}, 0 4px 0 rgba(255,255,255,0.9) inset`
      : '0 16px 48px rgba(0,68,168,0.14), 0 4px 0 rgba(255,255,255,0.9) inset',
  } : {}

  // Dynamic gloss highlight based on mouse position
  const glossStyle: React.CSSProperties = isHovered && magnetic ? {
    backgroundImage: `radial-gradient(circle at ${mousePos.x * 100}% ${mousePos.y * 100}%, rgba(255,255,255,0.25) 0%, transparent 60%)`,
  } : {}

  return (
    <Tag
      ref={ref as any}
      className={className}
      onClick={onClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => { setIsHovered(false); setMousePos({ x: 0.5, y: 0.5 }) }}
      style={{
        position: 'relative',
        overflow: 'hidden',
        transition: 'transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease',
        cursor: onClick ? 'pointer' : 'default',
        ...variantStyles[variant],
        ...sizeStyles[size],
        ...style,
        ...hoverStyle,
      }}
    >
      {/* Top gloss highlight */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: '45%',
        background: 'linear-gradient(180deg, rgba(255,255,255,0.28) 0%, transparent 100%)',
        pointerEvents: 'none', borderRadius: 'inherit',
      }} />
      {/* Dynamic mouse gloss */}
      {isHovered && (
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          ...glossStyle, transition: 'all 0.1s ease',
        }} />
      )}
      {/* Edge refraction */}
      <div style={{
        position: 'absolute', inset: 0, borderRadius: 'inherit', pointerEvents: 'none',
        boxShadow: '0 0 0 1px rgba(255,255,255,0.4) inset',
      }} />
      {children}
    </Tag>
  )
}
