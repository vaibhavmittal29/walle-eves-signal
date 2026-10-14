import Database from 'better-sqlite3';

export class AlertCooldownTracker {
  private db: Database.Database;
  private cooldownHours: number;

  constructor(db: Database.Database, cooldownHours = 6) {
    this.db = db;
    this.cooldownHours = cooldownHours;
  }

  /**
   * Checks if an alert is currently suppressed under the 6-hour cooldown window.
   */
  isAlertSuppressed(subscriptionId: string, currentContentHash: string): boolean {
    const row = this.db.prepare(`
      SELECT last_alerted_hash, last_alert_sent_at,
             datetime(last_alert_sent_at, '+' || ? || ' hours') > datetime('now') as in_cooldown
      FROM sub_state
      WHERE subscription_id = ?
    `).get(this.cooldownHours, subscriptionId) as {
      last_alerted_hash: string | null;
      last_alert_sent_at: string | null;
      in_cooldown: number;
    } | undefined;

    if (!row || !row.last_alert_sent_at) {
      return false; // Never alerted before
    }

    // If within cooldown period and alerted hash is identical or similar
    if (Boolean(row.in_cooldown)) {
      return true;
    }

    return false;
  }

  /**
   * Records that an alert was dispatched for a given content hash.
   */
  recordAlertDispatched(subscriptionId: string, contentHash: string): void {
    this.db.prepare(`
      UPDATE sub_state
      SET last_alert_sent_at = datetime('now'),
          last_alerted_hash = ?
      WHERE subscription_id = ?
    `).run(contentHash, subscriptionId);
  }
}
