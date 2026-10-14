import Database from 'better-sqlite3';
import crypto from 'crypto';

export interface DigestSummary {
  userId: string;
  totalEvents: number;
  changesCount: number;
  outagesCount: number;
  recoveriesCount: number;
  summaryText: string;
  eventIds: string[];
}

export class DailyDigestEngine {
  private db: Database.Database;

  constructor(db: Database.Database) {
    this.db = db;
  }

  generateUserDigest(userId: string, hours = 24): DigestSummary | null {
    const events = this.db.prepare(`
      SELECT ce.id, ce.event_type, ce.summary, ce.created_at, s.name as monitor_name
      FROM change_events ce
      JOIN subscriptions s ON ce.subscription_id = s.id
      WHERE s.user_id = ?
        AND datetime(ce.created_at) > datetime('now', '-' || ? || ' hours')
      ORDER BY ce.created_at ASC
    `).all(userId, hours) as Array<{
      id: string;
      event_type: 'CHANGE' | 'DOWN' | 'RECOVERED' | 'DIGEST';
      summary: string;
      created_at: string;
      monitor_name: string;
    }>;

    if (events.length === 0) {
      return null;
    }

    let changesCount = 0;
    let outagesCount = 0;
    let recoveriesCount = 0;
    const lines: string[] = [];

    for (const ev of events) {
      if (ev.event_type === 'CHANGE') changesCount++;
      else if (ev.event_type === 'DOWN') outagesCount++;
      else if (ev.event_type === 'RECOVERED') recoveriesCount++;

      lines.push(`• [${ev.event_type}] ${ev.monitor_name}: ${ev.summary}`);
    }

    const summaryText = `Daily ChangeWatch Digest (Past ${hours}h):\n` +
      `Total Events: ${events.length} (${changesCount} changes, ${outagesCount} outages, ${recoveriesCount} recoveries)\n\n` +
      lines.join('\n');

    return {
      userId,
      totalEvents: events.length,
      changesCount,
      outagesCount,
      recoveriesCount,
      summaryText,
      eventIds: events.map(e => e.id),
    };
  }
}
