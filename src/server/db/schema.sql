-- Core User & Session Authentication
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  password_salt TEXT NOT NULL,
  display_name TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL,
  expires_at DATETIME NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Canonical Targets & Origin-Scoped Robots Cache with Response Headers
CREATE TABLE IF NOT EXISTS targets (
  id TEXT PRIMARY KEY,
  canonical_url TEXT UNIQUE NOT NULL,
  safe_hostname TEXT NOT NULL,
  origin TEXT NOT NULL, -- e.g. "https://example.com:443"
  last_fetched_at DATETIME,
  last_fetch_status TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS robots_cache (
  origin TEXT PRIMARY KEY, -- Keyed by scheme://hostname:port
  raw_content TEXT NOT NULL, -- Complete raw robots.txt response
  http_status INTEGER NOT NULL,
  response_headers TEXT NOT NULL DEFAULT '{}', -- JSON text of retained headers
  cached_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  expires_at DATETIME NOT NULL
);

-- User Subscriptions & Granular State (Single Source of Truth: capture_config)
CREATE TABLE IF NOT EXISTS subscriptions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  target_id TEXT NOT NULL REFERENCES targets(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  interval_minutes INTEGER NOT NULL CHECK (interval_minutes >= 15 AND interval_minutes <= 1440),
  next_check_at DATETIME NOT NULL, -- Persistent per-subscription scheduling
  capture_config TEXT NOT NULL,    -- Complete canonical JSON capture parameters (Engine, Viewport, Wait)
  capture_fingerprint TEXT NOT NULL, -- SHA-256 hash of canonical capture config
  required_engine TEXT GENERATED ALWAYS AS (json_extract(capture_config, '$.engine')) STORED,
  sensitivity TEXT NOT NULL DEFAULT 'balanced' CHECK (sensitivity IN ('low', 'balanced', 'high')),
  include_selectors TEXT NOT NULL DEFAULT '[]', -- JSON array
  ignore_selectors TEXT NOT NULL DEFAULT '[]',  -- JSON array
  noise_filters TEXT NOT NULL DEFAULT '{"timestamps": true, "counters": true, "tokens": true}',
  keyword_rules TEXT NOT NULL DEFAULT '[]',     -- JSON array
  is_paused INTEGER NOT NULL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Observations (Shared Raw Captures) & Versioned History
CREATE TABLE IF NOT EXISTS observations (
  id TEXT PRIMARY KEY,
  target_id TEXT NOT NULL REFERENCES targets(id) ON DELETE CASCADE,
  engine_used TEXT NOT NULL CHECK (engine_used IN ('http_dom', 'playwright')),
  capture_fingerprint TEXT NOT NULL, -- Canonical SHA-256 fingerprint of capture config
  rendering_fingerprint TEXT NOT NULL, -- JSON detailed metadata
  final_url TEXT NOT NULL,
  http_status INTEGER NOT NULL,
  sanitized_dom TEXT NOT NULL,
  raw_text TEXT NOT NULL,
  screenshot_path TEXT,
  subresource_count INTEGER NOT NULL DEFAULT 0,
  captured_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sub_state (
  subscription_id TEXT PRIMARY KEY REFERENCES subscriptions(id) ON DELETE CASCADE,
  active_version_id TEXT,
  consecutive_failures INTEGER NOT NULL DEFAULT 0,
  is_currently_down INTEGER NOT NULL DEFAULT 0,
  last_down_alert_at DATETIME,
  pending_candidate_hash TEXT,
  pending_candidate_checks INTEGER NOT NULL DEFAULT 0,
  pending_observation_id TEXT REFERENCES observations(id) ON DELETE SET NULL, -- Protected candidate link
  last_alerted_hash TEXT,
  last_alert_sent_at DATETIME,
  recent_checks_window TEXT NOT NULL DEFAULT '[]', -- JSON array of recent statuses
  is_noisy INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS monitor_versions (
  id TEXT PRIMARY KEY,
  subscription_id TEXT NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
  observation_id TEXT NOT NULL REFERENCES observations(id) ON DELETE RESTRICT, -- Protected against cascading deletion
  version_number INTEGER NOT NULL,
  content_hash TEXT NOT NULL,
  stored_text TEXT NOT NULL,
  screenshot_path TEXT,
  change_summary TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(subscription_id, version_number)
);

-- Operational Audit & Events (Nullable version IDs for non-CHANGE events)
CREATE TABLE IF NOT EXISTS check_runs (
  id TEXT PRIMARY KEY,
  subscription_id TEXT REFERENCES subscriptions(id) ON DELETE CASCADE,
  target_id TEXT NOT NULL REFERENCES targets(id) ON DELETE CASCADE,
  job_id TEXT,
  outcome TEXT NOT NULL CHECK (outcome IN ('OK', 'ERROR', 'BLOCKED')),
  reason TEXT,
  http_status INTEGER,
  duration_ms INTEGER NOT NULL,
  was_deduplicated INTEGER NOT NULL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS change_events (
  id TEXT PRIMARY KEY,
  subscription_id TEXT NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
  previous_version_id TEXT REFERENCES monitor_versions(id) ON DELETE SET NULL,
  current_version_id TEXT REFERENCES monitor_versions(id) ON DELETE SET NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('CHANGE', 'DOWN', 'RECOVERED', 'DIGEST')),
  text_diff TEXT, -- JSON diff representation
  keyword_matches TEXT, -- JSON
  summary TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT check_change_has_version CHECK (
    (event_type = 'CHANGE' AND current_version_id IS NOT NULL) OR
    (event_type IN ('DOWN', 'RECOVERED', 'DIGEST'))
  )
);

-- Durable SQLite Queue
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  queue_name TEXT NOT NULL DEFAULT 'checks',
  target_id TEXT REFERENCES targets(id) ON DELETE CASCADE,
  subscription_id TEXT REFERENCES subscriptions(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'CLAIMED', 'RUNNING', 'COMPLETED', 'FAILED')),
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  scheduled_at DATETIME NOT NULL,
  lease_expires_at DATETIME,
  locked_by TEXT,
  error_message TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME
);

-- Notification Outbox & Destinations (Channel-Independent Idempotency)
CREATE TABLE IF NOT EXISTS notification_destinations (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  channel TEXT NOT NULL CHECK (channel IN ('discord', 'telegram', 'email', 'in_app')),
  destination_config TEXT NOT NULL, -- Encrypted/masked config
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notification_outbox (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  change_event_id TEXT NOT NULL REFERENCES change_events(id) ON DELETE CASCADE,
  channel TEXT NOT NULL CHECK (channel IN ('discord', 'telegram', 'email', 'in_app')),
  destination_id TEXT NOT NULL DEFAULT 'default',
  idempotency_key TEXT UNIQUE NOT NULL, -- `${event_id}_${channel}_${dest_id}`
  payload TEXT NOT NULL, -- JSON
  status TEXT NOT NULL CHECK (status IN ('QUEUED', 'PENDING_CONFIG', 'SENT_EXTERNAL', 'RECORDED_IN_APP', 'RETRYING', 'FAILED')),
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  sent_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for optimal lookup performance
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_subs_next_check ON subscriptions(next_check_at) WHERE is_paused = 0;
CREATE INDEX IF NOT EXISTS idx_subs_target ON subscriptions(target_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status_scheduled ON jobs(status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_obs_target_fingerprint ON observations(target_id, capture_fingerprint, captured_at);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON notification_outbox(status);
