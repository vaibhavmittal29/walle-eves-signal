import Database from 'better-sqlite3';
import crypto from 'crypto';
import { initDatabase } from '../src/server/db/database.js';
import { hashPassword, verifyPassword, createSession, validateSessionToken } from '../src/server/core/auth.js';
import { validatePublicIp } from '../src/server/core/security/ip-validator.js';
import { computeCaptureFingerprint } from '../src/server/core/config.js';
import { ConfigAwareDeduplicator } from '../src/server/core/scheduler/deduplicator.js';
import { VersionManager } from '../src/server/core/analysis/version-manager.js';
import { FailureTracker } from '../src/server/core/analysis/failure-tracker.js';
import { NotificationOutboxEngine } from '../src/server/core/notification/outbox.js';
import { setFixtureOverride, clearFixtureOverrides } from '../src/server/core/capture/fixture-dispatcher.js';
import { FIXTURES } from '../src/fixtures/index.js';

async function runSmokeTests() {
  console.log('================================================================');
  console.log('  ChangeWatch — Automated Smoke Test Suite [AH]');
  console.log('================================================================\n');

  const db = initDatabase({ inMemory: true });
  const deduplicator = new ConfigAwareDeduplicator(db);
  const vm = new VersionManager(db);
  const ft = new FailureTracker(db);
  const outbox = new NotificationOutboxEngine(db);

  // STEP 1: User Registration & Session Lifecycle
  process.stdout.write('[1/12] Testing User Auth & PBKDF2 Password Hashing... ');
  const userId = crypto.randomUUID();
  const { salt, hash } = hashPassword('Secur3P@ssw0rd!');
  if (!verifyPassword('Secur3P@ssw0rd!', salt, hash)) throw new Error('Password verification failed');

  db.prepare(`
    INSERT INTO users (id, email, password_hash, password_salt, display_name)
    VALUES (?, 'smoke@example.com', ?, ?, 'Smoke Tester')
  `).run(userId, hash, salt);

  const session = createSession(db, userId);
  const user = validateSessionToken(db, session.token);
  if (!user || user.email !== 'smoke@example.com') throw new Error('Session validation failed');
  console.log('PASSED ✅');

  // STEP 2: SSRF & IP Pinning Verification
  process.stdout.write('[2/12] Testing Multi-Layer SSRF & IP Validation... ');
  const loopback = validatePublicIp('127.0.0.1');
  const metadata = validatePublicIp('169.254.169.254');
  const publicIp = validatePublicIp('8.8.8.8');
  if (loopback.valid || metadata.valid || !publicIp.valid) throw new Error('SSRF IP validation rule breach');
  console.log('PASSED ✅');

  // STEP 3: Canonical Capture Configuration & Fingerprinting
  process.stdout.write('[3/12] Testing Canonical Fingerprint & Cross-Field Schema... ');
  const config = computeCaptureFingerprint({
    engine: 'http_dom',
    viewport: { width: 1280, height: 720 },
  });
  if (!config.fingerprint || config.parsed.engine !== 'http_dom') throw new Error('Config schema failed');
  console.log('PASSED ✅');

  // STEP 4: Target & Monitor Creation
  process.stdout.write('[4/12] Creating Target & Subscription in SQLite... ');
  const targetId = crypto.randomUUID();
  const targetUrl = 'fixture://stable-clean';
  db.prepare(`
    INSERT INTO targets (id, canonical_url, safe_hostname, origin)
    VALUES (?, ?, 'fixture-host', 'fixture://local')
  `).run(targetId, targetUrl);

  const subId = crypto.randomUUID();
  db.prepare(`
    INSERT INTO subscriptions (
      id, user_id, target_id, name, interval_minutes, next_check_at,
      capture_config, capture_fingerprint, sensitivity
    ) VALUES (?, ?, ?, 'Smoke Monitor', 60, datetime('now'), ?, ?, 'balanced')
  `).run(subId, userId, targetId, config.canonicalJson, config.fingerprint);

  db.prepare('INSERT INTO sub_state (subscription_id) VALUES (?)').run(subId);
  console.log('PASSED ✅');

  // STEP 5: Initial Baseline Snapshot (Version 1)
  process.stdout.write('[5/12] Executing Initial Capture & Baseline Commit (v1)... ');
  const cap1 = await deduplicator.executeOrShareCapture(targetId, targetUrl, config.parsed);
  if (cap1.classification.outcome !== 'OK' || !cap1.observation) throw new Error('Initial capture failed');

  const v1Outcome = vm.evaluateSubscription(subId, cap1.observation);
  if (!v1Outcome.isInitialBaseline || v1Outcome.version?.version_number !== 1) {
    throw new Error('Baseline v1 not established');
  }
  console.log('PASSED ✅');

  // STEP 6: Repeated Capture on Unchanged Page (Zero new versions)
  process.stdout.write('[6/12] Verifying Zero New Versions on Repeated Clean Check... ');
  const cap2 = await deduplicator.executeOrShareCapture(targetId, targetUrl, config.parsed);
  const vRepeatOutcome = vm.evaluateSubscription(subId, cap2.observation!);
  if (vRepeatOutcome.changeDetected) throw new Error('False change detected on unchanged page');

  const versionsCount = db.prepare('SELECT count(*) as c FROM monitor_versions WHERE subscription_id = ?').get(subId) as { c: number };
  if (versionsCount.c !== 1) throw new Error('Unchanged check created duplicate version');
  console.log('PASSED ✅');

  // STEP 7: Simulating Meaningful Page Modification
  process.stdout.write('[7/12] Mutating Target Fixture & Confirming Version 2... ');
  setFixtureOverride('stable-clean', {
    html: FIXTURES['content-modified'].html,
  });

  // Force a fresh observation by bypassing the 15s in-memory deduplicator for the mutation
  const { executeCapture } = await import('../src/server/core/capture/capture-engine.js');
  const freshCapture = await executeCapture(targetUrl, config.parsed);
  const obsId = crypto.randomUUID();
  db.prepare(`
    INSERT INTO observations (
      id, target_id, engine_used, capture_fingerprint, rendering_fingerprint,
      final_url, http_status, sanitized_dom, raw_text, subresource_count
    ) VALUES (?, ?, 'http_dom', ?, '{}', ?, 200, ?, ?, 0)
  `).run(obsId, targetId, config.fingerprint, targetUrl, freshCapture.capture!.sanitizedDom, freshCapture.capture!.rawText);

  const mutatedObs = db.prepare('SELECT * FROM observations WHERE id = ?').get(obsId) as any;
  const v2Outcome = vm.evaluateSubscription(subId, mutatedObs);

  if (!v2Outcome.changeDetected || v2Outcome.version?.version_number !== 2) {
    throw new Error('Confirmed change did not increment version to v2');
  }
  console.log('PASSED ✅');

  // STEP 8: Outbox Notification & Composite Idempotency
  process.stdout.write('[8/12] Testing Outbox Dispatch & Channel-Independent Idempotency... ');
  const changeEvent = db.prepare('SELECT id FROM change_events WHERE subscription_id = ? AND current_version_id = ?').get(subId, v2Outcome.version!.id) as any;

  const inAppNotif = outbox.enqueueNotification(userId, changeEvent.id, 'in_app', { summary: 'V2 released' });
  const discordNotif = outbox.enqueueNotification(userId, changeEvent.id, 'discord', { summary: 'V2 released' });
  const dupDiscord = outbox.enqueueNotification(userId, changeEvent.id, 'discord', { summary: 'V2 released again' });

  if (!inAppNotif.enqueued || !discordNotif.enqueued) throw new Error('Multi-channel outbox enqueue failed');
  if (dupDiscord.enqueued) throw new Error('Duplicate notification was not suppressed by idempotency');

  const processedInApp = await outbox.processRecord(inAppNotif.outboxId);
  if (processedInApp.status !== 'RECORDED_IN_APP') throw new Error('In-app state transition failed');
  console.log('PASSED ✅');

  // STEP 9: 3-Failure Outage Flow
  process.stdout.write('[9/12] Verifying 3-Consecutive-Failure Outage Flow (DOWN Event)... ');
  ft.handleCheckOutcome(subId, 'ERROR', 'HTTP_500_SERVER_ERROR');
  ft.handleCheckOutcome(subId, 'ERROR', 'HTTP_500_SERVER_ERROR');
  const downResult = ft.handleCheckOutcome(subId, 'ERROR', 'HTTP_500_SERVER_ERROR');

  if (!downResult.downEventEmitted || !downResult.isCurrentlyDown) {
    throw new Error('3 consecutive failures failed to trigger DOWN event');
  }
  console.log('PASSED ✅');

  // STEP 10: Service Recovery Flow
  process.stdout.write('[10/12] Verifying Service Recovery Flow (RECOVERED Event)... ');
  const recResult = ft.handleCheckOutcome(subId, 'OK');
  if (!recResult.recoveredEventEmitted || recResult.isCurrentlyDown) {
    throw new Error('Recovery failed to trigger RECOVERED event');
  }
  console.log('PASSED ✅');

  // STEP 11: Observation Retention vs Confirmed Version Survival
  process.stdout.write('[11/12] Testing 30-Day Unreferenced Capture Purge & Version Survival... ');
  // Insert unreferenced old observation
  const oldGarbageId = crypto.randomUUID();
  db.prepare(`
    INSERT INTO observations (
      id, target_id, engine_used, capture_fingerprint, rendering_fingerprint,
      final_url, http_status, sanitized_dom, raw_text, subresource_count, captured_at
    ) VALUES (?, ?, 'http_dom', 'f', '{}', 'url', 200, 'dom', 'text', 0, datetime('now', '-35 days'))
  `).run(oldGarbageId, targetId);

  const deleted = vm.cleanupUnreferencedObservations(30);
  if (deleted < 1) throw new Error('Failed to delete unreferenced old capture');

  // Verify confirmed versions 1 and 2 still exist
  const versionsLeft = db.prepare('SELECT id FROM monitor_versions WHERE subscription_id = ?').all(subId);
  if (versionsLeft.length !== 2) throw new Error('Confirmed versions were inadvertently purged');
  console.log('PASSED ✅');

  // STEP 12: Explicit User Monitor Deletion Workflow
  process.stdout.write('[12/12] Testing Explicit Cascade Deletion Workflow... ');
  db.prepare('DELETE FROM subscriptions WHERE id = ? AND user_id = ?').run(subId, userId);

  const subCheck = db.prepare('SELECT id FROM subscriptions WHERE id = ?').get(subId);
  const versionCheck = db.prepare('SELECT id FROM monitor_versions WHERE subscription_id = ?').all(subId);
  const stateCheck = db.prepare('SELECT subscription_id FROM sub_state WHERE subscription_id = ?').get(subId);

  if (subCheck || versionCheck.length > 0 || stateCheck) {
    throw new Error('Cascade deletion failed to clean up all subscription resources');
  }
  console.log('PASSED ✅');

  clearFixtureOverrides();
  db.close();

  console.log('\n================================================================');
  console.log('  ALL 12/12 SMOKE CHECKS PASSED SUCCESSFULLY! [AH Verified]');
  console.log('================================================================\n');
}

runSmokeTests().catch(err => {
  console.error('\n❌ Smoke test failed:', err);
  process.exit(1);
});
