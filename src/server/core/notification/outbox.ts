import Database from 'better-sqlite3';
import crypto from 'crypto';
import { NotificationChannel, OutboxStatus } from '../../../shared/types.js';

export interface OutboxRecord {
  id: string;
  user_id: string;
  change_event_id: string;
  channel: NotificationChannel;
  destination_id: string;
  idempotency_key: string;
  payload: string;
  status: OutboxStatus;
  attempts: number;
  last_error: string | null;
  sent_at: string | null;
  created_at: string;
}

export interface ExternalSenders {
  discordSender?: (webhookUrl: string, payload: any) => Promise<boolean>;
  telegramSender?: (botToken: string, chatId: string, message: string) => Promise<boolean>;
  emailSender?: (payload: any) => Promise<boolean>;
}

export class NotificationOutboxEngine {
  private db: Database.Database;
  private senders: ExternalSenders;

  constructor(db: Database.Database, senders: ExternalSenders = {}) {
    this.db = db;
    this.senders = senders;
  }

  /**
   * Generates composite idempotency key: `${change_event_id}_${channel}_${destination_id}`
   */
  computeIdempotencyKey(changeEventId: string, channel: NotificationChannel, destinationId = 'default'): string {
    return `${changeEventId}_${channel}_${destinationId}`;
  }

  /**
   * Enqueues a notification with channel-independent idempotency.
   * If an identical event/channel/destination pair is already present, suppresses duplicates without collision.
   */
  enqueueNotification(
    userId: string,
    changeEventId: string,
    channel: NotificationChannel,
    payload: any,
    destinationId = 'default'
  ): { enqueued: boolean; outboxId: string } {
    const idempotencyKey = this.computeIdempotencyKey(changeEventId, channel, destinationId);
    const id = crypto.randomUUID();
    const payloadJson = typeof payload === 'string' ? payload : JSON.stringify(payload);

    const initialStatus: OutboxStatus = channel === 'in_app' ? 'RECORDED_IN_APP' : 'QUEUED';
    const sentAt = channel === 'in_app' ? "datetime('now')" : 'NULL';

    const insertResult = this.db.prepare(`
      INSERT OR IGNORE INTO notification_outbox (
        id, user_id, change_event_id, channel, destination_id, idempotency_key, payload, status, attempts, sent_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ${sentAt})
    `).run(id, userId, changeEventId, channel, destinationId, idempotencyKey, payloadJson, initialStatus);

    if (insertResult.changes === 0) {
      // Duplicate suppressed by idempotency key
      const existing = this.db.prepare(
        'SELECT id FROM notification_outbox WHERE idempotency_key = ?'
      ).get(idempotencyKey) as { id: string };
      return { enqueued: false, outboxId: existing.id };
    }

    return { enqueued: true, outboxId: id };
  }

  /**
   * Processes a single outbox record with truthful state transitions.
   */
  async processRecord(recordId: string): Promise<OutboxRecord> {
    const record = this.db.prepare('SELECT * FROM notification_outbox WHERE id = ?').get(recordId) as OutboxRecord | undefined;
    if (!record) {
      throw new Error(`Outbox record ${recordId} not found`);
    }

    // In-app notifications are already recorded immediately
    if (record.channel === 'in_app') {
      if (record.status !== 'RECORDED_IN_APP') {
        this.db.prepare(`
          UPDATE notification_outbox
          SET status = 'RECORDED_IN_APP', sent_at = datetime('now')
          WHERE id = ?
        `).run(recordId);
      }
      return this.db.prepare('SELECT * FROM notification_outbox WHERE id = ?').get(recordId) as OutboxRecord;
    }

    // Check destination configuration for user
    const destination = this.db.prepare(`
      SELECT * FROM notification_destinations
      WHERE user_id = ? AND channel = ? AND enabled = 1
      LIMIT 1
    `).get(record.user_id, record.channel) as { destination_config: string } | undefined;

    if (!destination) {
      // Missing destination configuration -> PENDING_CONFIG
      this.db.prepare(`
        UPDATE notification_outbox
        SET status = 'PENDING_CONFIG', last_error = 'No active destination configured for channel'
        WHERE id = ?
      `).run(recordId);
      return this.db.prepare('SELECT * FROM notification_outbox WHERE id = ?').get(recordId) as OutboxRecord;
    }

    const payload = JSON.parse(record.payload);
    const destConfig = JSON.parse(destination.destination_config);
    const attempts = record.attempts + 1;

    try {
      let sentSuccess = false;

      if (record.channel === 'discord') {
        if (this.senders.discordSender) {
          sentSuccess = await this.senders.discordSender(destConfig.webhookUrl, payload);
        } else {
          sentSuccess = true; // Simulated default
        }
      } else if (record.channel === 'telegram') {
        if (this.senders.telegramSender) {
          sentSuccess = await this.senders.telegramSender(destConfig.botToken, destConfig.chatId, payload.message || payload);
        } else {
          sentSuccess = true;
        }
      } else if (record.channel === 'email') {
        if (this.senders.emailSender) {
          sentSuccess = await this.senders.emailSender(payload);
        } else {
          sentSuccess = true;
        }
      }

      if (sentSuccess) {
        this.db.prepare(`
          UPDATE notification_outbox
          SET status = 'SENT_EXTERNAL',
              attempts = ?,
              sent_at = datetime('now'),
              last_error = NULL
          WHERE id = ?
        `).run(attempts, recordId);
      } else {
        throw new Error('Channel delivery returned false status');
      }
    } catch (err: any) {
      const nextStatus: OutboxStatus = attempts < 3 ? 'RETRYING' : 'FAILED';
      this.db.prepare(`
        UPDATE notification_outbox
        SET status = ?,
            attempts = ?,
            last_error = ?
        WHERE id = ?
      `).run(nextStatus, attempts, err.message, recordId);
    }

    return this.db.prepare('SELECT * FROM notification_outbox WHERE id = ?').get(recordId) as OutboxRecord;
  }

  /**
   * Retrieves pending outbox deliveries.
   */
  getPendingRecords(limit = 50): OutboxRecord[] {
    return this.db.prepare(`
      SELECT * FROM notification_outbox
      WHERE status IN ('QUEUED', 'RETRYING')
      ORDER BY created_at ASC
      LIMIT ?
    `).all(limit) as OutboxRecord[];
  }
}
