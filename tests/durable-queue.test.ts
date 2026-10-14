import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { initDatabase } from '../src/server/db/database.js';
import { DurableJobQueue } from '../src/server/core/scheduler/queue.js';
import { SchedulerEngine } from '../src/server/core/scheduler/scheduler.js';
import { DomainRateLimiter, calculateJitteredNextCheck } from '../src/server/core/scheduler/rate-limiter.js';
import { computeCaptureFingerprint } from '../src/server/core/config.js';
import Database from 'better-sqlite3';
import crypto from 'crypto';
import { toSqliteDateTime } from '../src/server/db/dates.js';

describe('Durable Queue, Deduplication & Due-Only Scheduling [D, F, R, AA, AB]', () => {
  let db: Database.Database;

  beforeEach(() => {
    db = initDatabase({ inMemory: true });
  });

  afterEach(() => {
    db.close();
  });

  it('[R] handles atomic job claims, heartbeat lease extensions, and crash recovery', () => {
    const queue = new DurableJobQueue(db, 'worker_1', 2); // 2 second lease

    // 1. Enqueue job
    const job = queue.enqueueJob({ queueName: 'checks' });
    expect(job.status).toBe('QUEUED');
    expect(job.attempts).toBe(0);

    // 2. Claim job
    const claimed = queue.claimNextJob('checks');
    expect(claimed).not.toBeNull();
    expect(claimed?.id).toBe(job.id);
    expect(claimed?.status).toBe('CLAIMED');
    expect(claimed?.locked_by).toBe('worker_1');
    expect(claimed?.attempts).toBe(1);

    // Second claim immediately returns null (already locked)
    const secondClaim = queue.claimNextJob('checks');
    expect(secondClaim).toBeNull();

    // 3. Heartbeat extends lease
    const beat = queue.heartbeatJob(job.id);
    expect(beat).toBe(true);

    // 4. Crash recovery: manually simulate expired lease in DB
    db.prepare(`
      UPDATE jobs
      SET lease_expires_at = datetime('now', '-10 seconds')
      WHERE id = ?
    `).run(job.id);

    // Worker 2 performs startup crash recovery
    const worker2Queue = new DurableJobQueue(db, 'worker_2');
    const recoveredCount = worker2Queue.recoverStaleJobs();
    expect(recoveredCount).toBe(1);

    // The job is back in QUEUED status and can be claimed by worker 2
    const claimedBy2 = worker2Queue.claimNextJob('checks');
    expect(claimedBy2).not.toBeNull();
    expect(claimedBy2?.locked_by).toBe('worker_2');
    expect(claimedBy2?.attempts).toBe(2);
  });

  it('[F] enforces per-domain rate limiting and ±10% scheduling jitter', () => {
    const limiter = new DomainRateLimiter(500); // 500ms min gap
    const domain = 'api.github.com';

    // First navigation is allowed
    expect(limiter.canNavigate(domain).allowed).toBe(true);
    limiter.startNavigation(domain);

    // While active, concurrent navigation is blocked
    expect(limiter.canNavigate(domain).allowed).toBe(false);

    // Finish navigation
    limiter.finishNavigation(domain);

    // Immediate subsequent navigation blocked due to min gap
    expect(limiter.canNavigate(domain).allowed).toBe(false);

    // Jitter calculation test: for interval 60 min, result is within [54, 66] minutes
    for (let i = 0; i < 50; i++) {
      const now = new Date();
      const next = calculateJitteredNextCheck(60, now);
      const diffMinutes = (next.getTime() - now.getTime()) / (60 * 1000);
      expect(diffMinutes).toBeGreaterThanOrEqual(53.9);
      expect(diffMinutes).toBeLessThanOrEqual(66.1);
    }
  });

  it('[AA] due-only subscription evaluation: only due monitors are evaluated and advanced', async () => {
    const scheduler = new SchedulerEngine(db);

    // Setup user and target
    const userId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO users (id, email, password_hash, password_salt, display_name)
      VALUES (?, 'u@test.com', 'h', 's', 'User')
    `).run(userId);

    const targetId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO targets (id, canonical_url, safe_hostname, origin)
      VALUES (?, 'fixture://stable-clean', 'fixture-host', 'fixture://local')
    `).run(targetId);

    const config = computeCaptureFingerprint({});

    // 1. Subscription A: DUE NOW (next_check_at in the past)
    const subADueTime = toSqliteDateTime(new Date(Date.now() - 60000));
    const subAId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO subscriptions (
        id, user_id, target_id, name, interval_minutes, next_check_at,
        capture_config, capture_fingerprint
      ) VALUES (?, ?, ?, 'Sub A (Due)', 60, ?, ?, ?)
    `).run(subAId, userId, targetId, subADueTime, config.canonicalJson, config.fingerprint);

    // 2. Subscription B: NOT DUE (next_check_at 30 minutes in the future)
    const futureTime = toSqliteDateTime(new Date(Date.now() + 30 * 60 * 1000));
    const subBId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO subscriptions (
        id, user_id, target_id, name, interval_minutes, next_check_at,
        capture_config, capture_fingerprint
      ) VALUES (?, ?, ?, 'Sub B (Not Due)', 60, ?, ?, ?)
    `).run(subBId, userId, targetId, futureTime, config.canonicalJson, config.fingerprint);

    // Run scheduler cycle
    const result = await scheduler.runDueCycle();
    expect(result.evaluatedCount).toBe(1); // ONLY Sub A was evaluated!

    // Verify Sub A has check_run and updated next_check_at
    const subARuns = db.prepare('SELECT * FROM check_runs WHERE subscription_id = ?').all(subAId);
    expect(subARuns.length).toBe(1);

    const subARow = db.prepare('SELECT next_check_at FROM subscriptions WHERE id = ?').get(subAId) as any;
    const subANextTime = new Date(subARow.next_check_at.replace(' ', 'T') + 'Z').getTime();
    expect(subANextTime).toBeGreaterThan(Date.now());

    // Verify Sub B has ZERO check_runs and its next_check_at was untouched
    const subBRuns = db.prepare('SELECT * FROM check_runs WHERE subscription_id = ?').all(subBId);
    expect(subBRuns.length).toBe(0);

    const subBRow = db.prepare('SELECT next_check_at FROM subscriptions WHERE id = ?').get(subBId) as any;
    expect(subBRow.next_check_at).toBe(futureTime);
  });

  it('[AB] config-aware deduplication: incompatible capture configs execute separate fetches', async () => {
    const scheduler = new SchedulerEngine(db);

    const userId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO users (id, email, password_hash, password_salt, display_name)
      VALUES (?, 'u2@test.com', 'h', 's', 'User2')
    `).run(userId);

    const targetId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO targets (id, canonical_url, safe_hostname, origin)
      VALUES (?, 'fixture://stable-clean', 'fixture-host', 'fixture://local')
    `).run(targetId);

    // Config 1: Viewport 1280x720
    const cfg1 = computeCaptureFingerprint({ viewport: { width: 1280, height: 720 } });
    // Config 2: Viewport 1920x1080 (distinct fingerprint)
    const cfg2 = computeCaptureFingerprint({ viewport: { width: 1920, height: 1080 } });

    expect(cfg1.fingerprint).not.toBe(cfg2.fingerprint);

    const sub1Id = crypto.randomUUID();
    db.prepare(`
      INSERT INTO subscriptions (
        id, user_id, target_id, name, interval_minutes, next_check_at,
        capture_config, capture_fingerprint
      ) VALUES (?, ?, ?, 'Sub 1', 60, datetime('now', '-10 seconds'), ?, ?)
    `).run(sub1Id, userId, targetId, cfg1.canonicalJson, cfg1.fingerprint);

    const sub2Id = crypto.randomUUID();
    db.prepare(`
      INSERT INTO subscriptions (
        id, user_id, target_id, name, interval_minutes, next_check_at,
        capture_config, capture_fingerprint
      ) VALUES (?, ?, ?, 'Sub 2', 60, datetime('now', '-10 seconds'), ?, ?)
    `).run(sub2Id, userId, targetId, cfg2.canonicalJson, cfg2.fingerprint);

    const cycle = await scheduler.runDueCycle();
    expect(cycle.evaluatedCount).toBe(2);
    // Because configs were incompatible, they were partitioned into 2 separate groups!
    expect(cycle.groupsProcessed).toBe(2);
    expect(cycle.deduplicatedRuns).toBe(0);

    // Both distinct observations were persisted in observations table
    const obs = db.prepare('SELECT DISTINCT capture_fingerprint FROM observations WHERE target_id = ?').all(targetId);
    expect(obs.length).toBe(2);
  });
});
