import Database from 'better-sqlite3';
import crypto from 'crypto';
import { toSqliteDateTime } from '../../db/dates.js';

export interface JobRecord {
  id: string;
  queue_name: string;
  target_id: string | null;
  subscription_id: string | null;
  status: 'QUEUED' | 'CLAIMED' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  attempts: number;
  max_attempts: number;
  scheduled_at: string;
  lease_expires_at: string | null;
  locked_by: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export class DurableJobQueue {
  private db: Database.Database;
  private workerId: string;
  private leaseDurationSeconds: number;

  constructor(db: Database.Database, workerId?: string, leaseDurationSeconds = 60) {
    this.db = db;
    this.workerId = workerId || `worker_${crypto.randomUUID()}`;
    this.leaseDurationSeconds = leaseDurationSeconds;
  }

  getWorkerId(): string {
    return this.workerId;
  }

  /**
   * Enqueues a new job or updates an existing pending one.
   */
  enqueueJob(options: {
    queueName?: string;
    targetId?: string;
    subscriptionId?: string;
    scheduledAt?: Date;
    maxAttempts?: number;
  }): JobRecord {
    const id = crypto.randomUUID();
    const queueName = options.queueName || 'checks';
    const scheduledAt = toSqliteDateTime(options.scheduledAt || new Date());
    const maxAttempts = options.maxAttempts ?? 3;

    this.db.prepare(`
      INSERT INTO jobs (
        id, queue_name, target_id, subscription_id, status, attempts, max_attempts, scheduled_at
      ) VALUES (?, ?, ?, ?, 'QUEUED', 0, ?, ?)
    `).run(id, queueName, options.targetId || null, options.subscriptionId || null, maxAttempts, scheduledAt);

    return this.db.prepare('SELECT * FROM jobs WHERE id = ?').get(id) as JobRecord;
  }

  /**
   * Atomically claims the next due job in a transaction.
   */
  claimNextJob(queueName = 'checks'): JobRecord | null {
    const leaseExpires = toSqliteDateTime(new Date(Date.now() + this.leaseDurationSeconds * 1000));

    const claimTx = this.db.transaction(() => {
      // Find candidate job: QUEUED and scheduled_at <= now, OR expired lease
      const candidate = this.db.prepare(`
        SELECT id, attempts, max_attempts FROM jobs
        WHERE queue_name = ?
          AND (
            (status = 'QUEUED' AND datetime(scheduled_at) <= datetime('now'))
            OR
            (status IN ('CLAIMED', 'RUNNING') AND datetime(lease_expires_at) < datetime('now'))
          )
        ORDER BY scheduled_at ASC
        LIMIT 1
      `).get(queueName) as { id: string; attempts: number; max_attempts: number } | undefined;

      if (!candidate) {
        return null;
      }

      // If attempts exceeded max_attempts, fail the job
      if (candidate.attempts >= candidate.max_attempts) {
        this.db.prepare(`
          UPDATE jobs
          SET status = 'FAILED', error_message = 'Max attempts exceeded', completed_at = datetime('now')
          WHERE id = ?
        `).run(candidate.id);
        return null;
      }

      // Atomically claim and advance attempts
      this.db.prepare(`
        UPDATE jobs
        SET status = 'CLAIMED',
            locked_by = ?,
            lease_expires_at = ?,
            attempts = attempts + 1
        WHERE id = ?
      `).run(this.workerId, leaseExpires, candidate.id);

      return this.db.prepare('SELECT * FROM jobs WHERE id = ?').get(candidate.id) as JobRecord;
    });

    return claimTx();
  }

  /**
   * Heartbeat to extend the lease of an actively running job.
   */
  heartbeatJob(jobId: string): boolean {
    const newLease = toSqliteDateTime(new Date(Date.now() + this.leaseDurationSeconds * 1000));
    const res = this.db.prepare(`
      UPDATE jobs
      SET lease_expires_at = ?
      WHERE id = ? AND locked_by = ? AND status IN ('CLAIMED', 'RUNNING')
    `).run(newLease, jobId, this.workerId);

    return res.changes > 0;
  }

  /**
   * Completes a job successfully.
   */
  completeJob(jobId: string): void {
    this.db.prepare(`
      UPDATE jobs
      SET status = 'COMPLETED',
          completed_at = datetime('now'),
          locked_by = NULL,
          lease_expires_at = NULL
      WHERE id = ?
    `).run(jobId);
  }

  /**
   * Fails a job with an error message. If attempts remain, re-queues with backoff.
   */
  failJob(jobId: string, errorMessage: string): void {
    const job = this.db.prepare('SELECT attempts, max_attempts FROM jobs WHERE id = ?').get(jobId) as {
      attempts: number;
      max_attempts: number;
    } | undefined;

    if (!job) return;

    if (job.attempts < job.max_attempts) {
      // Re-queue with exponential backoff
      const delaySeconds = Math.pow(2, job.attempts) * 10;
      const nextRun = toSqliteDateTime(new Date(Date.now() + delaySeconds * 1000));

      this.db.prepare(`
        UPDATE jobs
        SET status = 'QUEUED',
            scheduled_at = ?,
            error_message = ?,
            locked_by = NULL,
            lease_expires_at = NULL
        WHERE id = ?
      `).run(nextRun, errorMessage, jobId);
    } else {
      this.db.prepare(`
        UPDATE jobs
        SET status = 'FAILED',
            error_message = ?,
            completed_at = datetime('now'),
            locked_by = NULL,
            lease_expires_at = NULL
      WHERE id = ?
    `).run(errorMessage, jobId);
    }
  }

  /**
   * Startup Crash Recovery: Resets stale or abandoned leases.
   */
  recoverStaleJobs(): number {
    const res = this.db.prepare(`
      UPDATE jobs
      SET status = 'QUEUED',
          locked_by = NULL,
          lease_expires_at = NULL
      WHERE status IN ('CLAIMED', 'RUNNING')
        AND datetime(lease_expires_at) < datetime('now')
        AND attempts < max_attempts
    `).run();

    // Mark expired jobs exceeding max_attempts as FAILED
    this.db.prepare(`
      UPDATE jobs
      SET status = 'FAILED',
          error_message = 'Abandoned during crash and exceeded max attempts',
          completed_at = datetime('now'),
          locked_by = NULL,
          lease_expires_at = NULL
      WHERE status IN ('CLAIMED', 'RUNNING')
        AND datetime(lease_expires_at) < datetime('now')
        AND attempts >= max_attempts
    `).run();

    return res.changes;
  }
}
