import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'

import AppLayout from './layouts/AppLayout'
import RequireAuth from './auth/RequireAuth'
import LandingPage from './pages/LandingPage'
import Dashboard from './pages/Dashboard'
import EventDetail from './pages/EventDetail'
import MappingRegistryPage from './pages/MappingRegistry'
import MappingReview from './pages/MappingReview'
import LogSources from './pages/LogSources'
import SourceDetail from './pages/SourceDetail'
import AddLogSourceWizard from './pages/AddLogSourceWizard'
import FailedEvents from './pages/FailedEvents'
import RawVault from './pages/RawVault'
import PrivacyPolicies from './pages/PrivacyPolicies'
import ReplayCenter from './pages/ReplayCenter'
import DataQuality from './pages/DataQuality'
import PlatformHealth from './pages/PlatformHealth'
import AuditLogs from './pages/AuditLogs'
import IncidentCenter from './pages/IncidentCenter'
import UserManagement from './pages/UserManagement'
import Supervisory from './pages/Supervisory'
import Evidence from './pages/Evidence'
import Alerts from './pages/Alerts'
import IntegrationsPage from './pages/IntegrationsPage'
import SettingsPage from './pages/SettingsPage'
import Cases from './pages/Cases'
import EntityGraph from './pages/EntityGraph'
import AttackPath from './pages/AttackPath'
import Hunt from './pages/Hunt'

const Placeholder = ({ title }: { title: string }) => (
  <div style={{ padding: 40 }}>
    <h1 style={{ fontSize: 24, fontWeight: 700, color: 'var(--color-text-main)', marginBottom: 12 }}>{title}</h1>
    <p style={{ color: 'var(--color-text-muted)' }}>This section is available in the full enterprise edition.</p>
  </div>
)

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1 } } })

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          {/* Landing Page Route */}
          <Route path="/" element={<LandingPage />} />

          {/* Log Dashboard Routes */}
          <Route path="/dashboard" element={<RequireAuth><AppLayout><Dashboard /></AppLayout></RequireAuth>} />
          <Route path="/events/:id" element={<RequireAuth><AppLayout><EventDetail /></AppLayout></RequireAuth>} />
          <Route path="/incidents" element={<RequireAuth><AppLayout><IncidentCenter /></AppLayout></RequireAuth>} />

          <Route path="/sources" element={<RequireAuth><AppLayout><LogSources /></AppLayout></RequireAuth>} />
          <Route path="/sources/:id" element={<RequireAuth><AppLayout><SourceDetail /></AppLayout></RequireAuth>} />
          <Route path="/add-source" element={<RequireAuth><AppLayout><AddLogSourceWizard /></AppLayout></RequireAuth>} />
          
          <Route path="/parsers" element={<RequireAuth><AppLayout><MappingRegistryPage /></AppLayout></RequireAuth>} />
          <Route path="/parser-studio" element={<RequireAuth><AppLayout><MappingReview /></AppLayout></RequireAuth>} />
          
          <Route path="/replay" element={<RequireAuth><AppLayout><ReplayCenter /></AppLayout></RequireAuth>} />
          <Route path="/dlq" element={<RequireAuth><AppLayout><FailedEvents /></AppLayout></RequireAuth>} />
          <Route path="/raw" element={<RequireAuth><AppLayout><RawVault /></AppLayout></RequireAuth>} />
          <Route path="/privacy" element={<RequireAuth><AppLayout><PrivacyPolicies /></AppLayout></RequireAuth>} />
          
          <Route path="/data-quality" element={<RequireAuth><AppLayout><DataQuality /></AppLayout></RequireAuth>} />
          <Route path="/supervisory" element={<RequireAuth><AppLayout><Supervisory /></AppLayout></RequireAuth>} />
          <Route path="/evidence" element={<RequireAuth><AppLayout><Evidence /></AppLayout></RequireAuth>} />
          <Route path="/alerts" element={<RequireAuth><AppLayout><Alerts /></AppLayout></RequireAuth>} />
          <Route path="/health" element={<RequireAuth><AppLayout><PlatformHealth /></AppLayout></RequireAuth>} />
          <Route path="/audit" element={<RequireAuth><AppLayout><AuditLogs /></AppLayout></RequireAuth>} />
          
          <Route path="/users" element={<RequireAuth><AppLayout><UserManagement /></AppLayout></RequireAuth>} />
          <Route path="/integrations" element={<RequireAuth><AppLayout><IntegrationsPage /></AppLayout></RequireAuth>} />
          <Route path="/settings" element={<RequireAuth><AppLayout><SettingsPage /></AppLayout></RequireAuth>} />

          <Route path="/cases" element={<RequireAuth><AppLayout><Cases /></AppLayout></RequireAuth>} />
          <Route path="/graph" element={<RequireAuth><AppLayout><EntityGraph /></AppLayout></RequireAuth>} />
          <Route path="/attack-path" element={<RequireAuth><AppLayout><AttackPath /></AppLayout></RequireAuth>} />
          <Route path="/hunt" element={<RequireAuth><AppLayout><Hunt /></AppLayout></RequireAuth>} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
)
