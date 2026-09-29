import axios from 'axios'
import { getToken, clearToken } from '../auth/authStore'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Real bearer-token auth: several routers on the backend (parsers, rules,
// dlq, audit, admin, integrations, privacy-policies, unknown-clusters,
// pack-sharing, ingestion) require `Depends(get_current_user)` at the
// router level -- this frontend had no auth flow at all, so every request
// to those routes 401'd silently and pages like Parser Lab just rendered
// their honest "no data" empty state, which looked like a bug.
apiClient.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err?.response?.status === 401 && window.location.pathname !== '/') {
      clearToken()
      window.location.href = '/'
    }
    return Promise.reject(err)
  }
)

// Simple wrapper to extract data from responses
const extractData = (res: any) => res.data

export const api = {
  // Auth
  login: (email: string, password: string) => apiClient.post('/auth/login', { email, password }).then(extractData),
  signup: (name: string, email: string, password: string) => apiClient.post('/auth/signup', { name, email, password }).then(extractData),
  getCurrentUser: () => apiClient.get('/auth/me').then(extractData),

  // Platform settings
  getSettings: () => apiClient.get('/settings').then(extractData),
  updateSettings: (values: Record<string, any>) => apiClient.put('/settings', { values }).then(extractData),

  // Health
  checkHealth: () => apiClient.get('/health').then(extractData),
  getPipelineHealth: () => apiClient.get('/pipeline/health').then(extractData),

  // Events & Ingestion
  ingestEvent: (data: any) => apiClient.post('/events', data).then(extractData),
  ingestBatch: (data: any) => apiClient.post('/events/batch', data).then(extractData),
  getEvents: (params?: any) => apiClient.get('/events', { params }).then(extractData),
  getEvent: (id: string) => apiClient.get(`/events/${id}`).then(extractData),
  getRawEvent: (id: string) => apiClient.get(`/events/${id}/raw`).then(extractData),
  getEventTrace: (id: string) => apiClient.get(`/events/${id}/trace`).then(extractData),
  getEventProof: (id: string) => apiClient.get(`/events/${id}/proof`).then(extractData),
  reprocessEvent: (id: string) => apiClient.post(`/reprocess/${id}`).then(extractData),

  // Raw vault
  getVault: (params?: any) => apiClient.get('/vault', { params }).then(extractData),
  getVaultRecord: (id: string) => apiClient.get(`/vault/${id}`).then(extractData),

  // Integrity (Merkle checkpoints)
  createCheckpoint: () => apiClient.post('/integrity/checkpoints').then(extractData),
  getLatestCheckpoint: () => apiClient.get('/integrity/checkpoints/latest').then(extractData),
  getCheckpoints: () => apiClient.get('/integrity/checkpoints').then(extractData),

  // Evidence
  getEvidenceBundleUrl: (eventId: string) => `${API_URL}/evidence/bundle/${eventId}`,
  getVerifierDownloadUrl: () => `${API_URL}/evidence/verifier`,

  // Export
  getExportUrl: (format: 'json' | 'csv' | 'ocsf.json' | 'cef' | 'syslog', params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return `${API_URL}/export/events.${format}${qs}`
  },
  getIndicatorsStixUrl: () => `${API_URL}/export/indicators.stix`,
  // Authenticated blob download (a plain <a href> would drop the bearer
  // token and bounce to /login, yielding an HTML file instead of data).
  downloadExport: async (format: 'json' | 'csv' | 'ocsf.json' | 'cef' | 'syslog', params?: Record<string, string>) => {
    const res = await apiClient.get(`/export/events.${format}`, { params, responseType: 'blob' })
    const blob = new Blob([res.data], { type: String(res.headers?.['content-type'] || 'application/octet-stream') })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ulpf_events.${format === 'json' ? 'json' : format === 'csv' ? 'csv' : 'txt'}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 5000)
  },

  // Coverage matrix
  getCoverageMatrix: () => apiClient.get('/parsers-coverage-matrix').then(extractData),

  // DLQ
  getDlq: (params?: any) => apiClient.get('/dlq', { params }).then(extractData),
  retryDlq: (id: number) => apiClient.post(`/dlq/${id}/retry`).then(extractData),
  resolveDlq: (id: number) => apiClient.post(`/dlq/${id}/resolve`).then(extractData),

  // Replay
  getReplayJobs: (params?: any) => apiClient.get('/replay/jobs', { params }).then(extractData),
  createReplayJob: (data: any) => apiClient.post('/replay/jobs', data).then(extractData),
  approveReplayJob: (id: number) => apiClient.post(`/replay/jobs/${id}/approve`).then(extractData),
  runReplayJob: (id: number) => apiClient.post(`/replay/jobs/${id}/run`).then(extractData),

  // Audit
  getAuditLogs: (params?: any) => apiClient.get('/audit-logs', { params }).then(extractData),

  // Analytics & Rules
  getStats: () => apiClient.get('/stats').then(extractData),
  getRiskSummary: () => apiClient.get('/risk').then(extractData),
  getTimeseries: (params?: any) => apiClient.get('/analytics/timeseries', { params }).then(extractData),
  getQualitySummary: () => apiClient.get('/analytics/quality-summary').then(extractData),
  getSilentSources: (params?: any) => apiClient.get('/analytics/silent-sources', { params }).then(extractData),
  getVolumeAnomalies: (params?: any) => apiClient.get('/analytics/volume-anomalies', { params }).then(extractData),
  getPeerDeviation: (params?: any) => apiClient.get('/analytics/peer-deviation', { params }).then(extractData),
  getSupervisoryOverview: (params?: any) => apiClient.get('/supervisory/organizations', { params }).then(extractData),
  getRules: () => apiClient.get('/rules').then(extractData),
  createRule: (data: any) => apiClient.post('/rules', data).then(extractData),
  updateRule: (id: number, data: any) => apiClient.put(`/rules/${id}`, data).then(extractData),
  deleteRule: (id: number) => apiClient.delete(`/rules/${id}`).then(extractData),

  // Parsers
  getParsers: () => apiClient.get('/parsers').then(extractData),
  getParser: (id: string) => apiClient.get(`/parsers/${id}`).then(extractData),
  createParser: (data: any) => apiClient.post('/parsers', data).then(extractData),
  testParser: (id: string, data: any) => apiClient.post(`/parsers/${id}/test`, data).then(extractData),
  publishParser: (id: string) => apiClient.post(`/parsers/${id}/publish`).then(extractData),

  // Storage
  getStorageSummary: () => apiClient.get('/storage/summary').then(extractData),

  // Admin
  getUsers: () => apiClient.get('/users').then(extractData),
  createUser: (data: any) => apiClient.post('/users', data).then(extractData),
  updateUser: (id: string, data: any) => apiClient.put(`/users/${id}`, data).then(extractData),
  deleteUser: (id: string) => apiClient.delete(`/users/${id}`).then(extractData),
  getRoles: () => apiClient.get('/roles').then(extractData),
  getOrganizations: () => apiClient.get('/organizations').then(extractData),
  createOrganization: (data: any) => apiClient.post('/organizations', data).then(extractData),

  // Privacy policies
  getPrivacyPolicies: () => apiClient.get('/privacy-policies').then(extractData),
  createPrivacyPolicy: (data: any) => apiClient.post('/privacy-policies', data).then(extractData),
  updatePrivacyPolicy: (id: number, data: any) => apiClient.put(`/privacy-policies/${id}`, data).then(extractData),
  deletePrivacyPolicy: (id: number) => apiClient.delete(`/privacy-policies/${id}`).then(extractData),

  // Integrations & Threat Intel
  getIntegrations: () => apiClient.get('/integrations').then(extractData),
  createIntegration: (data: any) => apiClient.post('/integrations', data).then(extractData),
  deleteIntegration: (id: number) => apiClient.delete(`/integrations/${id}`).then(extractData),
  testIntegration: (id: number) => apiClient.post(`/integrations/${id}/test`).then(extractData),
  getThreatIndicators: () => apiClient.get('/threat-intel/indicators').then(extractData),
  createThreatIndicator: (data: any) => apiClient.post('/threat-intel/indicators', data).then(extractData),
  // Real bug found live: backend expects {"indicators": [...]} (a list --
  // it checks several IOCs against stored indicators at once), but this
  // was sending {"value": "..."}, which never matched the schema and threw
  // a 422 on every single search.
  checkThreatIntel: (value: string) => apiClient.post('/threat-intel/check', { indicators: [value] }).then(extractData),

  // Sources & Mappings (legacy)
  getSources: () => apiClient.get('/sources').then(extractData),
  createSource: (data: any) => apiClient.post('/sources', data).then(extractData),
  updateSource: (id: string, data: any) => apiClient.put(`/sources/${id}`, data).then(extractData),
  analyzeSample: (data: { sample: string; vendor?: string; device_type?: string }) =>
    apiClient.post('/sources/analyze-sample', data).then(extractData),
  getMappings: (params?: any) => apiClient.get('/mappings', { params }).then(extractData),
  approveMapping: (id: number, data: any) => apiClient.post(`/mappings/${id}/approve`, data).then(extractData),
  rejectMapping: (id: number, data: any) => apiClient.post(`/mappings/${id}/reject`, data).then(extractData),
  autoMap: (data: any) => apiClient.post('/mappings/auto', data).then(extractData),

  // Correlation (E1)
  getCorrelations: (params?: any) => apiClient.get('/correlations', { params }).then(extractData),
  getCorrelation: (id: string) => apiClient.get(`/correlations/${id}`).then(extractData),
  evaluateCorrelations: () => apiClient.post('/correlations/evaluate').then(extractData),

  // Entity behavioral profiles / Sentinel (E7a)
  getEntities: (params?: any) => apiClient.get('/entities', { params }).then(extractData),
  getEntityProfile: (id: string) => apiClient.get(`/entities/${encodeURIComponent(id)}/profile`).then(extractData),
  updateEntityProfiles: () => apiClient.post('/entities/update-profiles').then(extractData),

  // Incident cases / notifications (E6)
  getCases: (params?: any) => apiClient.get('/cases', { params }).then(extractData),
  getCase: (id: string) => apiClient.get(`/cases/${id}`).then(extractData),
  createCase: (data: any) => apiClient.post('/cases', data).then(extractData),
  updateCase: (id: string, data: any) => apiClient.patch(`/cases/${id}`, data).then(extractData),
  notifyCase: (id: string) => apiClient.post(`/cases/${id}/notify`).then(extractData),
  ackNotification: (id: string, acknowledged_by: string) => apiClient.post(`/notifications/${id}/ack`, { acknowledged_by }).then(extractData),
  getOnCallContacts: () => apiClient.get('/oncall').then(extractData),
  createOnCallContact: (data: any) => apiClient.post('/oncall', data).then(extractData),

  // Entity graph / attack path / timeline (E2/E8)
  getGraph: (params?: any) => apiClient.get('/graph', { params }).then(extractData),
  getAttackPath: (entity: string) => apiClient.get('/attack-path', { params: { entity } }).then(extractData),
  getTimeline: (params: { entity?: string; incident_id?: string }) => apiClient.get('/timeline', { params }).then(extractData),

  // Threat-hunting workspace (E3)
  getHunts: () => apiClient.get('/hunts').then(extractData),
  createHunt: (data: any) => apiClient.post('/hunts', data).then(extractData),
  deleteHunt: (id: string) => apiClient.delete(`/hunts/${id}`).then(extractData),
  runHunt: (id: string) => apiClient.post(`/hunts/${id}/run`).then(extractData),

  // Retention / legal hold (D10)
  getRetentionPolicies: () => apiClient.get('/retention-policies').then(extractData),
  upsertRetentionPolicy: (data: any) => apiClient.put('/retention-policies', data).then(extractData),
  getLegalHolds: (params?: any) => apiClient.get('/legal-holds', { params }).then(extractData),
  createLegalHold: (data: any) => apiClient.post('/legal-holds', data).then(extractData),
  releaseLegalHold: (id: string) => apiClient.post(`/legal-holds/${id}/release`).then(extractData),
  runRetentionSweep: () => apiClient.post('/retention/run-sweep').then(extractData),

  // Unknown-format clusters + AI-assisted pack drafting
  getUnknownClusters: () => apiClient.get('/unknown-clusters').then(extractData),
  getClusterSamples: (clusterId: string) => apiClient.get(`/unknown-clusters/${clusterId}/samples`).then(extractData),
  draftPackForCluster: (clusterId: string) => apiClient.post(`/unknown-clusters/${clusterId}/draft-pack`).then(extractData),
  getReasoningTrace: (clusterId: string) => apiClient.get(`/unknown-clusters/${clusterId}/reasoning-trace`).then(extractData),

  // Sparks (Item 2)
  getSparks: () => apiClient.get('/sparks').then(extractData),
  getSpark: (id: string) => apiClient.get(`/sparks/${id}`).then(extractData),

  // Parser Lab community sharing (signed export/import/rollback)
  exportParser: (id: string) => apiClient.get(`/parsers/${id}/export`).then(extractData),
  importParser: (bundle: any) => apiClient.post('/parsers/import', bundle).then(extractData),
  rollbackParser: (id: string, version: string) => apiClient.post(`/parsers/${id}/rollback/${version}`).then(extractData),
  getParserVersions: (id: string) => apiClient.get(`/parsers/${id}/versions`).then(extractData),

  // Event version history (replay-safe: appended, not overwritten)
  getEventVersions: (eventId: string) => apiClient.get(`/events/${eventId}/versions`).then(extractData),
}
