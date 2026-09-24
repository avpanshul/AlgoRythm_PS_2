import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Simple wrapper to extract data from responses
const extractData = (res: any) => res.data

export const api = {
  // Health
  checkHealth: () => apiClient.get('/health').then(extractData),
  getPipelineHealth: () => apiClient.get('/pipeline/health').then(extractData),

  // Events & Ingestion
  ingestEvent: (data: any) => apiClient.post('/events', data).then(extractData),
  ingestBatch: (data: any) => apiClient.post('/events/batch', data).then(extractData),
  getEvents: (params?: any) => apiClient.get('/events', { params }).then(extractData),
  getEvent: (id: string) => apiClient.get(`/events/${id}`).then(extractData),
  getEventTrace: (id: string) => apiClient.get(`/events/${id}/trace`).then(extractData),
  reprocessEvent: (id: string) => apiClient.post(`/reprocess/${id}`).then(extractData),

  // DLQ
  getDlq: (params?: any) => apiClient.get('/dlq', { params }).then(extractData),
  retryDlq: (id: number) => apiClient.post(`/dlq/${id}/retry`).then(extractData),
  resolveDlq: (id: number) => apiClient.post(`/dlq/${id}/resolve`).then(extractData),

  // Replay
  getReplayJobs: (params?: any) => apiClient.get('/replay/jobs', { params }).then(extractData),
  createReplayJob: (data: any) => apiClient.post('/replay/jobs', data).then(extractData),
  approveReplayJob: (id: number) => apiClient.post(`/replay/jobs/${id}/approve`).then(extractData),

  // Audit
  getAuditLogs: (params?: any) => apiClient.get('/audit-logs', { params }).then(extractData),

  // Analytics & Rules
  getStats: () => apiClient.get('/stats').then(extractData),
  getRiskSummary: () => apiClient.get('/risk').then(extractData),
  getTimeseries: (params?: any) => apiClient.get('/analytics/timeseries', { params }).then(extractData),
  getRules: () => apiClient.get('/rules').then(extractData),
  createRule: (data: any) => apiClient.post('/rules', data).then(extractData),
  updateRule: (id: number, data: any) => apiClient.put(`/rules/${id}`, data).then(extractData),
  deleteRule: (id: number) => apiClient.delete(`/rules/${id}`).then(extractData),

  // Parsers
  getParsers: () => apiClient.get('/parsers').then(extractData),
  getParser: (id: string) => apiClient.get(`/parsers/${id}`).then(extractData),
  testParser: (id: string, data: any) => apiClient.post(`/parsers/${id}/test`, data).then(extractData),
  publishParser: (id: string) => apiClient.post(`/parsers/${id}/publish`).then(extractData),

  // Storage
  getStorageSummary: () => apiClient.get('/storage/summary').then(extractData),

  // Admin
  getUsers: () => apiClient.get('/users').then(extractData),
  createUser: (data: any) => apiClient.post('/users', data).then(extractData),
  getRoles: () => apiClient.get('/roles').then(extractData),
  getOrganizations: () => apiClient.get('/organizations').then(extractData),

  // Integrations & Threat Intel
  getIntegrations: () => apiClient.get('/integrations').then(extractData),
  createIntegration: (data: any) => apiClient.post('/integrations', data).then(extractData),
  testIntegration: (id: number) => apiClient.post(`/integrations/${id}/test`).then(extractData),
  getThreatIndicators: () => apiClient.get('/threat-intel/indicators').then(extractData),
  checkThreatIntel: (data: any) => apiClient.post('/threat-intel/check', data).then(extractData),

  // Sources & Mappings (legacy)
  getSources: () => apiClient.get('/sources').then(extractData),
  getMappings: () => apiClient.get('/mappings').then(extractData),
  autoMap: (data: any) => apiClient.post('/mappings/auto', data).then(extractData),
}
