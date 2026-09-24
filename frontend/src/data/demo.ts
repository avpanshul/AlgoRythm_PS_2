// Centralized realistic demo data for ULPF
// This data is used as a fallback when backend APIs are not yet implemented or returning empty.

export const DEMO_SOURCES = [
  { id: 'src_01', name: 'FW-Delhi-01', type: 'Firewall', vendor: 'Palo Alto', transport: 'Syslog UDP', status: 'Healthy', eventsPerMin: 12431, parser: 'v1.4.2', lastSeen: 'Just now' },
  { id: 'src_02', name: 'FW-Mumbai-02', type: 'Firewall', vendor: 'Fortinet', transport: 'Syslog TCP', status: 'Healthy', eventsPerMin: 8432, parser: 'v1.1.0', lastSeen: 'Just now' },
  { id: 'src_03', name: 'IDS-Mumbai', type: 'IDS/IPS', vendor: 'Snort', transport: 'Kafka', status: 'Warning', eventsPerMin: 2193, parser: 'v2.0.1', lastSeen: '2 mins ago' },
  { id: 'src_04', name: 'Web-Server-Prod', type: 'Server', vendor: 'Nginx', transport: 'Filebeat', status: 'Healthy', eventsPerMin: 8291, parser: 'v1.0.5', lastSeen: 'Just now' },
  { id: 'src_05', name: 'AWS-CloudTrail', type: 'Cloud', vendor: 'AWS', transport: 'S3 Bucket', status: 'Healthy', eventsPerMin: 6120, parser: 'v3.2.0', lastSeen: '1 min ago' },
  { id: 'src_06', name: 'App-Logs', type: 'Application', vendor: 'Internal', transport: 'HTTP Webhook', status: 'Healthy', eventsPerMin: 1984, parser: 'v1.0.0', lastSeen: 'Just now' },
  { id: 'src_07', name: 'Router-HQ', type: 'Network Device', vendor: 'Cisco', transport: 'Syslog UDP', status: 'Healthy', eventsPerMin: 450, parser: 'v1.1.2', lastSeen: '5 mins ago' },
  { id: 'src_08', name: 'DB-Server', type: 'Database', vendor: 'Oracle', transport: 'JDBC Agent', status: 'Failed', eventsPerMin: 0, parser: 'v1.0.0', lastSeen: '14 hours ago' }
]

export const DEMO_EVENTS = [
  { event_id: 'evt_001', timestamp: new Date(Date.now() - 1000).toISOString(), source: { ip: '192.168.1.10', name: 'FW-Delhi-01' }, event: { action: 'Intrusion Detected', severity: 'critical' }, quality: 96, integrity: true },
  { event_id: 'evt_002', timestamp: new Date(Date.now() - 5000).toISOString(), source: { ip: '10.0.5.22', name: 'Web-Server-Prod' }, event: { action: 'Admin Login', severity: 'medium' }, quality: 88, integrity: true },
  { event_id: 'evt_003', timestamp: new Date(Date.now() - 12000).toISOString(), source: { ip: '172.16.0.5', name: 'AWS-CloudTrail' }, event: { action: 'IAM Policy Changed', severity: 'low' }, quality: 91, integrity: true },
  { event_id: 'evt_004', timestamp: new Date(Date.now() - 25000).toISOString(), source: { ip: '192.168.2.50', name: 'IDS-Mumbai' }, event: { action: 'Port Scan', severity: 'high' }, quality: 79, integrity: true },
  { event_id: 'evt_005', timestamp: new Date(Date.now() - 45000).toISOString(), source: { ip: '10.0.1.100', name: 'App-Logs' }, event: { action: 'File Upload', severity: 'low' }, quality: 99, integrity: true }
]

export const DEMO_ALERTS = [
  { id: 1, time: '2 min ago', message: 'Multiple failed logins', source: 'FW-Delhi-01', severity: 'High' },
  { id: 2, time: '12 min ago', message: 'Port scan detected', source: 'IDS-Mumbai', severity: 'Medium' },
  { id: 3, time: '28 min ago', message: 'Suspicious file download', source: 'Web-Server-Prod', severity: 'High' },
  { id: 4, time: '1 hour ago', message: 'Unusual data transfer', source: 'App-Logs', severity: 'Low' }
]

export const DEMO_PIPELINE_STAGES = [
  { name: 'Sources', status: 'Healthy', metric: '12/12' },
  { name: 'Ingestion', status: 'Events', metric: '1.24M' },
  { name: 'Parsing', status: 'Success', metric: '95.5%' },
  { name: 'Normalization', status: 'Valid', metric: '98.8%' },
  { name: 'Redaction', status: 'Complete', metric: '98.6%' },
  { name: 'Integrity', status: 'Verified', metric: '100%' },
  { name: 'Storage', status: 'Healthy', metric: 'OK' }
]

export const DEMO_DLQ_FAILURES = [
  { id: 'err_293847239', reason: 'Schema Validation', parser: 'v1.4.2', time: '10 mins ago', severity: 'danger' },
  { id: 'err_293847111', reason: 'Unknown Format', parser: 'v1.4.2', time: '12 mins ago', severity: 'warning' },
  { id: 'err_293847005', reason: 'Missing Required Field', parser: 'v1.1.0', time: '1 hour ago', severity: 'warning' },
  { id: 'err_293846999', reason: 'Parser Exception', parser: 'v2.0.1', time: '3 hours ago', severity: 'danger' }
]

export const DEMO_REPLAY_JOBS = [
  { id: 'replay_001', status: 'Completed', events: '24,532', time: '2 hours ago' },
  { id: 'replay_002', status: 'Completed', events: '8,421', time: 'Yesterday' },
  { id: 'replay_003', status: 'Failed', events: '0', time: 'Yesterday' }
]
