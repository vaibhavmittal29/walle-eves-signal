import { Router, Response } from 'express';
import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import { z } from 'zod';
import { getDatabase } from '../db/database.js';
import { requireAuth, AuthenticatedRequest } from '../core/auth.js';
import { computeCaptureFingerprint, CaptureConfigSchema } from '../core/config.js';

const router = Router();

// Monitor creation schema
const CreateMonitorSchema = z.object({
  url: z.string().url('Invalid URL format'),
  name: z.string().min(1, 'Name is required').max(100),
  interval_minutes: z.number().int().min(15).max(1440).default(60),
  capture_config: z.record(z.any()).optional().default({}),
  sensitivity: z.enum(['low', 'balanced', 'high']).default('balanced'),
  include_selectors: z.array(z.string()).default([]),
  ignore_selectors: z.array(z.string()).default([]),
  noise_filters: z.object({
    timestamps: z.boolean().default(true),
    counters: z.boolean().default(true),
    tokens: z.boolean().default(true),
  }).default({ timestamps: true, counters: true, tokens: true }),
  keyword_rules: z.array(z.object({
    keyword: z.string(),
    mode: z.enum(['MUST_CONTAIN', 'MUST_NOT_CONTAIN', 'ALERT_IF_ADDED', 'ALERT_IF_REMOVED']),
  })).default([]),
});

const UpdateMonitorSchema = z.object({
  name: z.string().min(1).max(100).optional(),
  interval_minutes: z.number().int().min(15).max(1440).optional(),
  capture_config: z.record(z.any()).optional(),
  sensitivity: z.enum(['low', 'balanced', 'high']).optional(),
  include_selectors: z.array(z.string()).optional(),
  ignore_selectors: z.array(z.string()).optional(),
  noise_filters: z.object({
    timestamps: z.boolean(),
    counters: z.boolean(),
    tokens: z.boolean(),
  }).optional(),
  keyword_rules: z.array(z.object({
    keyword: z.string(),
    mode: z.enum(['MUST_CONTAIN', 'MUST_NOT_CONTAIN', 'ALERT_IF_ADDED', 'ALERT_IF_REMOVED']),
  })).optional(),
  is_paused: z.boolean().optional(),
});

export function normalizeTargetUrl(rawUrl: string): { canonicalUrl: string; hostname: string; origin: string } {
  const parsed = new URL(rawUrl);
  // Normalize protocol & hostname to lowercase
  parsed.protocol = parsed.protocol.toLowerCase();
  parsed.hostname = parsed.hostname.toLowerCase();
  
  // Default ports stripped
  const defaultPort = parsed.protocol === 'https:' ? '443' : '80';
  const effectivePort = parsed.port || defaultPort;
  const origin = `${parsed.protocol}//${parsed.hostname}:${effectivePort}`;

  // Canonical URL strips fragment and trailing slash unless root path
  parsed.hash = '';
  let canonicalUrl = parsed.toString();
  if (canonicalUrl.endsWith('/') && parsed.pathname === '/') {
    // Keep single trailing slash for root domain
  } else if (canonicalUrl.endsWith('/')) {
    canonicalUrl = canonicalUrl.slice(0, -1);
  }

  return {
    canonicalUrl,
    hostname: parsed.hostname,
    origin,
  };
}

// GET /api/monitors - List all monitors for logged in user
router.get('/', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const db = getDatabase();
  const userId = req.user!.id;

  const monitors = db.prepare(`
    SELECT 
      s.id, s.user_id, s.name, s.interval_minutes, s.next_check_at,
      s.capture_config, s.capture_fingerprint, s.required_engine,
      s.sensitivity, s.include_selectors, s.ignore_selectors,
      s.noise_filters, s.keyword_rules, s.is_paused, s.created_at,
      t.canonical_url, t.safe_hostname, t.origin,
      st.active_version_id, st.consecutive_failures, st.is_currently_down,
      st.is_noisy, st.last_alert_sent_at,
      mv.version_number as latest_version_number,
      mv.created_at as latest_version_at
    FROM subscriptions s
    JOIN targets t ON s.target_id = t.id
    LEFT JOIN sub_state st ON s.id = st.subscription_id
    LEFT JOIN monitor_versions mv ON st.active_version_id = mv.id
    WHERE s.user_id = ?
    ORDER BY s.created_at DESC
  `).all(userId);

  const formatted = monitors.map((m: any) => ({
    ...m,
    capture_config: JSON.parse(m.capture_config),
    include_selectors: JSON.parse(m.include_selectors),
    ignore_selectors: JSON.parse(m.ignore_selectors),
    noise_filters: JSON.parse(m.noise_filters),
    keyword_rules: JSON.parse(m.keyword_rules),
    is_paused: Boolean(m.is_paused),
    is_currently_down: Boolean(m.is_currently_down),
    is_noisy: Boolean(m.is_noisy),
  }));

  res.json({ monitors: formatted });
});

// GET /api/monitors/:id - Retrieve single monitor
router.get('/:id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const db = getDatabase();
  const userId = req.user!.id;
  const monitorId = String(req.params.id);

  const monitor = db.prepare(`
    SELECT 
      s.id, s.user_id, s.name, s.interval_minutes, s.next_check_at,
      s.capture_config, s.capture_fingerprint, s.required_engine,
      s.sensitivity, s.include_selectors, s.ignore_selectors,
      s.noise_filters, s.keyword_rules, s.is_paused, s.created_at,
      t.canonical_url, t.safe_hostname, t.origin,
      st.active_version_id, st.consecutive_failures, st.is_currently_down,
      st.is_noisy, st.last_alert_sent_at, st.recent_checks_window
    FROM subscriptions s
    JOIN targets t ON s.target_id = t.id
    LEFT JOIN sub_state st ON s.id = st.subscription_id
    WHERE s.id = ? AND s.user_id = ?
  `).get(monitorId, userId) as any;

  if (!monitor) {
    res.status(404).json({ error: 'Monitor not found' });
    return;
  }

  const versions = db.prepare(`
    SELECT id, version_number, content_hash, stored_text, screenshot_path, change_summary, created_at
    FROM monitor_versions
    WHERE subscription_id = ?
    ORDER BY version_number DESC
    LIMIT 20
  `).all(monitorId);

  const recentRuns = db.prepare(`
    SELECT id, outcome, reason, http_status, duration_ms, was_deduplicated, created_at
    FROM check_runs
    WHERE subscription_id = ?
    ORDER BY created_at DESC
    LIMIT 20
  `).all(monitorId);

  res.json({
    monitor: {
      ...monitor,
      capture_config: JSON.parse(monitor.capture_config),
      include_selectors: JSON.parse(monitor.include_selectors),
      ignore_selectors: JSON.parse(monitor.ignore_selectors),
      noise_filters: JSON.parse(monitor.noise_filters),
      keyword_rules: JSON.parse(monitor.keyword_rules),
      recent_checks_window: JSON.parse(monitor.recent_checks_window || '[]'),
      is_paused: Boolean(monitor.is_paused),
      is_currently_down: Boolean(monitor.is_currently_down),
      is_noisy: Boolean(monitor.is_noisy),
    },
    versions,
    recentRuns,
  });
});

// POST /api/monitors - Create new monitor
router.post('/', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const parseResult = CreateMonitorSchema.safeParse(req.body);
  if (!parseResult.success) {
    res.status(400).json({ error: parseResult.error.errors[0].message });
    return;
  }

  const data = parseResult.data;
  const userId = req.user!.id;
  const db = getDatabase();

  // Validate capture_config with cross-field consistency
  let captureParsed;
  try {
    captureParsed = computeCaptureFingerprint(data.capture_config);
  } catch (err: any) {
    res.status(400).json({ error: err.message || 'Invalid capture configuration' });
    return;
  }

  // Normalize target URL
  let targetInfo;
  try {
    targetInfo = normalizeTargetUrl(data.url);
  } catch {
    res.status(400).json({ error: 'Invalid URL scheme or structure' });
    return;
  }

  // Find or insert canonical target
  let target = db.prepare('SELECT id FROM targets WHERE canonical_url = ?').get(targetInfo.canonicalUrl) as any;
  if (!target) {
    const targetId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO targets (id, canonical_url, safe_hostname, origin)
      VALUES (?, ?, ?, ?)
    `).run(targetId, targetInfo.canonicalUrl, targetInfo.hostname, targetInfo.origin);
    target = { id: targetId };
  }

  const subscriptionId = crypto.randomUUID();
  const nextCheckAt = new Date().toISOString(); // Immediate first check scheduled

  const insertStmt = db.prepare(`
    INSERT INTO subscriptions (
      id, user_id, target_id, name, interval_minutes, next_check_at,
      capture_config, capture_fingerprint,
      sensitivity, include_selectors, ignore_selectors,
      noise_filters, keyword_rules, is_paused
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
  `);

  insertStmt.run(
    subscriptionId,
    userId,
    target.id,
    data.name,
    data.interval_minutes,
    nextCheckAt,
    captureParsed.canonicalJson,
    captureParsed.fingerprint,
    data.sensitivity,
    JSON.stringify(data.include_selectors),
    JSON.stringify(data.ignore_selectors),
    JSON.stringify(data.noise_filters),
    JSON.stringify(data.keyword_rules)
  );

  // Initialize subscription state
  db.prepare(`
    INSERT INTO sub_state (subscription_id)
    VALUES (?)
  `).run(subscriptionId);

  // Fetch created subscription to return generated stored columns
  const created = db.prepare(`
    SELECT s.*, t.canonical_url, t.safe_hostname, t.origin
    FROM subscriptions s
    JOIN targets t ON s.target_id = t.id
    WHERE s.id = ?
  `).get(subscriptionId) as any;

  res.status(201).json({
    monitor: {
      ...created,
      capture_config: JSON.parse(created.capture_config),
      include_selectors: JSON.parse(created.include_selectors),
      ignore_selectors: JSON.parse(created.ignore_selectors),
      noise_filters: JSON.parse(created.noise_filters),
      keyword_rules: JSON.parse(created.keyword_rules),
      is_paused: Boolean(created.is_paused),
    },
  });
});

// PUT /api/monitors/:id - Update monitor
router.put('/:id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const parseResult = UpdateMonitorSchema.safeParse(req.body);
  if (!parseResult.success) {
    res.status(400).json({ error: parseResult.error.errors[0].message });
    return;
  }

  const db = getDatabase();
  const userId = req.user!.id;
  const monitorId = String(req.params.id);

  const existing = db.prepare('SELECT id, capture_config FROM subscriptions WHERE id = ? AND user_id = ?').get(monitorId, userId) as any;
  if (!existing) {
    res.status(404).json({ error: 'Monitor not found' });
    return;
  }

  const updates = parseResult.data;
  const sets: string[] = [];
  const params: any[] = [];

  if (updates.name !== undefined) {
    sets.push('name = ?');
    params.push(updates.name);
  }
  if (updates.interval_minutes !== undefined) {
    sets.push('interval_minutes = ?');
    params.push(updates.interval_minutes);
  }
  if (updates.sensitivity !== undefined) {
    sets.push('sensitivity = ?');
    params.push(updates.sensitivity);
  }
  if (updates.include_selectors !== undefined) {
    sets.push('include_selectors = ?');
    params.push(JSON.stringify(updates.include_selectors));
  }
  if (updates.ignore_selectors !== undefined) {
    sets.push('ignore_selectors = ?');
    params.push(JSON.stringify(updates.ignore_selectors));
  }
  if (updates.noise_filters !== undefined) {
    sets.push('noise_filters = ?');
    params.push(JSON.stringify(updates.noise_filters));
  }
  if (updates.keyword_rules !== undefined) {
    sets.push('keyword_rules = ?');
    params.push(JSON.stringify(updates.keyword_rules));
  }
  if (updates.is_paused !== undefined) {
    sets.push('is_paused = ?');
    params.push(updates.is_paused ? 1 : 0);
  }
  if (updates.capture_config !== undefined) {
    try {
      const { canonicalJson, fingerprint } = computeCaptureFingerprint(updates.capture_config);
      sets.push('capture_config = ?');
      params.push(canonicalJson);
      sets.push('capture_fingerprint = ?');
      params.push(fingerprint);
    } catch (err: any) {
      res.status(400).json({ error: err.message || 'Invalid capture configuration' });
      return;
    }
  }

  if (sets.length > 0) {
    params.push(monitorId, userId);
    db.prepare(`UPDATE subscriptions SET ${sets.join(', ')} WHERE id = ? AND user_id = ?`).run(...params);
  }

  const updated = db.prepare(`
    SELECT s.*, t.canonical_url, t.safe_hostname, t.origin
    FROM subscriptions s
    JOIN targets t ON s.target_id = t.id
    WHERE s.id = ?
  `).get(monitorId) as any;

  res.json({
    monitor: {
      ...updated,
      capture_config: JSON.parse(updated.capture_config),
      include_selectors: JSON.parse(updated.include_selectors),
      ignore_selectors: JSON.parse(updated.ignore_selectors),
      noise_filters: JSON.parse(updated.noise_filters),
      keyword_rules: JSON.parse(updated.keyword_rules),
      is_paused: Boolean(updated.is_paused),
    },
  });
});

// DELETE /api/monitors/:id - Explicit user deletion workflow
router.delete('/:id', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const db = getDatabase();
  const userId = req.user!.id;
  const monitorId = String(req.params.id);

  const existing = db.prepare('SELECT id FROM subscriptions WHERE id = ? AND user_id = ?').get(monitorId, userId);
  if (!existing) {
    res.status(404).json({ error: 'Monitor not found' });
    return;
  }

  // 1. Gather any screenshot file paths that belong to this monitor's versions
  const versions = db.prepare(`
    SELECT screenshot_path FROM monitor_versions WHERE subscription_id = ?
  `).all(monitorId) as { screenshot_path: string | null }[];

  // 2. Delete the subscription from SQLite (cascades to sub_state, monitor_versions, check_runs, change_events)
  db.prepare('DELETE FROM subscriptions WHERE id = ? AND user_id = ?').run(monitorId, userId);

  // 3. Remove physical files if they exist
  for (const v of versions) {
    if (v.screenshot_path && fs.existsSync(v.screenshot_path)) {
      try {
        fs.unlinkSync(v.screenshot_path);
      } catch (err) {
        console.warn('Could not remove screenshot file during monitor deletion:', v.screenshot_path, err);
      }
    }
  }

  res.json({ success: true, message: 'Monitor and associated versions deleted successfully' });
});

// POST /api/monitors/:id/check - Trigger an immediate check run
router.post('/:id/check', requireAuth, async (req: AuthenticatedRequest, res: Response) => {
  const db = getDatabase();
  const userId = req.user!.id;
  const monitorId = String(req.params.id);

  const monitor = db.prepare(`
    SELECT s.*, t.canonical_url, t.safe_hostname, t.origin
    FROM subscriptions s
    JOIN targets t ON s.target_id = t.id
    WHERE s.id = ? AND s.user_id = ?
  `).get(monitorId, userId) as any;

  if (!monitor) {
    res.status(404).json({ error: 'Monitor not found' });
    return;
  }

  const { ConfigAwareDeduplicator } = await import('../core/scheduler/deduplicator.js');
  const { VersionManager } = await import('../core/analysis/version-manager.js');
  const { FailureTracker } = await import('../core/analysis/failure-tracker.js');
  const { NotificationOutboxEngine } = await import('../core/notification/outbox.js');

  const deduplicator = new ConfigAwareDeduplicator(db);
  const vm = new VersionManager(db);
  const ft = new FailureTracker(db);
  const outbox = new NotificationOutboxEngine(db);

  const rawConfig = JSON.parse(monitor.capture_config);
  const captureResult = await deduplicator.executeOrShareCapture(
    monitor.target_id,
    monitor.canonical_url,
    rawConfig
  );

  const failureStatus = ft.handleCheckOutcome(
    monitorId,
    captureResult.classification.outcome,
    captureResult.classification.reason
  );

  let versionOutcome: any = null;
  if (captureResult.classification.outcome === 'OK' && captureResult.observation) {
    versionOutcome = vm.evaluateSubscription(monitorId, captureResult.observation);

    // If change confirmed, enqueue notifications to configured channels
    if (versionOutcome.changeDetected && versionOutcome.version) {
      const changeEvent = db.prepare(`
        SELECT id FROM change_events
        WHERE subscription_id = ? AND current_version_id = ?
      `).get(monitorId, versionOutcome.version.id) as { id: string } | undefined;

      if (changeEvent) {
        // Enqueue in_app notification
        outbox.enqueueNotification(userId, changeEvent.id, 'in_app', {
          monitorName: monitor.name,
          url: monitor.canonical_url,
          summary: `Version ${versionOutcome.version.version_number} recorded`,
        });

        // Enqueue discord if configured
        const discordDest = db.prepare(`
          SELECT * FROM notification_destinations WHERE user_id = ? AND channel = 'discord' AND enabled = 1
        `).get(userId);
        if (discordDest) {
          outbox.enqueueNotification(userId, changeEvent.id, 'discord', {
            monitorName: monitor.name,
            url: monitor.canonical_url,
            summary: `Content updated on ${monitor.name}`,
          });
        }
      }
    }
  }

  // Record check_run
  const runId = crypto.randomUUID();
  db.prepare(`
    INSERT INTO check_runs (
      id, subscription_id, target_id, outcome, reason, http_status, duration_ms, was_deduplicated
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    runId,
    monitorId,
    monitor.target_id,
    captureResult.classification.outcome,
    captureResult.classification.reason,
    captureResult.classification.httpStatus || null,
    captureResult.durationMs,
    captureResult.wasDeduplicated ? 1 : 0
  );

  res.json({
    outcome: captureResult.classification.outcome,
    reason: captureResult.classification.reason,
    httpStatus: captureResult.classification.httpStatus,
    durationMs: captureResult.durationMs,
    wasDeduplicated: captureResult.wasDeduplicated,
    versionOutcome,
    failureStatus,
  });
});

// GET /api/monitors/:id/diff - Retrieve diff between versions
router.get('/:id/diff', requireAuth, async (req: AuthenticatedRequest, res: Response) => {
  const db = getDatabase();
  const userId = req.user!.id;
  const monitorId = String(req.params.id);

  const monitor = db.prepare('SELECT id FROM subscriptions WHERE id = ? AND user_id = ?').get(monitorId, userId);
  if (!monitor) {
    res.status(404).json({ error: 'Monitor not found' });
    return;
  }

  const v1Param = req.query.v1 as string | undefined;
  const v2Param = req.query.v2 as string | undefined;

  let v1: any;
  let v2: any;

  if (v1Param && v2Param) {
    v1 = db.prepare('SELECT * FROM monitor_versions WHERE id = ? AND subscription_id = ?').get(v1Param, monitorId);
    v2 = db.prepare('SELECT * FROM monitor_versions WHERE id = ? AND subscription_id = ?').get(v2Param, monitorId);
  } else {
    const recent = db.prepare(`
      SELECT * FROM monitor_versions WHERE subscription_id = ? ORDER BY version_number DESC LIMIT 2
    `).all(monitorId) as any[];

    if (recent.length >= 2) {
      v2 = recent[0];
      v1 = recent[1];
    } else if (recent.length === 1) {
      v2 = recent[0];
      v1 = recent[0];
    }
  }

  if (!v2) {
    res.status(404).json({ error: 'No version snapshots available to compare' });
    return;
  }

  const { computeMyersDiff } = await import('../core/analysis/myers-diff.js');
  const text1 = v1 ? v1.stored_text : '';
  const text2 = v2.stored_text;

  const diffResult = computeMyersDiff(text1, text2, { includeWordDiff: true, label: `v${v1?.version_number || 1} -> v${v2.version_number}` });

  res.json({
    previousVersion: v1,
    currentVersion: v2,
    diff: diffResult,
  });
});

export default router;
