import { Navigate, useLocation } from 'react-router-dom'
import { getToken } from './authStore'

export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const token = getToken()
  if (!token) {
    // The landing page's own dark glass panel is the one real login/signup
    // surface -- there's no separate /login page anymore.
    return <Navigate to="/" state={{ openAuth: true, from: location.pathname }} replace />
  }
  return <>{children}</>
}
