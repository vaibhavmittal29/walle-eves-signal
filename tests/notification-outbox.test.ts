import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { initDatabase } from '../src/server/db/database.js';
import { NotificationOutboxEngine } from '../src/server/core/notification/outbox.js';
import { DailyDigestEngine } from '../src/server/core/notification/digest.js';
import Database from 'better-sqlite3';
import crypto from 'crypto';

describe('Notification Outbox, Truthful States & Channel Idempotency [V, W]', () => {
  let db: Database.Database;
  let outbox: NotificationOutboxEngine;
  let digest: DailyDigestEngine;
  let userId: string;
  let subId: string;
  let changeEventId: string;

  beforeEach(() => {
    db = initDatabase({ inMemory: true });
    outbox = new NotificationOutboxEngine(db);
    digest = new DailyDigestEngine(db);

    userId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO users (id, email, password_hash, password_salt, display_name)
      VALUES (?, 'user@site.com', 'h', 's', 'User')
    `).run(userId);

    const targetId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO targets (id, canonical_url, safe_hostname, origin)
      VALUES (?, 'https://site.com', 'site.com', 'https://site.com:443')
    `).run(targetId);

    subId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO subscriptions (
        id, user_id, target_id, name, interval_minutes, next_check_at,
        capture_config, capture_fingerprint
      ) VALUES (?, ?, ?, 'Sub 1', 60, datetime('now'), '{}', 'f')
    `).run(subId, userId, targetId);

    const obsId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO observations (
        id, target_id, engine_used, capture_fingerprint, rendering_fingerprint,
        final_url, http_status, sanitized_dom, raw_text, subresource_count
      ) VALUES (?, ?, 'http_dom', 'f', '{}', 'https://site.com', 200, 'dom', 'text', 0)
    `).run(obsId, targetId);

    const versionId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO monitor_versions (
        id, subscription_id, observation_id, version_number, content_hash, stored_text
      ) VALUES (?, ?, ?, 1, 'hash1', 'text1')
    `).run(versionId, subId, obsId);

    changeEventId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO change_events (id, subscription_id, current_version_id, event_type, summary)
      VALUES (?, ?, ?, 'CHANGE', 'Content changed on page')
    `).run(changeEventId, subId, versionId);
  });

  afterEach(() => {
    db.close();
  });

  it('[W] composite idempotency key enables simultaneous multi-channel deliveries without cross-channel collision or duplicate alerts', () => {
    // 1. Enqueue to In-App, Discord, and Telegram for the SAME change event
    const inApp = outbox.enqueueNotification(userId, changeEventId, 'in_app', { text: 'In-app alert' });
    const discord = outbox.enqueueNotification(userId, changeEventId, 'discord', { text: 'Discord alert' });
    const telegram = outbox.enqueueNotification(userId, changeEventId, 'telegram', { text: 'Telegram alert' });

    expect(inApp.enqueued).toBe(true);
    expect(discord.enqueued).toBe(true);
    expect(telegram.enqueued).toBe(true);

    // Assert composite keys are completely independent:
    // `${change_event_id}_in_app_default` vs `${change_event_id}_discord_default`
    expect(inApp.outboxId).not.toBe(discord.outboxId);

    // 2. Duplicate attempt to enqueue the exact same event + channel + destination
    const duplicateDiscord = outbox.enqueueNotification(userId, changeEventId, 'discord', { text: 'Discord alert again' });
    expect(duplicateDiscord.enqueued).toBe(false); // Suppressed by idempotency!
    expect(duplicateDiscord.outboxId).toBe(discord.outboxId); // Points to existing record

    // Verify row count in DB for discord channel is strictly 1
    const discordRows = db.prepare("SELECT * FROM notification_outbox WHERE change_event_id = ? AND channel = 'discord'").all(changeEventId);
    expect(discordRows.length).toBe(1);
  });

  it('[V] accurately transitions through truthful outbox states (RECORDED_IN_APP, PENDING_CONFIG, SENT_EXTERNAL, RETRYING, FAILED)', async () => {
    // 1. in_app channel transitions immediately to RECORDED_IN_APP
    const inAppRes = outbox.enqueueNotification(userId, changeEventId, 'in_app', { msg: 'Test' });
    const inAppRecord = await outbox.processRecord(inAppRes.outboxId);
    expect(inAppRecord.status).toBe('RECORDED_IN_APP');
    expect(inAppRecord.sent_at).not.toBeNull();

    // 2. Unconfigured external channel transitions to PENDING_CONFIG
    const discordRes = outbox.enqueueNotification(userId, changeEventId, 'discord', { msg: 'Discord test' });
    const pendingRecord = await outbox.processRecord(discordRes.outboxId);
    expect(pendingRecord.status).toBe('PENDING_CONFIG');
    expect(pendingRecord.last_error).toContain('No active destination configured');

    // 3. Configure Discord destination with successful sender -> SENT_EXTERNAL
    const destId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO notification_destinations (id, user_id, channel, destination_config, enabled)
      VALUES (?, ?, 'discord', '{"webhookUrl": "https://discord.com/api/webhooks/mock"}', 1)
    `).run(destId, userId);

    const outboxWithSuccess = new NotificationOutboxEngine(db, {
      discordSender: async () => true,
    });

    const successRes = outboxWithSuccess.enqueueNotification(userId, changeEventId, 'discord', { msg: 'Hello' }, 'dest_custom');
    const sentRecord = await outboxWithSuccess.processRecord(successRes.outboxId);
    expect(sentRecord.status).toBe('SENT_EXTERNAL');
    expect(sentRecord.sent_at).not.toBeNull();

    // 4. Failing sender: attempts 1 and 2 transition to RETRYING, attempt 3 transitions to FAILED
    const outboxWithFailure = new NotificationOutboxEngine(db, {
      discordSender: async () => {
        throw new Error('Connection refused by remote server');
      },
    });

    const failEventId = crypto.randomUUID();
    const version2Id = crypto.randomUUID();
    db.prepare(`
      INSERT INTO monitor_versions (
        id, subscription_id, observation_id, version_number, content_hash, stored_text
      ) VALUES (?, ?, (SELECT id FROM observations LIMIT 1), 2, 'hash2', 'text2')
    `).run(version2Id, subId);

    db.prepare(`
      INSERT INTO change_events (id, subscription_id, current_version_id, event_type, summary)
      VALUES (?, ?, ?, 'CHANGE', 'Another change')
    `).run(failEventId, subId, version2Id);

    const failRes = outboxWithFailure.enqueueNotification(userId, failEventId, 'discord', { msg: 'Fail' });

    // Attempt 1 -> RETRYING
    const rec1 = await outboxWithFailure.processRecord(failRes.outboxId);
    expect(rec1.status).toBe('RETRYING');
    expect(rec1.attempts).toBe(1);

    // Attempt 2 -> RETRYING
    const rec2 = await outboxWithFailure.processRecord(failRes.outboxId);
    expect(rec2.status).toBe('RETRYING');
    expect(rec2.attempts).toBe(2);

    // Attempt 3 -> FAILED (max attempts reached)
    const rec3 = await outboxWithFailure.processRecord(failRes.outboxId);
    expect(rec3.status).toBe('FAILED');
    expect(rec3.attempts).toBe(3);
    expect(rec3.last_error).toContain('Connection refused');
  });

  it('generates daily digest aggregating user changes, outages, and recoveries', () => {
    // Insert additional DOWN and RECOVERED events
    db.prepare(`
      INSERT INTO change_events (id, subscription_id, event_type, summary)
      VALUES ('ev-down', ?, 'DOWN', '3 consecutive failures')
    `).run(subId);

    db.prepare(`
      INSERT INTO change_events (id, subscription_id, event_type, summary)
      VALUES ('ev-rec', ?, 'RECOVERED', 'Service back online')
    `).run(subId);

    const digestSummary = digest.generateUserDigest(userId, 24);
    expect(digestSummary).not.toBeNull();
    expect(digestSummary?.totalEvents).toBe(3);
    expect(digestSummary?.changesCount).toBe(1);
    expect(digestSummary?.outagesCount).toBe(1);
    expect(digestSummary?.recoveriesCount).toBe(1);
    expect(digestSummary?.summaryText).toContain('Total Events: 3');
  });
});
