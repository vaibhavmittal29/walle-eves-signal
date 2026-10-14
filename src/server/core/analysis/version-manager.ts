import Database from 'better-sqlite3';
import crypto from 'crypto';
import { extractNormalizedText } from './normalizer.js';
import { computeContentHash } from './hasher.js';
import { ObservationRecord } from '../scheduler/deduplicator.js';

export interface VersionRecord {
  id: string;
  subscription_id: string;
  observation_id: string;
  version_number: number;
  content_hash: string;
  stored_text: string;
  screenshot_path: string | null;
  change_summary: string | null;
  created_at: string;
}

export interface EvaluationOutcome {
  changeDetected: boolean;
  isInitialBaseline: boolean;
  pendingConfirmation?: boolean;
  version?: VersionRecord;
  previousVersion?: VersionRecord;
  contentHash: string;
  normalizedText: string;
}

export class VersionManager {
  private db: Database.Database;

  constructor(db: Database.Database) {
    this.db = db;
  }

  /**
   * Evaluates an observation against a subscription's baseline.
   * Emits new versions only upon genuine confirmed changes.
   */
  evaluateSubscription(
    subscriptionId: string,
    observation: ObservationRecord
  ): EvaluationOutcome {
    const sub = this.db.prepare(`
      SELECT s.*, st.active_version_id, st.pending_candidate_hash,
             st.pending_candidate_checks, st.pending_observation_id,
             st.last_alerted_hash, st.consecutive_failures, st.is_currently_down
      FROM subscriptions s
      JOIN sub_state st ON s.id = st.subscription_id
      WHERE s.id = ?
    `).get(subscriptionId) as any;

    if (!sub) {
      throw new Error(`Subscription not found: ${subscriptionId}`);
    }

    // 1. Extract and normalize subscriber-specific text
    const includeSelectors = JSON.parse(sub.include_selectors || '[]');
    const ignoreSelectors = JSON.parse(sub.ignore_selectors || '[]');
    const noiseFilters = JSON.parse(sub.noise_filters || '{}');

    const normalizedText = extractNormalizedText(observation.sanitized_dom, {
      includeSelectors,
      ignoreSelectors,
      noiseFilters,
    });

    const contentHash = computeContentHash(normalizedText);

    // 2. Initial baseline check (no prior version exists)
    if (!sub.active_version_id) {
      const v1Id = crypto.randomUUID();
      this.db.prepare(`
        INSERT INTO monitor_versions (
          id, subscription_id, observation_id, version_number,
          content_hash, stored_text, screenshot_path, change_summary
        ) VALUES (?, ?, ?, 1, ?, ?, ?, 'Initial baseline snapshot')
      `).run(v1Id, subscriptionId, observation.id, contentHash, normalizedText, observation.screenshot_path);

      this.db.prepare(`
        UPDATE sub_state
        SET active_version_id = ?,
            last_alerted_hash = ?,
            pending_candidate_hash = NULL,
            pending_candidate_checks = 0,
            pending_observation_id = NULL,
            consecutive_failures = 0,
            is_currently_down = 0
        WHERE subscription_id = ?
      `).run(v1Id, contentHash, subscriptionId);

      const v1 = this.db.prepare('SELECT * FROM monitor_versions WHERE id = ?').get(v1Id) as VersionRecord;

      return {
        changeDetected: false,
        isInitialBaseline: true,
        version: v1,
        contentHash,
        normalizedText,
      };
    }

    // 3. Compare with active baseline version
    const activeVersion = this.db.prepare(
      'SELECT * FROM monitor_versions WHERE id = ?'
    ).get(sub.active_version_id) as VersionRecord;

    if (!activeVersion) {
      throw new Error(`Corrupted state: active version ${sub.active_version_id} not found`);
    }

    // Identical content hash -> ZERO new versions
    if (activeVersion.content_hash === contentHash) {
      // Clear any pending candidate since page returned to baseline
      if (sub.pending_candidate_hash) {
        this.db.prepare(`
          UPDATE sub_state
          SET pending_candidate_hash = NULL,
              pending_candidate_checks = 0,
              pending_observation_id = NULL
          WHERE subscription_id = ?
        `).run(subscriptionId);
      }

      return {
        changeDetected: false,
        isInitialBaseline: false,
        version: activeVersion,
        contentHash,
        normalizedText,
      };
    }

    // 4. Candidate change detected!
    // Confirmation policy:
    // - Sensitivity 'low': requires 2-check confirmation
    // - Sensitivity 'balanced' / 'high': immediate confirmation (or confirmed on second check)
    const requiresTwoChecks = sub.sensitivity === 'low';

    if (requiresTwoChecks) {
      if (sub.pending_candidate_hash !== contentHash) {
        // First check of new candidate: record in sub_state and protect candidate observation
        this.db.prepare(`
          UPDATE sub_state
          SET pending_candidate_hash = ?,
              pending_candidate_checks = 1,
              pending_observation_id = ?
          WHERE subscription_id = ?
        `).run(contentHash, observation.id, subscriptionId);

        return {
          changeDetected: false,
          isInitialBaseline: false,
          pendingConfirmation: true,
          contentHash,
          normalizedText,
        };
      }
      // If we reach here, pending_candidate_hash matches for 2nd consecutive check!
    }

    // 5. Commit confirmed new version
    const newVersionNumber = activeVersion.version_number + 1;
    const newVersionId = crypto.randomUUID();

    this.db.prepare(`
      INSERT INTO monitor_versions (
        id, subscription_id, observation_id, version_number,
        content_hash, stored_text, screenshot_path, change_summary
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      newVersionId,
      subscriptionId,
      observation.id,
      newVersionNumber,
      contentHash,
      normalizedText,
      observation.screenshot_path,
      `Detected change at version ${newVersionNumber}`
    );

    // Create change event
    const eventId = crypto.randomUUID();
    this.db.prepare(`
      INSERT INTO change_events (
        id, subscription_id, previous_version_id, current_version_id,
        event_type, summary
      ) VALUES (?, ?, ?, ?, 'CHANGE', ?)
    `).run(
      eventId,
      subscriptionId,
      activeVersion.id,
      newVersionId,
      `Content updated from v${activeVersion.version_number} to v${newVersionNumber}`
    );

    // Update subscription state
    this.db.prepare(`
      UPDATE sub_state
      SET active_version_id = ?,
          last_alerted_hash = ?,
          pending_candidate_hash = NULL,
          pending_candidate_checks = 0,
          pending_observation_id = NULL
      WHERE subscription_id = ?
    `).run(newVersionId, contentHash, subscriptionId);

    const committedVersion = this.db.prepare(
      'SELECT * FROM monitor_versions WHERE id = ?'
    ).get(newVersionId) as VersionRecord;

    return {
      changeDetected: true,
      isInitialBaseline: false,
      version: committedVersion,
      previousVersion: activeVersion,
      contentHash,
      normalizedText,
    };
  }

  /**
   * Routine observation cleanup: deletes only unreferenced captures older than 30 days.
   * Confirmed monitor_versions and pending candidate observations are strictly preserved.
   */
  cleanupUnreferencedObservations(olderThanDays = 30): number {
    const res = this.db.prepare(`
      DELETE FROM observations 
      WHERE id NOT IN (
        SELECT observation_id FROM monitor_versions 
        UNION 
        SELECT pending_observation_id FROM sub_state WHERE pending_observation_id IS NOT NULL
      ) 
      AND datetime(captured_at) < datetime('now', '-' || ? || ' days')
    `).run(olderThanDays);

    return res.changes;
  }
}
