import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { initDatabase } from '../src/server/db/database.js';
import { SchedulerEngine } from '../src/server/core/scheduler/scheduler.js';
import { computeCaptureFingerprint } from '../src/server/core/config.js';
import { toSqliteDateTime } from '../src/server/db/dates.js';
import Database from 'better-sqlite3';
import crypto from 'crypto';

describe('200-Subscription Concurrency Benchmark [S]', () => {
  let db: Database.Database;
  let scheduler: SchedulerEngine;

  beforeEach(() => {
    db = initDatabase({ inMemory: true });
    scheduler = new SchedulerEngine(db);
  });

  afterEach(() => {
    db.close();
  });

  it('[S] 200 subscriptions on the same URL with compatible fingerprints trigger exactly 1 top-level fetch', async () => {
    const targetId = crypto.randomUUID();
    const targetUrl = 'fixture://stable-clean';
    db.prepare(`
      INSERT INTO targets (id, canonical_url, safe_hostname, origin)
      VALUES (?, ?, 'fixture-host', 'fixture://local')
    `).run(targetId, targetUrl);

    const config = computeCaptureFingerprint({
      engine: 'http_dom',
      viewport: { width: 1280, height: 720 },
    });

    const dueTime = toSqliteDateTime(new Date(Date.now() - 30000));
    const COUNT = 200;

    // Fast transaction insert of 200 subscribers
    const insertTx = db.transaction(() => {
      for (let i = 1; i <= COUNT; i++) {
        const uId = `user_${i}`;
        db.prepare(`
          INSERT INTO users (id, email, password_hash, password_salt, display_name)
          VALUES (?, ?, 'h', 's', ?)
        `).run(uId, `u${i}@example.com`, `User ${i}`);

        const sId = `sub_${i}`;
        db.prepare(`
          INSERT INTO subscriptions (
            id, user_id, target_id, name, interval_minutes, next_check_at,
            capture_config, capture_fingerprint, sensitivity
          ) VALUES (?, ?, ?, ?, 60, ?, ?, ?, 'balanced')
        `).run(sId, uId, targetId, `Sub ${i}`, dueTime, config.canonicalJson, config.fingerprint);

        db.prepare('INSERT INTO sub_state (subscription_id) VALUES (?)').run(sId);
      }
    });

    insertTx();

    // Run scheduler cycle
    const result = await scheduler.runDueCycle();

    expect(result.evaluatedCount).toBe(200);
    expect(result.groupsProcessed).toBe(1); // 1 compatible group!

    // Verify top-level observations table contains STRICTLY 1 capture!
    const obsRows = db.prepare('SELECT id FROM observations WHERE target_id = ?').all(targetId);
    expect(obsRows.length).toBe(1);

    // Verify check_runs contains 200 entries
    const runRows = db.prepare('SELECT id, was_deduplicated FROM check_runs WHERE target_id = ?').all(targetId) as any[];
    expect(runRows.length).toBe(200);

    // 1 initial fetch + 199 deduplicated runs
    const dedupCount = runRows.filter(r => r.was_deduplicated === 1).length;
    expect(dedupCount).toBe(199);
  });
});
