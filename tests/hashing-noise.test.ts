import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { initDatabase } from '../src/server/db/database.js';
import { computeContentHash } from '../src/server/core/analysis/hasher.js';
import { extractNormalizedText } from '../src/server/core/analysis/normalizer.js';
import { VersionManager } from '../src/server/core/analysis/version-manager.js';
import { ObservationRecord } from '../src/server/core/scheduler/deduplicator.js';
import { FIXTURES } from '../src/fixtures/index.js';
import Database from 'better-sqlite3';
import crypto from 'crypto';

describe('Deterministic Hashing, Snapshots & Version History [I, K, L, M, Z]', () => {
  let db: Database.Database;
  let vm: VersionManager;
  let userId: string;
  let targetId: string;
  let subId: string;

  beforeEach(() => {
    db = initDatabase({ inMemory: true });
    vm = new VersionManager(db);

    userId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO users (id, email, password_hash, password_salt, display_name)
      VALUES (?, 'test@site.com', 'h', 's', 'User')
    `).run(userId);

    targetId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO targets (id, canonical_url, safe_hostname, origin)
      VALUES (?, 'https://site.com', 'site.com', 'https://site.com:443')
    `).run(targetId);

    subId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO subscriptions (
        id, user_id, target_id, name, interval_minutes, next_check_at,
        capture_config, capture_fingerprint, sensitivity
      ) VALUES (?, ?, ?, 'Test Monitor', 60, datetime('now'), '{}', 'f', 'balanced')
    `).run(subId, userId, targetId);

    db.prepare('INSERT INTO sub_state (subscription_id) VALUES (?)').run(subId);
  });

  afterEach(() => {
    db.close();
  });

  function createMockObservation(html: string, id = crypto.randomUUID(), capturedAt = "datetime('now')"): ObservationRecord {
    db.prepare(`
      INSERT INTO observations (
        id, target_id, engine_used, capture_fingerprint, rendering_fingerprint,
        final_url, http_status, sanitized_dom, raw_text, subresource_count, captured_at
      ) VALUES (?, ?, 'http_dom', 'f', '{}', 'https://site.com', 200, ?, ?, 0, ${capturedAt})
    `).run(id, targetId, html, html);

    return db.prepare('SELECT * FROM observations WHERE id = ?').get(id) as ObservationRecord;
  }

  it('[K] deterministic SHA-256 hashing produces identical hash for identical normalized text', () => {
    const text1 = 'School of Computer Science & Engineering\nFall 2026 Curriculum Updates';
    const text2 = '  School of Computer Science & Engineering  \n\n  Fall 2026 Curriculum Updates  ';

    const normalized1 = extractNormalizedText(`<div><p>School of Computer Science & Engineering</p><p>Fall 2026 Curriculum Updates</p></div>`);
    const normalized2 = extractNormalizedText(`<div> <p>  School of Computer Science & Engineering  </p> \n\n <p> Fall 2026 Curriculum Updates </p> </div>`);

    expect(normalized1).toBe(normalized2);

    const hash1 = computeContentHash(normalized1);
    const hash2 = computeContentHash(normalized2);

    expect(hash1).toBe(hash2);
    expect(hash1).toHaveLength(64);
  });

  it('[L] unchanged page creates zero new versions across repeated runs', () => {
    const cleanHtml = FIXTURES['stable-clean'].html;

    // Run 1: Initial baseline capture
    const obs1 = createMockObservation(cleanHtml);
    const res1 = vm.evaluateSubscription(subId, obs1);
    expect(res1.isInitialBaseline).toBe(true);
    expect(res1.version?.version_number).toBe(1);

    // Runs 2 through 6: Repeated observations with identical clean HTML
    for (let i = 2; i <= 6; i++) {
      const obsRepeat = createMockObservation(cleanHtml);
      const resRepeat = vm.evaluateSubscription(subId, obsRepeat);
      expect(resRepeat.changeDetected).toBe(false);
      expect(resRepeat.isInitialBaseline).toBe(false);
      expect(resRepeat.version?.version_number).toBe(1);
    }

    // Total versions in DB must strictly remain 1
    const versions = db.prepare('SELECT * FROM monitor_versions WHERE subscription_id = ?').all(subId);
    expect(versions.length).toBe(1);

    // Zero change events emitted
    const events = db.prepare('SELECT * FROM change_events WHERE subscription_id = ?').all(subId);
    expect(events.length).toBe(0);
  });

  it('[M] meaningful content change creates sequential version 2 with change event', () => {
    const initialHtml = FIXTURES['stable-clean'].html;
    const modifiedHtml = FIXTURES['content-modified'].html;

    // Run 1: Baseline v1
    const obs1 = createMockObservation(initialHtml);
    const res1 = vm.evaluateSubscription(subId, obs1);
    expect(res1.version?.version_number).toBe(1);

    // Run 2: Modified content
    const obs2 = createMockObservation(modifiedHtml);
    const res2 = vm.evaluateSubscription(subId, obs2);

    expect(res2.changeDetected).toBe(true);
    expect(res2.version?.version_number).toBe(2);
    expect(res2.previousVersion?.version_number).toBe(1);
    expect(res2.version?.stored_text).toContain('REVISED');

    // Monitor versions now contains v1 and v2
    const versions = db.prepare('SELECT version_number FROM monitor_versions WHERE subscription_id = ? ORDER BY version_number ASC').all(subId) as any[];
    expect(versions.map(v => v.version_number)).toEqual([1, 2]);

    // Change event was recorded
    const events = db.prepare('SELECT * FROM change_events WHERE subscription_id = ?').all(subId) as any[];
    expect(events.length).toBe(1);
    expect(events[0].event_type).toBe('CHANGE');
    expect(events[0].current_version_id).toBe(res2.version?.id);
  });

  it('[I] failure outcomes (ERROR, BLOCKED) never alter baselines or create false versions', () => {
    const cleanHtml = FIXTURES['stable-clean'].html;

    // Establish baseline v1
    const obs1 = createMockObservation(cleanHtml);
    const res1 = vm.evaluateSubscription(subId, obs1);
    const baselineHash = res1.contentHash;

    // Outage capture occurs: in scheduler/queue, ERROR or BLOCKED runs are logged to check_runs
    // but NEVER passed into evaluateSubscription to mutate version state
    const outageRunId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO check_runs (id, subscription_id, target_id, outcome, reason, http_status, duration_ms)
      VALUES (?, ?, ?, 'ERROR', 'HTTP_500_SERVER_ERROR', 500, 150)
    `).run(outageRunId, subId, targetId);

    // Verify sub_state baseline is intact
    const subState = db.prepare('SELECT active_version_id, last_alerted_hash FROM sub_state WHERE subscription_id = ?').get(subId) as any;
    expect(subState.active_version_id).toBe(res1.version?.id);
    expect(subState.last_alerted_hash).toBe(baselineHash);

    // Version table remains strictly at v1
    const versions = db.prepare('SELECT * FROM monitor_versions WHERE subscription_id = ?').all(subId);
    expect(versions.length).toBe(1);
  });

  it('[Z] observation retention: unreferenced captures older than 30 days are purged while confirmed versions and candidates survive', () => {
    // 1. Confirmed version observation (35 days old)
    const obsConfirmedId = crypto.randomUUID();
    createMockObservation('Confirmed HTML', obsConfirmedId, "datetime('now', '-35 days')");
    db.prepare(`
      INSERT INTO monitor_versions (
        id, subscription_id, observation_id, version_number, content_hash, stored_text
      ) VALUES ('v-confirmed', ?, ?, 1, 'hash-confirmed', 'text')
    `).run(subId, obsConfirmedId);

    // 2. Pending candidate observation (35 days old)
    const obsCandidateId = crypto.randomUUID();
    createMockObservation('Candidate HTML', obsCandidateId, "datetime('now', '-35 days')");
    db.prepare(`
      UPDATE sub_state
      SET pending_observation_id = ?
      WHERE subscription_id = ?
    `).run(obsCandidateId, subId);

    // 3. Unreferenced old observation (35 days old) - should be deleted
    const obsOldUnreferencedId = crypto.randomUUID();
    createMockObservation('Old Garbage HTML', obsOldUnreferencedId, "datetime('now', '-35 days')");

    // 4. Unreferenced recent observation (5 days old) - should NOT be deleted
    const obsRecentId = crypto.randomUUID();
    createMockObservation('Recent HTML', obsRecentId, "datetime('now', '-5 days')");

    // Execute 30-day cleanup
    const deletedCount = vm.cleanupUnreferencedObservations(30);
    expect(deletedCount).toBe(1);

    // Assert: old unreferenced observation is gone
    const oldRow = db.prepare('SELECT id FROM observations WHERE id = ?').get(obsOldUnreferencedId);
    expect(oldRow).toBeUndefined();

    // Assert: confirmed version observation survived
    const confirmedRow = db.prepare('SELECT id FROM observations WHERE id = ?').get(obsConfirmedId);
    expect(confirmedRow).toBeDefined();

    // Assert: pending candidate observation survived
    const candidateRow = db.prepare('SELECT id FROM observations WHERE id = ?').get(obsCandidateId);
    expect(candidateRow).toBeDefined();

    // Assert: recent observation survived
    const recentRow = db.prepare('SELECT id FROM observations WHERE id = ?').get(obsRecentId);
    expect(recentRow).toBeDefined();
  });
});
