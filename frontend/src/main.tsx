import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'

import AppLayout from './layouts/AppLayout'
import Dashboard from './pages/Dashboard'
import EventExplorer from './pages/EventExplorer'
import EventDetail from './pages/EventDetail'
import RiskAnalytics from './pages/RiskAnalytics'
import MappingRegistryPage from './pages/MappingRegistry'
import MappingReview from './pages/MappingReview'
import LogSources from './pages/LogSources'
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
import DemoJourney from './pages/DemoJourney'
import ArchitecturePage from './pages/ArchitecturePage'
import UserFlows from './pages/UserFlows'
import NationalImpact from './pages/NationalImpact'
import FeatureClassification from './pages/FeatureClassification'

// Placeholder pages for minor routes
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
        <AppLayout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/events" element={<EventExplorer />} />
            <Route path="/events/:id" element={<EventDetail />} />
            <Route path="/incidents" element={<IncidentCenter />} />
            
            <Route path="/sources" element={<LogSources />} />
            <Route path="/add-source" element={<AddLogSourceWizard />} />
            
            <Route path="/parsers" element={<MappingRegistryPage />} />
            <Route path="/parser-studio" element={<MappingReview />} />
            
            <Route path="/replay" element={<ReplayCenter />} />
            <Route path="/dlq" element={<FailedEvents />} />
            <Route path="/raw" element={<RawVault />} />
            <Route path="/privacy" element={<PrivacyPolicies />} />
            
            <Route path="/data-quality" element={<DataQuality />} />
            <Route path="/health" element={<PlatformHealth />} />
            <Route path="/audit" element={<AuditLogs />} />
            
            <Route path="/users" element={<UserManagement />} />
            <Route path="/integrations" element={<Placeholder title="Integrations" />} />
            <Route path="/docs" element={<Placeholder title="Documentation" />} />
            <Route path="/demo" element={<DemoJourney />} />
            <Route path="/architecture" element={<ArchitecturePage />} />
            <Route path="/user-flows" element={<UserFlows />} />
            <Route path="/national-impact" element={<NationalImpact />} />
            <Route path="/features" element={<FeatureClassification />} />
          </Routes>
        </AppLayout>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
)
