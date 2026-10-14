import Database from 'better-sqlite3';
import crypto from 'crypto';
import { initDatabase } from '../src/server/db/database.js';
import { SchedulerEngine } from '../src/server/core/scheduler/scheduler.js';
import { computeCaptureFingerprint } from '../src/server/core/config.js';
import { toSqliteDateTime } from '../src/server/db/dates.js';

async function runBenchmark() {
  console.log('================================================================');
  console.log('  ChangeWatch — 200-Subscription Concurrency Benchmark [S]');
  console.log('================================================================\n');

  const db = initDatabase({ inMemory: true });
  const scheduler = new SchedulerEngine(db);

  // 1. Setup shared target
  const targetId = crypto.randomUUID();
  const targetUrl = 'fixture://stable-clean';
  db.prepare(`
    INSERT INTO targets (id, canonical_url, safe_hostname, origin)
    VALUES (?, ?, 'fixture-host', 'fixture://local')
  `).run(targetId, targetUrl);

  // 2. Canonical capture config (shared across all 200 subscribers)
  const config = computeCaptureFingerprint({
    engine: 'http_dom',
    viewport: { width: 1280, height: 720 },
  });

  const dueTime = toSqliteDateTime(new Date(Date.now() - 30000)); // Due 30 seconds ago
  const SUBSCRIBER_COUNT = 200;

  console.log(`[1/3] Generating ${SUBSCRIBER_COUNT} due subscriptions with compatible capture fingerprints...`);

  // Insert 200 subscribers in a fast transaction
  const insertSubTx = db.transaction(() => {
    for (let i = 1; i <= SUBSCRIBER_COUNT; i++) {
      const uId = `user_${i}`;
      db.prepare(`
        INSERT INTO users (id, email, password_hash, password_salt, display_name)
        VALUES (?, ?, 'h', 's', ?)
      `).run(uId, `user${i}@example.com`, `User ${i}`);

      const sId = `sub_${i}`;
      db.prepare(`
        INSERT INTO subscriptions (
          id, user_id, target_id, name, interval_minutes, next_check_at,
          capture_config, capture_fingerprint, sensitivity
        ) VALUES (?, ?, ?, ?, 60, ?, ?, ?, 'balanced')
      `).run(sId, uId, targetId, `Monitor ${i}`, dueTime, config.canonicalJson, config.fingerprint);

      db.prepare('INSERT INTO sub_state (subscription_id) VALUES (?)').run(sId);
    }
  });

  insertSubTx();
  console.log(`[2/3] Successfully inserted ${SUBSCRIBER_COUNT} due subscriptions.`);

  // 3. Execute Scheduler Due Cycle
  console.log('[3/3] Executing scheduler runDueCycle() over shared target...');
  const startTime = Date.now();
  const cycleResult = await scheduler.runDueCycle();
  const totalElapsedMs = Date.now() - startTime;

  // 4. Verification queries
  const totalObservations = db.prepare('SELECT count(*) as count FROM observations WHERE target_id = ?').get(targetId) as { count: number };
  const totalCheckRuns = db.prepare('SELECT count(*) as count FROM check_runs WHERE target_id = ?').get(targetId) as { count: number };
  const deduplicatedRuns = db.prepare('SELECT count(*) as count FROM check_runs WHERE target_id = ? AND was_deduplicated = 1').get(targetId) as { count: number };

  console.log('\n------------------- Benchmark Results -------------------');
  console.log(`  Subscribers Evaluated:       ${cycleResult.evaluatedCount} / ${SUBSCRIBER_COUNT}`);
  console.log(`  Target URL Top-Level Fetches: ${totalObservations.count} (Strict Requirement: 1)`);
  console.log(`  Deduplication Ratio:         ${cycleResult.evaluatedCount} : ${totalObservations.count} (${((deduplicatedRuns.count / cycleResult.evaluatedCount) * 100).toFixed(1)}% savings)`);
  console.log(`  Total Execution Latency:     ${totalElapsedMs} ms`);
  console.log(`  Average Latency / Sub:       ${(totalElapsedMs / cycleResult.evaluatedCount).toFixed(2)} ms`);
  console.log('---------------------------------------------------------\n');

  if (totalObservations.count === 1 && cycleResult.evaluatedCount === SUBSCRIBER_COUNT) {
    console.log('✅ BENCHMARK PASSED: 200 compatible subscriptions triggered strictly 1 top-level capture!\n');
    db.close();
    process.exit(0);
  } else {
    console.error('❌ BENCHMARK FAILED: Expected 1 fetch for 200 subscribers, got', totalObservations.count);
    db.close();
    process.exit(1);
  }
}

runBenchmark().catch(err => {
  console.error('Benchmark error:', err);
  process.exit(1);
});
