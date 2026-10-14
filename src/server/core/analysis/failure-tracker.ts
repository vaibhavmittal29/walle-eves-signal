import Database from 'better-sqlite3';
import crypto from 'crypto';
import { CheckOutcome } from '../../../shared/types.js';

export interface OutageStatusResult {
  consecutiveFailures: number;
  isCurrentlyDown: boolean;
  downEventEmitted: boolean;
  recoveredEventEmitted: boolean;
  changeEventId?: string;
}

export class FailureTracker {
  private db: Database.Database;
  private failureThreshold: number;

  constructor(db: Database.Database, failureThreshold = 3) {
    this.db = db;
    this.failureThreshold = failureThreshold;
  }

  handleCheckOutcome(
    subscriptionId: string,
    outcome: CheckOutcome,
    reason?: string
  ): OutageStatusResult {
    const state = this.db.prepare(`
      SELECT consecutive_failures, is_currently_down, last_down_alert_at
      FROM sub_state
      WHERE subscription_id = ?
    `).get(subscriptionId) as {
      consecutive_failures: number;
      is_currently_down: number;
      last_down_alert_at: string | null;
    } | undefined;

    if (!state) {
      throw new Error(`Sub state not found for subscription ${subscriptionId}`);
    }

    let consecutiveFailures = state.consecutive_failures;
    let isCurrentlyDown = Boolean(state.is_currently_down);
    let downEventEmitted = false;
    let recoveredEventEmitted = false;
    let changeEventId: string | undefined;

    if (outcome === 'ERROR' || outcome === 'BLOCKED') {
      consecutiveFailures++;

      if (consecutiveFailures >= this.failureThreshold && !isCurrentlyDown) {
        // Outage detected!
        isCurrentlyDown = true;
        downEventEmitted = true;
        changeEventId = crypto.randomUUID();

        this.db.prepare(`
          INSERT INTO change_events (
            id, subscription_id, event_type, summary
          ) VALUES (?, ?, 'DOWN', ?)
        `).run(
          changeEventId,
          subscriptionId,
          `Service outage detected: ${consecutiveFailures} consecutive failures (${reason || outcome})`
        );

        this.db.prepare(`
          UPDATE sub_state
          SET consecutive_failures = ?,
              is_currently_down = 1,
              last_down_alert_at = datetime('now')
          WHERE subscription_id = ?
        `).run(consecutiveFailures, subscriptionId);
      } else {
        this.db.prepare(`
          UPDATE sub_state
          SET consecutive_failures = ?
          WHERE subscription_id = ?
        `).run(consecutiveFailures, subscriptionId);
      }
    } else if (outcome === 'OK') {
      if (isCurrentlyDown) {
        // Recovery detected!
        isCurrentlyDown = false;
        recoveredEventEmitted = true;
        consecutiveFailures = 0;
        changeEventId = crypto.randomUUID();

        this.db.prepare(`
          INSERT INTO change_events (
            id, subscription_id, event_type, summary
          ) VALUES (?, ?, 'RECOVERED', ?)
        `).run(
          changeEventId,
          subscriptionId,
          'Service recovered: target returned OK status'
        );

        this.db.prepare(`
          UPDATE sub_state
          SET consecutive_failures = 0,
              is_currently_down = 0
          WHERE subscription_id = ?
        `).run(subscriptionId);
      } else {
        consecutiveFailures = 0;
        this.db.prepare(`
          UPDATE sub_state
          SET consecutive_failures = 0
          WHERE subscription_id = ?
        `).run(subscriptionId);
      }
    }

    return {
      consecutiveFailures,
      isCurrentlyDown,
      downEventEmitted,
      recoveredEventEmitted,
      changeEventId,
    };
  }
}
