export interface MonitorItem {
  id: string;
  user_id: string;
  name: string;
  interval_minutes: number;
  next_check_at: string;
  capture_config: any;
  capture_fingerprint: string;
  required_engine: 'http_dom' | 'playwright';
  sensitivity: 'low' | 'balanced' | 'high';
  include_selectors: string[];
  ignore_selectors: string[];
  noise_filters: { timestamps: boolean; counters: boolean; tokens: boolean };
  keyword_rules: Array<{ keyword: string; mode: string }>;
  is_paused: boolean;
  created_at: string;
  canonical_url: string;
  safe_hostname: string;
  origin: string;
  active_version_id?: string;
  consecutive_failures: number;
  is_currently_down: boolean;
  is_noisy: boolean;
  latest_version_number?: number;
  latest_version_at?: string;
}

export interface VersionItem {
  id: string;
  version_number: number;
  content_hash: string;
  stored_text: string;
  screenshot_path: string | null;
  change_summary: string | null;
  created_at: string;
}

export interface CheckRunItem {
  id: string;
  outcome: 'OK' | 'ERROR' | 'BLOCKED';
  reason: string | null;
  http_status: number | null;
  duration_ms: number;
  was_deduplicated: boolean;
  created_at: string;
}

export interface OutboxItem {
  id: string;
  change_event_id: string;
  channel: 'discord' | 'telegram' | 'email' | 'in_app';
  destination_id: string;
  idempotency_key: string;
  payload: any;
  status: 'QUEUED' | 'PENDING_CONFIG' | 'SENT_EXTERNAL' | 'RECORDED_IN_APP' | 'RETRYING' | 'FAILED';
  attempts: number;
  last_error: string | null;
  sent_at: string | null;
  created_at: string;
  monitor_name: string;
  event_type: string;
  summary: string;
}

export interface DiffChunk {
  type: 'added' | 'removed' | 'unchanged';
  value: string;
  count?: number;
}

export interface MyersDiffResult {
  additions: number;
  deletions: number;
  lineChanges: DiffChunk[];
  wordChanges?: DiffChunk[];
  unifiedPatch: string;
}

