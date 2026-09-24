// Canonical Event Types
export interface CanonicalEvent {
  event_id: string
  timestamp: string
  event: {
    category: string
    type: string
    action: string
    severity: string
    outcome: string
  }
  source: { ip?: string; port?: number }
  destination: { ip?: string; port?: number }
  network: { protocol?: string; transport?: string }
  device: { id?: string; vendor?: string; product?: string }
  parser: { format: string; parser_version: string }
  normalization: { mapping_method: string; confidence: number }
  provenance: { raw_event_id: string; raw_sha256: string }
  risk?: { score: number; level: string; factors: Array<{ factor: string; contribution: number }> }
  extensions?: Record<string, unknown>
}

export interface RawEvent {
  event_id: string
  raw_sha256: string
  raw_location: string
  received_at: string
  ingestion_protocol: string
  raw_content: string
}

export interface Mapping {
  id: number
  vendor: string
  device_type?: string
  raw_field: string
  canonical_field: string
  mapping_type: string
  confidence: number
  approved: boolean
  approved_by?: string
  created_at: string
}

export interface Source {
  id: string
  name: string
  vendor?: string
  product?: string
  device_type?: string
  enabled: boolean
  created_at: string
}

export interface Stats {
  total_events: number
  formats: Record<string, number>
  severities: Record<string, number>
  top_actions: Record<string, number>
  events_over_time: Array<{ time: string; count: number }>
}

export interface RiskSummary {
  risk_distribution: Record<string, number>
  average_risk_score: number
  max_risk_score: number
  critical_events_count: number
  critical_events: CanonicalEvent[]
}

export interface TraceStage {
  stage: string
  label: string
  data: Record<string, unknown> | null
}

export interface EventTrace {
  event_id: string
  trace: TraceStage[]
}
