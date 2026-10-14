import Database from 'better-sqlite3';
import crypto from 'crypto';
import { CaptureConfig, computeCaptureFingerprint } from '../config.js';
import { executeCapture, UnifiedCaptureResult } from '../capture/capture-engine.js';
import { ClassificationResult } from '../capture/classifier.js';

export interface ObservationRecord {
  id: string;
  target_id: string;
  engine_used: 'http_dom' | 'playwright';
  capture_fingerprint: string;
  rendering_fingerprint: string;
  final_url: string;
  http_status: number;
  sanitized_dom: string;
  raw_text: string;
  screenshot_path: string | null;
  subresource_count: number;
  captured_at: string;
}

export interface DeduplicatedCaptureResult {
  observation?: ObservationRecord;
  classification: ClassificationResult;
  wasDeduplicated: boolean;
  durationMs: number;
}

export class ConfigAwareDeduplicator {
  private db: Database.Database;
  private inFlightCaptures = new Map<string, Promise<DeduplicatedCaptureResult>>();
  private cacheFreshnessSeconds: number;

  constructor(db: Database.Database, cacheFreshnessSeconds = 15) {
    this.db = db;
    this.cacheFreshnessSeconds = cacheFreshnessSeconds;
  }

  getDedupKey(targetId: string, captureFingerprint: string): string {
    return `${targetId}:${captureFingerprint}`;
  }

  /**
   * Retrieves an existing fresh observation from SQLite if captured within freshness window.
   */
  findRecentObservation(targetId: string, captureFingerprint: string): ObservationRecord | null {
    const row = this.db.prepare(`
      SELECT * FROM observations
      WHERE target_id = ?
        AND capture_fingerprint = ?
        AND captured_at > datetime('now', '-' || ? || ' seconds')
      ORDER BY captured_at DESC
      LIMIT 1
    `).get(targetId, captureFingerprint, this.cacheFreshnessSeconds) as ObservationRecord | undefined;

    return row || null;
  }

  /**
   * Executes or shares a capture for the specified target and capture config.
   */
  async executeOrShareCapture(
    targetId: string,
    canonicalUrl: string,
    rawConfig: unknown
  ): Promise<DeduplicatedCaptureResult> {
    const { parsed, fingerprint } = computeCaptureFingerprint(rawConfig);
    const dedupKey = this.getDedupKey(targetId, fingerprint);

    // 1. Check SQLite for recently saved observation
    const existing = this.findRecentObservation(targetId, fingerprint);
    if (existing) {
      return {
        observation: existing,
        classification: {
          outcome: existing.http_status >= 200 && existing.http_status < 400 ? 'OK' : 'ERROR',
          reason: 'SHARED_OBSERVATION_CACHE_HIT',
          httpStatus: existing.http_status,
        },
        wasDeduplicated: true,
        durationMs: 0,
      };
    }

    // 2. Check for an in-flight capture to piggyback on
    const existingFlight = this.inFlightCaptures.get(dedupKey);
    if (existingFlight) {
      const res = await existingFlight;
      return {
        ...res,
        wasDeduplicated: true,
      };
    }

    // 3. Initiate new capture
    const capturePromise = (async () => {
      const startTime = Date.now();
      const outcome = await executeCapture(canonicalUrl, parsed);
      const durationMs = Date.now() - startTime;

      if (!outcome.capture) {
        return {
          classification: outcome.classification,
          wasDeduplicated: false,
          durationMs,
        };
      }

      // Persist new observation to SQLite
      const obsId = crypto.randomUUID();
      const cap = outcome.capture;

      this.db.prepare(`
        INSERT INTO observations (
          id, target_id, engine_used, capture_fingerprint, rendering_fingerprint,
          final_url, http_status, sanitized_dom, raw_text, screenshot_path, subresource_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `).run(
        obsId,
        targetId,
        cap.engine,
        fingerprint,
        JSON.stringify(cap.renderingFingerprint),
        cap.finalUrl,
        cap.httpStatus,
        cap.sanitizedDom,
        cap.rawText,
        ('screenshotPath' in cap ? cap.screenshotPath : null) || null,
        cap.subresourceCount
      );

      const savedObs = this.db.prepare('SELECT * FROM observations WHERE id = ?').get(obsId) as ObservationRecord;

      return {
        observation: savedObs,
        classification: outcome.classification,
        wasDeduplicated: false,
        durationMs,
      };
    })();

    this.inFlightCaptures.set(dedupKey, capturePromise);

    try {
      return await capturePromise;
    } finally {
      this.inFlightCaptures.delete(dedupKey);
    }
  }
}
