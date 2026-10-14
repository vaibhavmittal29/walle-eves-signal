import Database from 'better-sqlite3';
import crypto from 'crypto';
import { toSqliteDateTime } from '../../db/dates.js';
import { ConfigAwareDeduplicator, DeduplicatedCaptureResult } from './deduplicator.js';
import { OriginRobotsCache } from './robots-cache.js';
import { DomainRateLimiter, calculateJitteredNextCheck } from './rate-limiter.js';
import { DurableJobQueue } from './queue.js';

export interface DueSubscription {
  id: string;
  user_id: string;
  target_id: string;
  name: string;
  interval_minutes: number;
  next_check_at: string;
  capture_config: string;
  capture_fingerprint: string;
  required_engine: string;
  canonical_url: string;
  safe_hostname: string;
  origin: string;
}

export class SchedulerEngine {
  private db: Database.Database;
  private deduplicator: ConfigAwareDeduplicator;
  private robotsCache: OriginRobotsCache;
  private rateLimiter: DomainRateLimiter;
  private queue: DurableJobQueue;

  constructor(
    db: Database.Database,
    options?: {
      cacheFreshnessSeconds?: number;
      minDomainGapMs?: number;
      leaseDurationSeconds?: number;
    }
  ) {
    this.db = db;
    this.deduplicator = new ConfigAwareDeduplicator(db, options?.cacheFreshnessSeconds ?? 15);
    this.robotsCache = new OriginRobotsCache(db);
    this.rateLimiter = new DomainRateLimiter(options?.minDomainGapMs ?? 10000);
    this.queue = new DurableJobQueue(db, undefined, options?.leaseDurationSeconds ?? 60);
  }

  getDeduplicator(): ConfigAwareDeduplicator {
    return this.deduplicator;
  }

  getRobotsCache(): OriginRobotsCache {
    return this.robotsCache;
  }

  getRateLimiter(): DomainRateLimiter {
    return this.rateLimiter;
  }

  getQueue(): DurableJobQueue {
    return this.queue;
  }

  /**
   * Queries strictly subscriptions that are due right now (`next_check_at <= now` and `is_paused = 0`).
   */
  getDueSubscriptions(): DueSubscription[] {
    const rows = this.db.prepare(`
      SELECT 
        s.id, s.user_id, s.target_id, s.name, s.interval_minutes, s.next_check_at,
        s.capture_config, s.capture_fingerprint, s.required_engine,
        t.canonical_url, t.safe_hostname, t.origin
      FROM subscriptions s
      JOIN targets t ON s.target_id = t.id
      WHERE datetime(s.next_check_at) <= datetime('now')
        AND s.is_paused = 0
      ORDER BY s.next_check_at ASC
    `).all() as DueSubscription[];

    return rows;
  }

  /**
   * Executes a scheduled evaluation cycle.
   * Groups due subscriptions by target_id and capture_fingerprint to execute 1 shared fetch.
   */
  async runDueCycle(): Promise<{
    evaluatedCount: number;
    groupsProcessed: number;
    deduplicatedRuns: number;
  }> {
    const dueSubs = this.getDueSubscriptions();
    if (dueSubs.length === 0) {
      return { evaluatedCount: 0, groupsProcessed: 0, deduplicatedRuns: 0 };
    }

    // Group due subscriptions by dedup key: `${target_id}:${capture_fingerprint}`
    const groups = new Map<string, DueSubscription[]>();
    for (const sub of dueSubs) {
      const key = `${sub.target_id}:${sub.capture_fingerprint}`;
      if (!groups.has(key)) {
        groups.set(key, []);
      }
      groups.get(key)!.push(sub);
    }

    let deduplicatedRuns = 0;
    let evaluatedCount = 0;

    for (const [groupKey, subs] of groups.entries()) {
      const first = subs[0];
      const targetId = first.target_id;
      const canonicalUrl = first.canonical_url;
      const hostname = first.safe_hostname;
      const rawConfig = JSON.parse(first.capture_config);

      // 1. Robots.txt check
      const robotsResult = await this.robotsCache.isAllowed(canonicalUrl, rawConfig.userAgent);
      if (!robotsResult.allowed) {
        // Disallowed: record BLOCKED run for all due subscriptions in this group
        for (const sub of subs) {
          this.recordCheckRun({
            subscriptionId: sub.id,
            targetId,
            outcome: 'BLOCKED',
            reason: robotsResult.reason || 'Blocked by robots.txt',
            durationMs: 0,
            wasDeduplicated: 0,
          });
          this.advanceNextCheck(sub.id, sub.interval_minutes);
          evaluatedCount++;
        }
        continue;
      }

      // 2. Domain rate limiter check
      const rateCheck = this.rateLimiter.canNavigate(hostname);
      if (!rateCheck.allowed && !canonicalUrl.startsWith('fixture://')) {
        // Skip for this iteration until gap elapsed
        continue;
      }

      this.rateLimiter.startNavigation(hostname);
      let captureResult: DeduplicatedCaptureResult;

      try {
        captureResult = await this.deduplicator.executeOrShareCapture(
          targetId,
          canonicalUrl,
          rawConfig
        );
      } finally {
        this.rateLimiter.finishNavigation(hostname);
      }

      // 3. Evaluate each due subscriber in this group
      subs.forEach((sub, index) => {
        const wasDedup = (captureResult.wasDeduplicated || index > 0) ? 1 : 0;
        if (wasDedup) deduplicatedRuns++;

        this.recordCheckRun({
          subscriptionId: sub.id,
          targetId,
          outcome: captureResult.classification.outcome,
          reason: captureResult.classification.reason,
          httpStatus: captureResult.classification.httpStatus,
          durationMs: captureResult.durationMs,
          wasDeduplicated: wasDedup,
        });

        // Advance next_check_at with ±10% jitter
        this.advanceNextCheck(sub.id, sub.interval_minutes);
        evaluatedCount++;
      });
    }

    return {
      evaluatedCount,
      groupsProcessed: groups.size,
      deduplicatedRuns,
    };
  }

  private recordCheckRun(data: {
    subscriptionId: string;
    targetId: string;
    outcome: 'OK' | 'ERROR' | 'BLOCKED';
    reason?: string;
    httpStatus?: number;
    durationMs: number;
    wasDeduplicated: number;
  }): void {
    const runId = crypto.randomUUID();
    this.db.prepare(`
      INSERT INTO check_runs (
        id, subscription_id, target_id, outcome, reason, http_status, duration_ms, was_deduplicated
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      runId,
      data.subscriptionId,
      data.targetId,
      data.outcome,
      data.reason || null,
      data.httpStatus || null,
      data.durationMs,
      data.wasDeduplicated
    );
  }

  private advanceNextCheck(subscriptionId: string, intervalMinutes: number): void {
    const nextCheck = toSqliteDateTime(calculateJitteredNextCheck(intervalMinutes));
    this.db.prepare(`
      UPDATE subscriptions
      SET next_check_at = ?
      WHERE id = ?
    `).run(nextCheck, subscriptionId);
  }
}
