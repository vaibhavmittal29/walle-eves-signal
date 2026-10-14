import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { initDatabase } from '../src/server/db/database.js';
import { extractNormalizedText, applyNoiseFilterRules } from '../src/server/core/analysis/normalizer.js';
import { detectUnstableLines } from '../src/server/core/analysis/volatility.js';
import { AlertCooldownTracker } from '../src/server/core/analysis/cooldown.js';
import { FailureTracker } from '../src/server/core/analysis/failure-tracker.js';
import { VersionManager } from '../src/server/core/analysis/version-manager.js';
import { computeContentHash } from '../src/server/core/analysis/hasher.js';
import { ObservationRecord } from '../src/server/core/scheduler/deduplicator.js';
import { FIXTURES } from '../src/fixtures/index.js';
import Database from 'better-sqlite3';
import crypto from 'crypto';

describe('Noise Filters, Volatility, 2-Check Confirmation & Cooldown [J, N, O, P, Q]', () => {
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
      VALUES (?, 'u@test.com', 'h', 's', 'User')
    `).run(userId);

    targetId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO targets (id, canonical_url, safe_hostname, origin)
      VALUES (?, 'fixture://noisy-timestamps', 'fixture-host', 'fixture://local')
    `).run(targetId);

    subId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO subscriptions (
        id, user_id, target_id, name, interval_minutes, next_check_at,
        capture_config, capture_fingerprint, sensitivity
      ) VALUES (?, ?, ?, 'Sub Noise', 60, datetime('now'), '{}', 'f', 'low')
    `).run(subId, userId, targetId);

    db.prepare('INSERT INTO sub_state (subscription_id) VALUES (?)').run(subId);
  });

  afterEach(() => {
    db.close();
  });

  function createMockObservation(html: string, id = crypto.randomUUID()): ObservationRecord {
    db.prepare(`
      INSERT INTO observations (
        id, target_id, engine_used, capture_fingerprint, rendering_fingerprint,
        final_url, http_status, sanitized_dom, raw_text, subresource_count
      ) VALUES (?, ?, 'http_dom', 'f', '{}', 'https://site.com', 200, ?, ?, 0)
    `).run(id, targetId, html, html);

    return db.prepare('SELECT * FROM observations WHERE id = ?').get(id) as ObservationRecord;
  }

  it('[N] multi-format timestamp, visitor counter & token filters stabilize noisy pages', () => {
    const rawNoisy = FIXTURES['noisy-timestamps'].html;

    // Without noise filters: raw text contains mutating numbers, timestamps, and tokens
    const textUnfiltered = extractNormalizedText(rawNoisy);
    expect(textUnfiltered).toMatch(/\d{4}-\d{2}-\d{2}/);
    expect(textUnfiltered).toMatch(/Visitor #\d+/);
    expect(textUnfiltered).toMatch(/[0-9a-f]{8}-[0-9a-f]{4}/);

    // With noise filters enabled:
    const textFiltered = extractNormalizedText(rawNoisy, {
      noiseFilters: { timestamps: true, counters: true, tokens: true },
    });

    expect(textFiltered).not.toMatch(/\d{4}-\d{2}-\d{2}/);
    expect(textFiltered).toContain('[TIMESTAMP]');
    expect(textFiltered).toContain('[COUNTER]');
    expect(textFiltered).toContain('[TOKEN]');

    // Second simulated noisy capture with DIFFERENT timestamp, visitor count, and token:
    const rawNoisy2 = rawNoisy
      .replace('2026-10-14T12:38:46.124Z', '2026-10-14T13:45:10.999Z')
      .replace('48201', '48299')
      .replace('f9b8c2d1-4e7a-4290-b3fa-9d18e87491bb', '11223344-5566-7788-99aa-bbccddeeff00');

    const textFiltered2 = extractNormalizedText(rawNoisy2, {
      noiseFilters: { timestamps: true, counters: true, tokens: true },
    });

    // Content hashes match 100% despite volatile timestamps/counters/tokens!
    expect(computeContentHash(textFiltered)).toBe(computeContentHash(textFiltered2));
  });

  it('[O] volatility detector identifies unstable lines and suggests filters', () => {
    const textA = `Title: Main Server\nLast checked: 10:00 AM\nVisitors: 150\nStatus: Operational`;
    const textB = `Title: Main Server\nLast checked: 10:15 AM\nVisitors: 195\nStatus: Operational`;

    const result = detectUnstableLines(textA, textB);
    expect(result.unstableLines).toContain('Last checked: 10:00 AM');
    expect(result.unstableLines).toContain('Last checked: 10:15 AM');
    expect(result.isNoisy).toBe(false); // 2 of 4 lines changed = 50%, not > 70%
  });

  it('[Q] >70% volatility flags page as isNoisy and 6-hour cooldown suppresses repeat alerts', () => {
    // 1. High volatility test (>70% changed lines)
    const textStable = `Line 1: static\nLine 2: static\nLine 3: static\nLine 4: static\nLine 5: static\nLine 6: static\nLine 7: static\nLine 8: static\nLine 9: static\nLine 10: static`;
    const textMutated = `Line 1: changed\nLine 2: changed\nLine 3: changed\nLine 4: changed\nLine 5: changed\nLine 6: changed\nLine 7: changed\nLine 8: changed\nLine 9: static\nLine 10: static`;

    const highVolResult = detectUnstableLines(textStable, textMutated);
    expect(highVolResult.isNoisy).toBe(true);
    expect(highVolResult.volatilityPercentage).toBeGreaterThan(70);

    // 2. Alert Cooldown Tracker
    const tracker = new AlertCooldownTracker(db, 6);
    const hash = 'sample-hash-123';

    // Before alert: not suppressed
    expect(tracker.isAlertSuppressed(subId, hash)).toBe(false);

    // Record alert dispatched
    tracker.recordAlertDispatched(subId, hash);

    // Immediately after alert: suppressed by 6-hour cooldown!
    expect(tracker.isAlertSuppressed(subId, hash)).toBe(true);
  });

  it('[P] two-check confirmation protects candidate in sub_state and requires 2 matches before commit', () => {
    // Note: subscription has sensitivity: 'low' (requires 2 consecutive checks)
    const baselineHtml = FIXTURES['stable-clean'].html;
    const changedHtml = FIXTURES['content-modified'].html;

    // Check 1: Initial baseline
    const obs1 = createMockObservation(baselineHtml);
    const res1 = vm.evaluateSubscription(subId, obs1);
    expect(res1.isInitialBaseline).toBe(true);
    expect(res1.version?.version_number).toBe(1);

    // Check 2: First appearance of change -> candidate pending!
    const obs2 = createMockObservation(changedHtml);
    const res2 = vm.evaluateSubscription(subId, obs2);

    expect(res2.changeDetected).toBe(false);
    expect(res2.pendingConfirmation).toBe(true);

    // Verify sub_state holds pending_observation_id and candidate hash
    const state = db.prepare('SELECT pending_candidate_hash, pending_observation_id FROM sub_state WHERE subscription_id = ?').get(subId) as any;
    expect(state.pending_candidate_hash).toBe(res2.contentHash);
    expect(state.pending_observation_id).toBe(obs2.id);

    // Version table remains strictly at v1 (unconfirmed!)
    const versionsPending = db.prepare('SELECT * FROM monitor_versions WHERE subscription_id = ?').all(subId);
    expect(versionsPending.length).toBe(1);

    // Check 3: Second check confirms the exact same change!
    const obs3 = createMockObservation(changedHtml);
    const res3 = vm.evaluateSubscription(subId, obs3);

    expect(res3.changeDetected).toBe(true);
    expect(res3.version?.version_number).toBe(2);

    // Pending candidate cleared
    const stateAfter = db.prepare('SELECT pending_candidate_hash, pending_observation_id FROM sub_state WHERE subscription_id = ?').get(subId) as any;
    expect(stateAfter.pending_candidate_hash).toBeNull();
    expect(stateAfter.pending_observation_id).toBeNull();

    // Now version 2 is committed
    const versionsConfirmed = db.prepare('SELECT * FROM monitor_versions WHERE subscription_id = ?').all(subId);
    expect(versionsConfirmed.length).toBe(2);
  });

  it('[J] 3-failure outage & recovery alert flow', () => {
    const ft = new FailureTracker(db, 3);

    // Failure 1: increments consecutive_failures to 1 (no DOWN alert)
    const f1 = ft.handleCheckOutcome(subId, 'ERROR', 'HTTP_500_SERVER_ERROR');
    expect(f1.consecutiveFailures).toBe(1);
    expect(f1.isCurrentlyDown).toBe(false);
    expect(f1.downEventEmitted).toBe(false);

    // Failure 2: increments consecutive_failures to 2 (no DOWN alert)
    const f2 = ft.handleCheckOutcome(subId, 'ERROR', 'HTTP_500_SERVER_ERROR');
    expect(f2.consecutiveFailures).toBe(2);
    expect(f2.isCurrentlyDown).toBe(false);
    expect(f2.downEventEmitted).toBe(false);

    // Failure 3: reaches threshold -> triggers DOWN alert!
    const f3 = ft.handleCheckOutcome(subId, 'ERROR', 'HTTP_500_SERVER_ERROR');
    expect(f3.consecutiveFailures).toBe(3);
    expect(f3.isCurrentlyDown).toBe(true);
    expect(f3.downEventEmitted).toBe(true);

    // Verify DOWN event exists in change_events
    const downEvent = db.prepare("SELECT * FROM change_events WHERE subscription_id = ? AND event_type = 'DOWN'").get(subId) as any;
    expect(downEvent).toBeDefined();
    expect(downEvent.summary).toContain('3 consecutive failures');

    // Recovery: target returns OK -> triggers RECOVERED alert and resets counter!
    const rec = ft.handleCheckOutcome(subId, 'OK');
    expect(rec.consecutiveFailures).toBe(0);
    expect(rec.isCurrentlyDown).toBe(false);
    expect(rec.recoveredEventEmitted).toBe(true);

    // Verify RECOVERED event in change_events
    const recEvent = db.prepare("SELECT * FROM change_events WHERE subscription_id = ? AND event_type = 'RECOVERED'").get(subId) as any;
    expect(recEvent).toBeDefined();
    expect(recEvent.summary).toContain('Service recovered');
  });
});
