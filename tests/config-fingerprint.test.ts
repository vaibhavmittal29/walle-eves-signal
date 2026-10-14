import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  CaptureConfigSchema,
  computeCaptureFingerprint,
  canonicalStringify,
} from '../src/server/core/config.js';
import { initDatabase } from '../src/server/db/database.js';
import Database from 'better-sqlite3';

describe('Canonical Capture Config & Fingerprinting [AD, AE, AF, AG]', () => {
  let db: Database.Database;

  beforeEach(() => {
    db = initDatabase({ inMemory: true });
  });

  afterEach(() => {
    db.close();
  });

  it('[AE] rejects screenshotRequired: true with engine: http_dom', () => {
    const invalidConfig = {
      engine: 'http_dom',
      screenshotRequired: true,
    };

    expect(() => {
      CaptureConfigSchema.parse(invalidConfig);
    }).toThrow(/Screenshots require the Playwright browser engine/);

    expect(() => {
      computeCaptureFingerprint(invalidConfig);
    }).toThrow(/Screenshots require the Playwright browser engine/);
  });

  it('accepts screenshotRequired: true with engine: playwright', () => {
    const validConfig = {
      engine: 'playwright',
      screenshotRequired: true,
    };

    const result = computeCaptureFingerprint(validConfig);
    expect(result.parsed.engine).toBe('playwright');
    expect(result.parsed.screenshotRequired).toBe(true);
  });

  it('[AF] generates identical SHA-256 for omitted defaults, explicit defaults, and reordered keys', () => {
    // 1. Completely omitted defaults
    const emptyConfig = {};
    const resEmpty = computeCaptureFingerprint(emptyConfig);

    // 2. Explicit defaults matching schema exactly
    const explicitDefaults = {
      engine: 'http_dom',
      viewport: { width: 1280, height: 720 },
      deviceScaleFactor: 1,
      jsEnabled: true,
      userAgent: 'ChangeWatch/1.0 (Student Project; VIT Vellore; +contact)',
      waitStrategy: { timeoutMs: 10000 },
      screenshotRequired: false,
    };
    const resExplicit = computeCaptureFingerprint(explicitDefaults);

    // 3. Reordered keys with identical values
    const reorderedKeys = {
      screenshotRequired: false,
      userAgent: 'ChangeWatch/1.0 (Student Project; VIT Vellore; +contact)',
      waitStrategy: { timeoutMs: 10000 },
      viewport: { height: 720, width: 1280 },
      jsEnabled: true,
      engine: 'http_dom',
      deviceScaleFactor: 1,
    };
    const resReordered = computeCaptureFingerprint(reorderedKeys);

    expect(resEmpty.fingerprint).toBe(resExplicit.fingerprint);
    expect(resEmpty.fingerprint).toBe(resReordered.fingerprint);
    expect(resEmpty.canonicalJson).toBe(resExplicit.canonicalJson);
    expect(resEmpty.canonicalJson).toBe(resReordered.canonicalJson);
  });

  it('[AG] generates distinct SHA-256 for material configuration differences', () => {
    const base = computeCaptureFingerprint({});

    // 1. Different viewport
    const customViewport = computeCaptureFingerprint({
      viewport: { width: 1920, height: 1080 },
    });
    expect(customViewport.fingerprint).not.toBe(base.fingerprint);

    // 2. Custom headers
    const customHeaders = computeCaptureFingerprint({
      customHeaders: { 'X-Custom-Header': 'val1' },
    });
    expect(customHeaders.fingerprint).not.toBe(base.fingerprint);

    // 3. Custom wait selector
    const customWait = computeCaptureFingerprint({
      waitStrategy: { waitForSelector: '#main-content', timeoutMs: 15000 },
    });
    expect(customWait.fingerprint).not.toBe(base.fingerprint);

    // 4. Engine switch
    const playwrightEngine = computeCaptureFingerprint({
      engine: 'playwright',
    });
    expect(playwrightEngine.fingerprint).not.toBe(base.fingerprint);
  });

  it('[AD] generated stored column required_engine matches capture_config.engine in SQLite', () => {
    // Insert mock user & target
    db.prepare(`
      INSERT INTO users (id, email, password_hash, password_salt, display_name)
      VALUES ('u1', 'test@example.com', 'h', 's', 'Tester')
    `).run();

    db.prepare(`
      INSERT INTO targets (id, canonical_url, safe_hostname, origin)
      VALUES ('t1', 'https://example.com', 'example.com', 'https://example.com:443')
    `).run();

    // 1. Insert subscription with http_dom
    const domConfig = computeCaptureFingerprint({ engine: 'http_dom' });
    db.prepare(`
      INSERT INTO subscriptions (
        id, user_id, target_id, name, interval_minutes, next_check_at,
        capture_config, capture_fingerprint
      ) VALUES ('s1', 'u1', 't1', 'Monitor 1', 60, datetime('now'), ?, ?)
    `).run(domConfig.canonicalJson, domConfig.fingerprint);

    const row1 = db.prepare('SELECT required_engine FROM subscriptions WHERE id = ?').get('s1') as any;
    expect(row1.required_engine).toBe('http_dom');

    // 2. Insert subscription with playwright
    const pwConfig = computeCaptureFingerprint({ engine: 'playwright' });
    db.prepare(`
      INSERT INTO subscriptions (
        id, user_id, target_id, name, interval_minutes, next_check_at,
        capture_config, capture_fingerprint
      ) VALUES ('s2', 'u1', 't1', 'Monitor 2', 60, datetime('now'), ?, ?)
    `).run(pwConfig.canonicalJson, pwConfig.fingerprint);

    const row2 = db.prepare('SELECT required_engine FROM subscriptions WHERE id = ?').get('s2') as any;
    expect(row2.required_engine).toBe('playwright');
  });
});
