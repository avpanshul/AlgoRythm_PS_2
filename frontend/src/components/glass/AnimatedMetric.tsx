import { useEffect, useRef, useState } from 'react'

interface AnimatedMetricProps {
  value: number | string | null | undefined
  label: string
  suffix?: string
  prefix?: string
  decimals?: number
  icon?: React.ReactNode
  trend?: number
  trendLabel?: string
  color?: string
  loading?: boolean
  emptyState?: string
}

function useCountUp(target: number, duration = 1200) {
  const [count, setCount] = useState(0)
  const rafRef = useRef<number | null>(null)
  const startRef = useRef<number | null>(null)

  useEffect(() => {
    if (target === 0) { setCount(0); return }
    startRef.current = null
    const animate = (ts: number) => {
      if (startRef.current === null) startRef.current = ts
      const elapsed = ts - startRef.current
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setCount(Math.round(eased * target))
      if (progress < 1) rafRef.current = requestAnimationFrame(animate)
    }
    rafRef.current = requestAnimationFrame(animate)
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }
  }, [target, duration])

  return count
}

export function AnimatedMetric({
  value, label, suffix = '', prefix = '', decimals = 0,
  icon, trend, trendLabel, color = '#0044A8', loading = false, emptyState,
}: AnimatedMetricProps) {
  const numericValue = typeof value === 'number' ? value : parseFloat(String(value)) || 0
  const animated = useCountUp(loading ? 0 : numericValue)
  const display = decimals > 0
    ? (loading ? 0 : numericValue).toFixed(decimals)
    : animated.toLocaleString()

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#8999b0' }}>
        {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        {icon && (
          <div style={{ color, marginBottom: -2 }}>{icon}</div>
        )}
        {loading ? (
          <div style={{
            height: 36, width: 120, borderRadius: 8,
            background: 'linear-gradient(90deg, rgba(0,68,168,0.06) 25%, rgba(0,68,168,0.12) 50%, rgba(0,68,168,0.06) 75%)',
            backgroundSize: '200% 100%',
            animation: 'shimmer 1.5s ease-in-out infinite',
          }} />
        ) : value == null ? (
          <span style={{ fontSize: 32, fontWeight: 800, color: '#c0cde3' }}>
            {emptyState || '—'}
          </span>
        ) : (
          <>
            {prefix && <span style={{ fontSize: 18, fontWeight: 700, color }}>{prefix}</span>}
            <span style={{
              fontSize: 32, fontWeight: 800, letterSpacing: '-0.03em',
              background: `linear-gradient(135deg, ${color}, ${color}cc)`,
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            }}>
              {display}
            </span>
            {suffix && <span style={{ fontSize: 16, fontWeight: 600, color: `${color}99` }}>{suffix}</span>}
          </>
        )}
      </div>
      {trend !== undefined && !loading && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, fontWeight: 600 }}>
          <span style={{ color: trend >= 0 ? '#057a55' : '#c81e1e' }}>
            {trend >= 0 ? '↑' : '↓'} {Math.abs(trend)}%
          </span>
          {trendLabel && <span style={{ color: '#8999b0', fontWeight: 400 }}>{trendLabel}</span>}
        </div>
      )}
    </div>
  )
}
