import React, { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import {
  Shield,
  ArrowRight,
  User,
  X,
  KeyRound,
  ArrowLeft,
  Lock,
  CheckCircle2
} from 'lucide-react'
import { api } from '../api/client'
import { setToken } from '../auth/authStore'

// Module-level (not defined inside AuthPanel): a component declared inside
// another component's body is a new function identity on every render, so
// React treats each keystroke's re-render as a brand-new component type and
// remounts the real <input> DOM node -- which drops focus after every single
// character typed. This was a real bug found live on the deployed signup
// form (typing "an" only kept "a", losing focus each time). Keeping it here
// at module scope gives it a stable identity across renders.
function InputField({ label, type, placeholder, value, onChange, onEnter }: { label: string, type: string, placeholder: string, value: string, onChange: (v: string) => void, onEnter?: () => void }) {
  return (
    <div>
      <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase' as const, color: 'rgba(255,255,255,0.85)', marginBottom: '0.4rem' }}>
        {label}
      </label>
      <input
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && onEnter?.()}
        style={{
          width: '100%', padding: '0.75rem 1rem', borderRadius: '0.75rem',
          background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)',
          color: '#fff', fontSize: '0.875rem', outline: 'none',
          transition: 'border-color 0.18s ease',
        }}
        onFocus={e => { (e.target as HTMLInputElement).style.borderColor = 'rgba(0,68,168,0.7)' }}
        onBlur={e => { (e.target as HTMLInputElement).style.borderColor = 'rgba(255,255,255,0.12)' }}
      />
    </div>
  )
}

// ─── AUTH PANEL (right-side sliding glass panel) ───────────────────────────
// The one real login/signup surface for this app -- RequireAuth sends
// anyone not logged in back here (not to a separate page) when they hit a
// protected route.
function AuthPanel({ navigate, redirectTo }: { navigate: (path: string) => void; redirectTo: string }) {
  const [mode, setMode] = useState<'login' | 'signup'>('login')

  const [loginEmail, setLoginEmail] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginError, setLoginError] = useState<string | null>(null)
  const [loginLoading, setLoginLoading] = useState(false)

  const [signupName, setSignupName] = useState('')
  const [signupEmail, setSignupEmail] = useState('')
  const [signupPassword, setSignupPassword] = useState('')
  const [signupConfirm, setSignupConfirm] = useState('')
  const [signupError, setSignupError] = useState<string | null>(null)
  const [signupLoading, setSignupLoading] = useState(false)

  const submitLogin = () => {
    if (!loginEmail || !loginPassword) {
      setLoginError('Email and password are required.')
      return
    }
    setLoginLoading(true)
    setLoginError(null)
    api.login(loginEmail, loginPassword)
      .then((res: any) => {
        setToken(res.access_token)
        navigate(redirectTo)
      })
      .catch((e: any) => setLoginError(e?.response?.data?.detail || e?.message || 'Login failed.'))
      .finally(() => setLoginLoading(false))
  }

  const submitSignup = () => {
    if (!signupName || !signupEmail || !signupPassword) {
      setSignupError('Name, email, and password are required.')
      return
    }
    if (signupPassword.length < 8) {
      setSignupError('Password must be at least 8 characters.')
      return
    }
    if (signupPassword !== signupConfirm) {
      setSignupError('Passwords do not match.')
      return
    }
    setSignupLoading(true)
    setSignupError(null)
    api.signup(signupName, signupEmail, signupPassword)
      .then((res: any) => {
        setToken(res.access_token)
        navigate(redirectTo)
      })
      .catch((e: any) => setSignupError(e?.response?.data?.detail || e?.message || 'Sign up failed.'))
      .finally(() => setSignupLoading(false))
  }

  const btnBase: React.CSSProperties = {
    width: '100%', padding: '1rem 1.25rem', borderRadius: '0.875rem',
    cursor: 'pointer', fontWeight: 700, letterSpacing: '0.08em',
    fontSize: 'clamp(0.8rem, 1vw, 0.95rem)',
    textTransform: 'uppercase' as const,
    transition: 'all 0.2s cubic-bezier(0.34,1.56,0.64,1)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', animation: 'fadeIn 0.35s ease forwards' }}>

      {/* Title */}
      <div style={{ textAlign: 'center' }}>
        <h2 style={{
          fontSize: 'clamp(2.6rem, 5vw, 3.8rem)', fontWeight: 900,
          letterSpacing: '0.12em', color: '#ffffff', lineHeight: 1,
          fontFamily: 'Georgia, "Times New Roman", serif',
          textShadow: '0 2px 24px rgba(0,68,168,0.4)',
        }}>
          {mode === 'login' ? 'LOGIN' : 'SIGN UP'}
        </h2>

        {/* Toggle link */}
        <p style={{ marginTop: '0.6rem', fontSize: '0.875rem', color: 'rgba(255,255,255,0.85)', fontWeight: 400 }}>
          {mode === 'login' ? (
            <>Don't have an account yet?{' '}
              <button onClick={() => setMode('signup')} style={{ background: 'none', border: 'none', color: '#60a5fa', fontWeight: 600, cursor: 'pointer', fontSize: 'inherit', padding: 0 }}>
                Sign Up
              </button>
            </>
          ) : (
            <>Already have an account?{' '}
              <button onClick={() => setMode('login')} style={{ background: 'none', border: 'none', color: '#60a5fa', fontWeight: 600, cursor: 'pointer', fontSize: 'inherit', padding: 0 }}>
                Log In
              </button>
            </>
          )}
        </p>
      </div>

      {mode === 'login' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

          <InputField label="Work Email / Organization Email" type="email" placeholder="analyst@soc-domain.com" value={loginEmail} onChange={setLoginEmail} onEnter={submitLogin} />
          <InputField label="Password" type="password" placeholder="••••••••••••" value={loginPassword} onChange={setLoginPassword} onEnter={submitLogin} />

          {loginError && <div style={{ fontSize: '0.8rem', color: '#fca5a5' }}>{loginError}</div>}

          <button
            onClick={submitLogin}
            disabled={loginLoading}
            style={{
              ...btnBase,
              marginTop: '0.5rem',
              background: 'linear-gradient(135deg, #0044A8 0%, #0066DD 100%)',
              border: '1px solid rgba(0,68,168,0.7)',
              color: '#ffffff',
              opacity: loginLoading ? 0.7 : 1,
              boxShadow: '0 4px 20px rgba(0,68,168,0.45), inset 0 1px 0 rgba(255,255,255,0.12)',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-2px)'; (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 8px 28px rgba(0,68,168,0.6)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(0)'; (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 4px 20px rgba(0,68,168,0.45)' }}
          >
            <Shield style={{ width: '1rem', height: '1rem', marginRight: '0.5rem' }} />
            {loginLoading ? 'Signing In…' : 'Sign In to Sanket'}
            <ArrowRight style={{ width: '1rem', height: '1rem', marginLeft: '0.5rem' }} />
          </button>

          {/* Demo login: fills in a real, working, but deliberately
              LOW-PRIVILEGE account -- never the real admin. VITE_* env vars
              are baked into the public JS bundle at build time (visible to
              anyone who views page source), so putting a real admin
              password there would hand out full admin access to every
              visitor. A dedicated "analyst"-role demo account (created via
              the same self-serve /auth/signup every real user goes through)
              costs nothing if its password leaks -- that's the whole point
              of it existing. Falls back to the local dev seed
              (admin@ulpf.local / local-demo-admin-pw, from
              backend/scripts/run_local_demo.py) when the env vars are
              unset, so `npm run dev` still works out of the box. */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', margin: '0.25rem 0' }}>
            <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.12)' }} />
            <span style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.5)', letterSpacing: '0.05em' }}>OR</span>
            <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.12)' }} />
          </div>
          <button
            type="button"
            onClick={() => {
              setLoginEmail(import.meta.env.VITE_DEMO_EMAIL || 'admin@ulpf.local')
              setLoginPassword(import.meta.env.VITE_DEMO_PASSWORD || 'local-demo-admin-pw')
            }}
            style={{
              width: '100%', padding: '0.7rem 1rem', borderRadius: '0.75rem',
              background: 'rgba(255,255,255,0.06)', border: '1px dashed rgba(255,255,255,0.25)',
              color: 'rgba(255,255,255,0.85)', fontSize: '0.8rem', fontWeight: 600,
              cursor: 'pointer', transition: 'background 0.18s ease',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.1)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.06)' }}
          >
            Fill Demo Credentials
          </button>
        </div>
      ) : (
        // Sign Up form
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <InputField label="Full Name" type="text" placeholder="Alex Mercer" value={signupName} onChange={setSignupName} onEnter={submitSignup} />
          <InputField label="Work Email" type="email" placeholder="alex@soc-domain.com" value={signupEmail} onChange={setSignupEmail} onEnter={submitSignup} />
          <InputField label="Password (min. 8 characters)" type="password" placeholder="••••••••••••" value={signupPassword} onChange={setSignupPassword} onEnter={submitSignup} />
          <InputField label="Confirm Password" type="password" placeholder="••••••••••••" value={signupConfirm} onChange={setSignupConfirm} onEnter={submitSignup} />

          <p style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.6)', margin: 0 }}>
            New accounts start with Analyst access. An administrator can grant elevated roles afterward from Administration → Users.
          </p>

          {signupError && <div style={{ fontSize: '0.8rem', color: '#fca5a5' }}>{signupError}</div>}

          <button
            onClick={submitSignup}
            disabled={signupLoading}
            style={{
              ...btnBase,
              marginTop: '0.25rem',
              background: 'linear-gradient(135deg, #0044A8 0%, #0066DD 100%)',
              border: '1px solid rgba(0,68,168,0.7)',
              color: '#ffffff',
              opacity: signupLoading ? 0.7 : 1,
              boxShadow: '0 4px 20px rgba(0,68,168,0.4)',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-2px)'; (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 8px 28px rgba(0,68,168,0.6)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(0)'; (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 4px 20px rgba(0,68,168,0.4)' }}
          >
            {signupLoading ? 'Creating Account…' : 'Create Account'}
          </button>
        </div>
      )}
    </div>
  )
}


export default function LandingPage() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const navigate = useNavigate()
  const location = useLocation()
  const redirectState = location.state as { openAuth?: boolean; from?: string } | null
  const redirectTo = redirectState?.from || '/dashboard'
  const [isContactModalOpen, setIsContactModalOpen] = useState(false)
  const [isSignInActive, setIsSignInActive] = useState(!!redirectState?.openAuth)

  // Animation state refs for seamless 60fps canvas convergence
  const zoomProgressRef = useRef(0)

  useEffect(() => {
    // Smoothly animate zoomProgressRef between 0 (Data Center) and 1 (Converged Sign In Matrix)
    let animationId: number
    const target = isSignInActive ? 1 : 0

    const animateZoom = () => {
      const diff = target - zoomProgressRef.current
      if (Math.abs(diff) > 0.001) {
        zoomProgressRef.current += diff * 0.08
        animationId = requestAnimationFrame(animateZoom)
      } else {
        zoomProgressRef.current = target
      }
    }

    animateZoom()
    return () => cancelAnimationFrame(animationId)
  }, [isSignInActive])

  // 3D Particle Data Center & Converging Warp Engine
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animationFrameId: number
    let width = 0
    let height = 0

    const updateDimensions = () => {
      if (!canvas) return
      width = canvas.width = window.innerWidth
      height = canvas.height = window.innerHeight
    }

    updateDimensions()

    const handleResize = () => {
      updateDimensions()
      initDataCenterParticles()
    }
    window.addEventListener('resize', handleResize)

    const mouse = {
      x: width / 2,
      y: height / 2,
      targetX: width / 2,
      targetY: height / 2,
      isHovered: false,
      radius: Math.min(width * 0.22, 280)
    }

    const handleMouseMove = (e: MouseEvent) => {
      mouse.targetX = e.clientX
      mouse.targetY = e.clientY
      mouse.isHovered = true
    }

    const handleTouchMove = (e: TouchEvent) => {
      if (e.touches.length > 0) {
        mouse.targetX = e.touches[0].clientX
        mouse.targetY = e.touches[0].clientY
        mouse.isHovered = true
      }
    }

    const handleMouseLeave = () => {
      mouse.isHovered = false
      mouse.targetX = width >= 1024 ? width * 0.70 : width / 2
      mouse.targetY = height * 0.5
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('touchmove', handleTouchMove, { passive: true })
    window.addEventListener('mouseleave', handleMouseLeave)

    let particles: Particle[] = []
    let edges: { p1: number; p2: number; isMainFrame?: boolean }[] = []
    let rotationY = -0.52
    let rotationX = 0.22

    class Particle {
      id: number
      ox: number
      oy: number
      oz: number
      x: number
      y: number
      z: number
      vx: number
      vy: number
      size: number
      colorType: number
      isLed: boolean
      ledBlinkSpeed: number
      convergeAngle: number
      convergeRadius: number
      projX: number = 0
      projY: number = 0
      projZ: number = 0
      alpha: number = 1

      constructor(id: number, ox: number, oy: number, oz: number, isLed: boolean = false) {
        this.id = id
        this.ox = ox
        this.oy = oy
        this.oz = oz

        this.x = ox
        this.y = oy
        this.z = oz

        this.vx = 0
        this.vy = 0

        this.isLed = isLed
        this.ledBlinkSpeed = 1.5 + Math.random() * 3.5
        this.size = isLed ? 2.0 + Math.random() * 1.5 : 1.2 + Math.random() * 1.5
        this.colorType = Math.random()

        // Circular halo convergence parameters for Sign In state
        this.convergeAngle = Math.random() * Math.PI * 2
        this.convergeRadius = 220 + Math.random() * 320
      }

      update(time: number, zoomProgress: number) {
        // Interpolate between 3D Server Rack coordinates and Converged Sign In Matrix
        const matrixX = Math.cos(this.convergeAngle + time * 0.7) * this.convergeRadius
        const matrixY = Math.sin(this.convergeAngle + time * 0.5) * (this.convergeRadius * 0.55)
        const matrixZ = (Math.sin(time * 1.2 + this.id) * 150)

        let targetX = this.ox * (1 - zoomProgress) + matrixX * zoomProgress
        let targetY = this.oy * (1 - zoomProgress) + matrixY * zoomProgress
        let targetZ = this.oz * (1 - zoomProgress) + matrixZ * zoomProgress

        if (this.isLed && zoomProgress < 0.5) {
          targetY += Math.sin(time * this.ledBlinkSpeed) * 1.2
        }

        // 3D Matrix Rotations around Y & X axes
        const curRotY = rotationY * (1 - zoomProgress) + Math.sin(time * 0.3) * 0.2 * zoomProgress
        const curRotX = rotationX * (1 - zoomProgress) + Math.cos(time * 0.2) * 0.1 * zoomProgress

        const cosY = Math.cos(curRotY)
        const sinY = Math.sin(curRotY)
        const cosX = Math.cos(curRotX)
        const sinX = Math.sin(curRotX)

        let x1 = targetX * cosY - targetZ * sinY
        let z1 = targetX * sinY + targetZ * cosY

        let y1 = targetY * cosX - z1 * sinX
        let z2 = targetY * sinX + z1 * cosX

        // Zoom Camera perspective warp effect
        const focalLength = 750 + zoomProgress * 250
        const cameraZOffset = 450 - zoomProgress * 300
        const perspective = focalLength / (focalLength + z2 + cameraZOffset)

        const defaultCenterX = width >= 1024 ? width * 0.70 : width / 2
        const defaultCenterY = width >= 1024 ? height * 0.52 : height * 0.45

        // Center position shifts to true screen center when converged on Sign In page
        const centerX = defaultCenterX * (1 - zoomProgress) + (width / 2) * zoomProgress
        const centerY = defaultCenterY * (1 - zoomProgress) + (height / 2) * zoomProgress

        const screenX = centerX + x1 * perspective
        const screenY = centerY + y1 * perspective

        // Cursor dispersion physics
        const dx = screenX - mouse.x
        const dy = screenY - mouse.y
        const dist = Math.sqrt(dx * dx + dy * dy)

        if (dist < mouse.radius && mouse.isHovered) {
          const force = (1 - dist / mouse.radius) * (18 + zoomProgress * 10)
          const angle = Math.atan2(dy, dx)
          this.vx += Math.cos(angle) * force
          this.vy += Math.sin(angle) * force
        }

        this.x += this.vx
        this.y += this.vy
        this.vx *= 0.86
        this.vy *= 0.86

        this.projX = screenX + this.x
        this.projY = screenY + this.y
        this.projZ = z2
        this.alpha = Math.max(0.15, Math.min(1, (z2 + 550) / 850))
      }

      draw(c: CanvasRenderingContext2D, time: number, zoomProgress: number) {
        if (this.projZ < -750) return
        c.beginPath()
        c.arc(this.projX, this.projY, this.size * (1 + (this.projZ + 300) / 700) * (1 + zoomProgress * 0.8), 0, Math.PI * 2)

        if (this.isLed || zoomProgress > 0.5) {
          const blink = Math.sin(time * this.ledBlinkSpeed) > 0.1
          if (blink) {
            c.fillStyle = `rgba(0, 136, 255, ${this.alpha * 1.0})`
          } else {
            c.fillStyle = `rgba(0, 68, 168, ${this.alpha * 0.85})`
          }
        } else {
          if (this.colorType > 0.6) {
            c.fillStyle = `rgba(0, 68, 168, ${this.alpha * 0.8})`
          } else if (this.colorType > 0.25) {
            c.fillStyle = `rgba(0, 136, 255, ${this.alpha * 0.65})`
          } else {
            c.fillStyle = `rgba(0, 44, 120, ${this.alpha * 0.5})`
          }
        }
        c.fill()
      }
    }

    function initDataCenterParticles() {
      particles = []
      edges = []
      let pId = 0

      const scale = width < 768 ? 0.70 : width < 1440 ? 1.0 : 1.25

      const rackWidth = 90 * scale
      const rackHeight = 260 * scale
      const rackDepth = 120 * scale

      const racks = [
        { x: -250 * scale, y: -130 * scale, z: -60, w: rackWidth, h: rackHeight, d: rackDepth },
        { x: -145 * scale, y: -130 * scale, z: -60, w: rackWidth, h: rackHeight, d: rackDepth },
        { x: -40 * scale, y: -130 * scale, z: -60, w: rackWidth, h: rackHeight, d: rackDepth },
        { x: 65 * scale, y: -130 * scale, z: -60, w: rackWidth, h: rackHeight, d: rackDepth },
        { x: 170 * scale, y: -130 * scale, z: -60, w: rackWidth, h: rackHeight, d: rackDepth },

        { x: -310 * scale, y: -110 * scale, z: 180, w: rackWidth * 0.9, h: rackHeight * 0.9, d: rackDepth * 0.9 },
        { x: -200 * scale, y: -110 * scale, z: 180, w: rackWidth * 0.9, h: rackHeight * 0.9, d: rackDepth * 0.9 },
        { x: 110 * scale, y: -110 * scale, z: 180, w: rackWidth * 0.9, h: rackHeight * 0.9, d: rackDepth * 0.9 },
        { x: 220 * scale, y: -110 * scale, z: 180, w: rackWidth * 0.9, h: rackHeight * 0.9, d: rackDepth * 0.9 }
      ]

      racks.forEach((rack) => {
        const { x, y, z, w, h, d } = rack

        const corners = [
          { x: x, y: y, z: z },
          { x: x + w, y: y, z: z },
          { x: x + w, y: y + h, z: z },
          { x: x, y: y + h, z: z },
          { x: x, y: y, z: z + d },
          { x: x + w, y: y, z: z + d },
          { x: x + w, y: y + h, z: z + d },
          { x: x, y: y + h, z: z + d }
        ]

        const cornerPIndices: number[] = []
        corners.forEach((c) => {
          const idx = pId
          particles.push(new Particle(pId++, c.x, c.y, c.z, true))
          cornerPIndices.push(idx)
        })

        const frameEdges = [
          [0, 1], [1, 2], [2, 3], [3, 0],
          [4, 5], [5, 6], [6, 7], [7, 4],
          [0, 4], [1, 5], [2, 6], [3, 7]
        ]

        frameEdges.forEach(([start, end]) => {
          const c1 = corners[start]
          const c2 = corners[end]
          const edgeDensity = 12
          let prevIdx = cornerPIndices[start]

          for (let i = 1; i < edgeDensity; i++) {
            const t = i / edgeDensity
            const px = c1.x + (c2.x - c1.x) * t
            const py = c1.y + (c2.y - c1.y) * t
            const pz = c1.z + (c2.z - c1.z) * t
            const curIdx = pId
            particles.push(new Particle(pId++, px, py, pz))
            edges.push({ p1: prevIdx, p2: curIdx, isMainFrame: true })
            prevIdx = curIdx
          }
          edges.push({ p1: prevIdx, p2: cornerPIndices[end], isMainFrame: true })
        })

        const slots = 14
        for (let s = 1; s < slots; s++) {
          const slotY = y + (h / slots) * s

          let prevFrontIdx: number | null = null
          for (let k = 0; k <= 6; k++) {
            const bx = x + (w / 6) * k
            const isLed = k === 1 || k === 5
            const curIdx = pId
            particles.push(new Particle(pId++, bx, slotY, z, isLed))
            if (prevFrontIdx !== null) {
              edges.push({ p1: prevFrontIdx, p2: curIdx })
            }
            prevFrontIdx = curIdx
          }

          let prevSideIdx: number | null = null
          for (let k = 0; k <= 5; k++) {
            const bz = z + (d / 5) * k
            const curIdx = pId
            particles.push(new Particle(pId++, x + w, slotY, bz))
            if (prevSideIdx !== null) {
              edges.push({ p1: prevSideIdx, p2: curIdx })
            }
            prevSideIdx = curIdx
          }
        }
      })

      const floorY = 130 * scale
      for (let fx = -450 * scale; fx <= 450 * scale; fx += 75 * scale) {
        let prevGridIdx: number | null = null
        for (let fz = -100; fz <= 350; fz += 50) {
          const curIdx = pId
          particles.push(new Particle(pId++, fx, floorY, fz))
          if (prevGridIdx !== null) {
            edges.push({ p1: prevGridIdx, p2: curIdx })
          }
          prevGridIdx = curIdx
        }
      }
    }

    initDataCenterParticles()
    const startTime = performance.now()

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate)

      const now = performance.now()
      const time = (now - startTime) * 0.0001
      const zoomProgress = zoomProgressRef.current

      mouse.x += (mouse.targetX - mouse.x) * 0.1
      mouse.y += (mouse.targetY - mouse.y) * 0.1

      rotationY = -0.52 + (mouse.x - width / 2) * 0.00005
      rotationX = 0.22 + (mouse.y - height / 2) * 0.00003

      ctx.clearRect(0, 0, width, height)

      for (let i = 0; i < particles.length; i++) {
        particles[i].update(time, zoomProgress)
      }

      // Draw Wireframe Connections
      const connectionMaxDist = 60 + zoomProgress * 40
      for (let i = 0; i < edges.length; i++) {
        const e = edges[i]
        const p1 = particles[e.p1]
        const p2 = particles[e.p2]

        if (!p1 || !p2 || p1.projZ < -750 || p2.projZ < -750) continue

        const dx = p1.projX - p2.projX
        const dy = p1.projY - p2.projY
        const dist = Math.sqrt(dx * dx + dy * dy)

        if (dist < connectionMaxDist) {
          ctx.beginPath()
          ctx.moveTo(p1.projX, p1.projY)
          ctx.lineTo(p2.projX, p2.projY)

          const alpha = (1 - dist / connectionMaxDist) * (e.isMainFrame ? 0.3 : 0.14) * p1.alpha
          ctx.strokeStyle = e.isMainFrame
            ? `rgba(0, 68, 168, ${alpha})`
            : `rgba(0, 102, 221, ${alpha})`
          ctx.lineWidth = e.isMainFrame ? 1.0 : 0.5
          ctx.stroke()
        }
      }

      for (let i = 0; i < particles.length; i++) {
        particles[i].draw(ctx, time, zoomProgress)
      }
    }

    animate()

    return () => {
      cancelAnimationFrame(animationFrameId)
      window.removeEventListener('resize', handleResize)
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('touchmove', handleTouchMove)
      window.removeEventListener('mouseleave', handleMouseLeave)
    }
  }, [])

  return (
    <div className="relative w-screen h-screen min-h-[100dvh] font-sans selection:bg-blue-200 selection:text-blue-900 overflow-hidden flex flex-col justify-between" style={{ background: 'linear-gradient(135deg, #eef4ff 0%, #f5f9ff 40%, #e8f3ff 70%, #f0f6ff 100%)' }}>

      {/* 3D Particle Data Center Canvas */}
      <canvas ref={canvasRef} className="fixed inset-0 w-full h-full pointer-events-auto z-0" />

      {/* Ambient Light Radials */}
      <div className="fixed inset-0 pointer-events-none z-0" style={{ background: 'radial-gradient(ellipse at 25% 35%, rgba(0,68,168,0.07), transparent 60%)' }} />
      <div className="fixed inset-0 pointer-events-none z-0" style={{ background: 'radial-gradient(ellipse at 75% 55%, rgba(0,136,255,0.05), transparent 55%)' }} />

      {/* Floating Bubbles */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden" style={{ zIndex: 1 }}>
        {Array.from({ length: 15 }).map((_, i) => (
          <div
            key={i}
            className="floating-bubble"
            style={{
              left: `${Math.random() * 100}%`,
              width: `${Math.random() * 60 + 20}px`,
              height: `${Math.random() * 60 + 20}px`,
              animationDuration: `${Math.random() * 8 + 6}s`,
              animationDelay: `${Math.random() * 5}s`,
            }}
          />
        ))}
      </div>

      {/* 1. HEADER (Only Logo & SIGN IN Button) */}
      <header className="relative z-50 w-full backdrop-blur-xl border-b shadow-sm" style={{ background: 'rgba(255,255,255,0.85)', borderBottomColor: 'rgba(0,68,168,0.12)' }}>
        <div
          style={{
            paddingLeft: 'clamp(1rem, 4vw, 5rem)',
            paddingRight: 'clamp(1rem, 4vw, 5rem)',
            paddingTop: 'clamp(0.75rem, 1.2vh, 1.25rem)',
            paddingBottom: 'clamp(0.75rem, 1.2vh, 1.25rem)'
          }}
          className="w-full flex items-center justify-between"
        >
          {/* Logo & Subtitle */}
          <Link to="/" onClick={() => setIsSignInActive(false)} className="flex items-center gap-3 group">
            <div className="flex flex-col transition-all group-hover:scale-105" style={{ transformOrigin: 'left center', alignItems: 'flex-start' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <img src="/sanket-icon.png" alt="" style={{ height: 'clamp(1.9rem, 2.8vw, 2.6rem)', width: 'auto', objectFit: 'contain', display: 'block', flexShrink: 0, filter: 'saturate(1.5) contrast(1.25)' }} />
                <span style={{ fontSize: 'clamp(1.4rem, 2.4vw, 2rem)', fontWeight: 800, color: '#0044A8', letterSpacing: '-0.02em' }}>Sanket</span>
              </div>
              <span
                style={{ fontSize: 'clamp(0.6rem, 0.75vw, 0.85rem)', color: '#000000' }}
                className="font-mono font-bold tracking-widest uppercase pt-0.5"
              >
                Secure Analytics Normalization Real-Time Threat Detection
              </span>
            </div>
          </Link>

          {/* Top Right: ONLY SIGN IN BUTTON */}
          <div className="flex items-center">
            {isSignInActive ? (
              <button
                onClick={() => setIsSignInActive(false)}
                style={{
                  fontSize: 'clamp(0.75rem, 0.9vw, 1rem)',
                  padding: 'clamp(0.5rem, 0.8vh, 0.75rem) clamp(1.2rem, 1.6vw, 1.8rem)',
                  color: '#0044A8',
                  background: 'rgba(0,68,168,0.08)',
                  border: '1px solid rgba(0,68,168,0.25)'
                }}
                className="rounded-full font-bold font-mono tracking-wider uppercase transition-all flex items-center gap-2 cursor-pointer"
              >
                <ArrowLeft className="w-4 h-4" style={{ color: '#0044A8' }} />
                <span>BACK TO LANDING</span>
              </button>
            ) : (
              <button
                onClick={() => setIsSignInActive(true)}
                style={{
                  fontSize: 'clamp(0.75rem, 0.9vw, 1rem)',
                  padding: 'clamp(0.5rem, 0.8vh, 0.75rem) clamp(1.4rem, 2vw, 2.2rem)',
                  background: 'linear-gradient(135deg, #0044A8, #0066DD)',
                  boxShadow: '0 4px 20px rgba(0,68,168,0.35)'
                }}
                className="rounded-full font-black font-mono tracking-wider uppercase text-white transition-all flex items-center gap-2 cursor-pointer hover:scale-105"
              >
                <User className="w-4 h-4 text-white" />
                <span>SIGN IN</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* 2. DYNAMIC VIEWPORT (HERO OR SIGN IN CONVERGED CONSOLE) */}
      <main
        style={{
          paddingLeft: 'clamp(1rem, 4vw, 5rem)',
          paddingRight: 'clamp(1rem, 4vw, 5rem)',
          paddingTop: 'clamp(1rem, 2vh, 2.5rem)',
          paddingBottom: 'clamp(1rem, 2vh, 2.5rem)'
        }}
        className="relative z-10 flex-1 flex items-center justify-center w-full"
      >
        {/* LANDING HERO STATE (Always visible) */}
        <div className="w-full grid grid-cols-1 lg:grid-cols-12 items-center animate-fade-in" style={{ gap: 'clamp(1rem, 2vw, 2rem)' }}>

          {/* Left Hero Content */}
          <div className="lg:col-span-9 xl:col-span-8 flex flex-col" style={{ gap: 'clamp(1rem, 2vh, 2rem)' }}>

            {/* Cyber Tag */}
            <div className="w-max">
              <div
                style={{
                  fontSize: 'clamp(0.65rem, 0.8vw, 0.85rem)',
                  padding: 'clamp(0.3rem, 0.5vh, 0.5rem) clamp(0.75rem, 1vw, 1.25rem)',
                  background: 'rgba(0,68,168,0.07)',
                  border: '1px solid rgba(0,68,168,0.25)',
                  color: '#0044A8'
                }}
                className="inline-flex items-center gap-2 rounded-full font-mono font-bold tracking-widest uppercase"
              >
                <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: '#0044A8' }} />
                CYBER SECURITY LOG PLATFORM
              </div>
            </div>

            {/* Headline */}
            <div className="space-y-1">
              <h1
                style={{ fontSize: 'clamp(2.5rem, 5.2vw, 5.8rem)', lineHeight: '0.96', color: '#0a0e27' }}
                className="font-black tracking-tight leading-none"
              >
                Securing <br />
                <span style={{ color: '#0044A8' }}>Every Event.</span>
              </h1>
              <h2
                style={{ fontSize: 'clamp(2rem, 4.2vw, 4.8rem)', color: '#0066DD' }}
                className="font-black tracking-tight pt-1 leading-tight"
              >
                Normalized.
              </h2>
            </div>

            {/* Description */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.1em' }}>

              <p style={{ fontSize: 'clamp(0.95rem, 1.2vw, 1.3rem)', color: '#1e2a4a', fontWeight: 600, lineHeight: 1.4, letterSpacing: '-0.01em' }}>Secure &nbsp;Analytics &nbsp;Normalization</p>
              <p style={{ fontSize: 'clamp(0.95rem, 1.2vw, 1.3rem)', color: '#1e2a4a', fontWeight: 600, lineHeight: 1.4, letterSpacing: '-0.01em' }}>Real-Time &nbsp;Threat &nbsp;Detection</p>
              <p style={{ fontSize: 'clamp(0.95rem, 1.2vw, 1.3rem)', color: '#0044A8', fontWeight: 700, lineHeight: 1.4, letterSpacing: '-0.01em' }}>Built for Modern Cyber Defense.</p>
            </div>

            {/* Stats bar */}
            <div style={{ display: 'flex', gap: 'clamp(1.5rem, 3vw, 3rem)', alignItems: 'center', paddingTop: '0.25rem', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ fontSize: 'clamp(1.4rem, 2.2vw, 2rem)', fontWeight: 900, color: '#0044A8', letterSpacing: '-0.03em', lineHeight: 1 }}>14.2B</span>
                <span style={{ fontSize: 'clamp(0.65rem, 0.8vw, 0.75rem)', color: '#8999b0', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Events / day</span>
              </div>
              <div style={{ width: 1, height: 36, background: 'rgba(0,68,168,0.15)' }} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ fontSize: 'clamp(1.4rem, 2.2vw, 2rem)', fontWeight: 900, color: '#0044A8', letterSpacing: '-0.03em', lineHeight: 1 }}>99.98%</span>
                <span style={{ fontSize: 'clamp(0.65rem, 0.8vw, 0.75rem)', color: '#8999b0', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Delivery Accuracy</span>
              </div>
              <div style={{ width: 1, height: 36, background: 'rgba(0,68,168,0.15)' }} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ fontSize: 'clamp(1.4rem, 2.2vw, 2rem)', fontWeight: 900, color: '#0044A8', letterSpacing: '-0.03em', lineHeight: 1 }}>45k EPS</span>
                <span style={{ fontSize: 'clamp(0.65rem, 0.8vw, 0.75rem)', color: '#8999b0', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Ingest Throughput</span>
              </div>
            </div>

            {/* Action Buttons */}
            <div style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: 'clamp(0.75rem, 1.2vw, 1rem)', alignItems: 'center', paddingTop: '0.5rem' }}>
              {/* Primary CTA */}
              <button
                onClick={() => setIsSignInActive(true)}
                style={{
                  fontSize: 'clamp(0.8rem, 0.95vw, 1rem)',
                  padding: 'clamp(0.7rem, 1.1vh, 0.9rem) clamp(1.6rem, 2.2vw, 2.2rem)',
                  background: 'linear-gradient(135deg, #0044A8 0%, #0066DD 100%)',
                  boxShadow: '0 4px 20px rgba(0,68,168,0.35), inset 0 1px 0 rgba(255,255,255,0.15)',
                  border: '1px solid rgba(0,68,168,0.6)',
                  transition: 'all 0.22s cubic-bezier(0.34,1.56,0.64,1)',
                }}
                className="group relative rounded-2xl text-white font-bold tracking-wide flex items-center justify-center gap-2.5 overflow-hidden cursor-pointer"
                onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-2px) scale(1.02)'; (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 8px 28px rgba(0,68,168,0.5), inset 0 1px 0 rgba(255,255,255,0.2)' }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(0) scale(1)'; (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 4px 20px rgba(0,68,168,0.35), inset 0 1px 0 rgba(255,255,255,0.15)' }}
                onMouseDown={e => { (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(0) scale(0.98)' }}
                onMouseUp={e => { (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-2px) scale(1.02)' }}
              >
                {/* Shimmer overlay */}
                <span style={{ position: 'absolute', inset: 0, background: 'linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.12) 50%, transparent 60%)', backgroundSize: '200% 100%', animation: 'shimmer 2.5s ease infinite', pointerEvents: 'none' }} />
                <Shield style={{ width: 'clamp(0.9rem, 1.05vw, 1.1rem)', height: 'clamp(0.9rem, 1.05vw, 1.1rem)', flexShrink: 0 }} />
                <span style={{ fontFamily: 'inherit', letterSpacing: '0.04em', fontSize: 'inherit' }}>SIGN IN TO SANKET</span>
                <span style={{
                  width: 'clamp(1.5rem, 1.8vw, 1.9rem)', height: 'clamp(1.5rem, 1.8vw, 1.9rem)',
                  borderRadius: '50%', background: 'rgba(255,255,255,0.15)', border: '1px solid rgba(255,255,255,0.2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                  transition: 'transform 0.2s ease'
                }} className="group-hover:translate-x-0.5">
                  <ArrowRight style={{ width: '0.8em', height: '0.8em' }} />
                </span>
              </button>


            </div>



          </div>



        </div>
        {/* RIGHT-SIDE AUTH PANEL — slides in when sign in clicked */}
        <div
          className="landing-auth-panel"
          style={{
            position: 'fixed',
            top: '50%',
            right: 'clamp(2rem, 5vw, 6rem)',
            width: 'clamp(340px, 35vw, 440px)',
            zIndex: 50,
            transform: isSignInActive ? 'translateY(-50%) translateX(0)' : 'translateY(-50%) translateX(100px)',
            opacity: isSignInActive ? 1 : 0,
            visibility: isSignInActive ? 'visible' : 'hidden',
            transition: 'all 0.45s cubic-bezier(0.32, 0.72, 0, 1)',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {/* Frosted glass panel floating box */}
          <div style={{
            borderRadius: '1.5rem',
            background: 'rgba(10, 14, 39, 0.50)',
            backdropFilter: 'blur(24px) saturate(1.2)',
            WebkitBackdropFilter: 'blur(24px) saturate(1.2)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            boxShadow: '0 32px 80px rgba(0, 10, 30, 0.2), 0 0 0 1px rgba(0,68,168,0.15) inset',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            padding: 'clamp(2.5rem, 4vh, 3rem) clamp(1.75rem, 3vw, 2.5rem)',
            position: 'relative',
            overflow: 'hidden',
          }}>

            {/* Subtle top-glow accent */}
            <div style={{ position: 'absolute', top: -60, left: '50%', transform: 'translateX(-50%)', width: '70%', height: 120, borderRadius: '50%', background: 'radial-gradient(ellipse, rgba(0,68,168,0.3) 0%, transparent 70%)', pointerEvents: 'none' }} />

            {/* Close button */}
            <button
              onClick={() => setIsSignInActive(false)}
              style={{ position: 'absolute', top: '1.25rem', right: '1.25rem', width: 32, height: 32, borderRadius: '50%', background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', transition: 'all 0.18s ease', color: 'rgba(255,255,255,0.5)' }}
              onMouseEnter={e => { (e.currentTarget).style.background = 'rgba(255,255,255,0.14)'; (e.currentTarget).style.color = '#fff' }}
              onMouseLeave={e => { (e.currentTarget).style.background = 'rgba(255,255,255,0.07)'; (e.currentTarget).style.color = 'rgba(255,255,255,0.5)' }}
            >
              <X style={{ width: 14, height: 14 }} />
            </button>

            {/* Auth Tab State */}
            <AuthPanel navigate={navigate} redirectTo={redirectTo} />
          </div>
        </div>

        {/* Invisible backdrop for click-outside-to-close */}
        {isSignInActive && (
          <div
            onClick={() => setIsSignInActive(false)}
            style={{
              position: 'fixed', inset: 0, zIndex: 40,
              cursor: 'default',
            }}
          />
        )}
      </main>


      {/* 3. CLEAN FOOTER */}
      <footer
        style={{
          paddingLeft: 'clamp(1rem, 4vw, 5rem)',
          paddingRight: 'clamp(1rem, 4vw, 5rem)',
          paddingTop: 'clamp(0.65rem, 1vh, 1rem)',
          paddingBottom: 'clamp(0.65rem, 1vh, 1rem)',
          background: 'rgba(255,255,255,0.85)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderTop: '1px solid rgba(0,68,168,0.12)',
        }}
        className="relative z-10 w-full"
      >
        <div className="w-full flex items-center justify-end">
          <div style={{ fontSize: 'clamp(0.7rem, 0.85vw, 0.95rem)', color: '#0044A8' }} className="font-mono font-bold tracking-wider">
            CRYPTOGRAPHIC INTEGRITY // MERKLE-VERIFIED AUDIT TRAIL
          </div>
        </div>
      </footer>

      {/* CONTACT MODAL */}
      {isContactModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/90 backdrop-blur-xl">
          <div
            style={{
              padding: 'clamp(1.5rem, 3vh, 2.5rem)',
              width: '90%',
              maxWidth: 'clamp(320px, 40vw, 500px)'
            }}
            className="rounded-3xl bg-slate-900 border border-cyan-400/60 shadow-2xl relative flex flex-col"
          >
            <button
              onClick={() => setIsContactModalOpen(false)}
              style={{
                top: 'clamp(1rem, 2vh, 1.5rem)',
                right: 'clamp(1rem, 2vw, 1.5rem)'
              }}
              className="absolute text-slate-400 hover:text-white transition-colors"
            >
              <X style={{ width: 'clamp(1.2rem, 1.5vw, 1.5rem)', height: 'clamp(1.2rem, 1.5vw, 1.5rem)' }} />
            </button>
            <div className="flex flex-col" style={{ gap: 'clamp(0.2rem, 0.5vh, 0.4rem)' }}>
              <div style={{ fontSize: 'clamp(0.6rem, 0.8vw, 0.75rem)' }} className="text-cyan-400 font-mono font-bold uppercase tracking-widest">
                [ CONTACT SANKET SECURITY ]
              </div>
              <h3 style={{ fontSize: 'clamp(1.5rem, 2.2vw, 2rem)' }} className="font-black text-white leading-tight">
                Get in Touch
              </h3>
              <p style={{ fontSize: 'clamp(0.7rem, 0.9vw, 0.85rem)' }} className="text-slate-300 font-normal">
                Schedule a consultation with our cyber security architects.
              </p>
            </div>

            <form onSubmit={(e) => { e.preventDefault(); alert('Thank you! A SANKET Specialist will contact you shortly.'); setIsContactModalOpen(false); }} className="flex flex-col pt-4" style={{ gap: 'clamp(0.8rem, 1.5vh, 1.25rem)' }}>
              <div>
                <label style={{ fontSize: 'clamp(0.6rem, 0.75vw, 0.75rem)' }} className="block font-mono font-bold text-slate-300 uppercase mb-1.5">
                  Full Name
                </label>
                <input
                  type="text"
                  required
                  placeholder="Alex Mercer"
                  style={{
                    fontSize: 'clamp(0.8rem, 1vw, 0.95rem)',
                    paddingTop: 'clamp(0.7rem, 1vh, 1rem)',
                    paddingBottom: 'clamp(0.7rem, 1vh, 1rem)',
                    paddingLeft: 'clamp(1rem, 1.5vw, 1.5rem)',
                    paddingRight: 'clamp(1rem, 1.5vw, 1.5rem)'
                  }}
                  className="w-full rounded-xl bg-slate-950 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400 transition-colors"
                />
              </div>
              <button
                type="submit"
                style={{
                  fontSize: 'clamp(0.75rem, 0.9vw, 0.95rem)',
                  paddingTop: 'clamp(0.8rem, 1.2vh, 1.2rem)',
                  paddingBottom: 'clamp(0.8rem, 1.2vh, 1.2rem)',
                  marginTop: 'clamp(0.25rem, 0.5vh, 0.5rem)'
                }}
                className="w-full rounded-xl bg-cyan-400 hover:bg-cyan-300 text-slate-950 font-black tracking-wide transition-all shadow-lg cursor-pointer hover:scale-[1.02]"
              >
                Send Message
              </button>
            </form>
          </div>
        </div>
      )}

    </div>
  )
}
