import { describe, it, expect, afterAll } from 'vitest';
import { executeCapture } from '../src/server/core/capture/capture-engine.js';
import { closePlaywrightBrowser } from '../src/server/core/capture/playwright-engine.js';
import { computeCaptureFingerprint } from '../src/server/core/config.js';
import { classifyCaptureResponse } from '../src/server/core/capture/classifier.js';
import { FIXTURES } from '../src/fixtures/index.js';

describe('Dual-Engine Capture & Classifier Testbed [G, H, Y]', () => {
  afterAll(async () => {
    await closePlaywrightBrowser();
  });

  it('[Y] testbed contains all 14+ required edge cases', () => {
    const fixtureKeys = Object.keys(FIXTURES);
    expect(fixtureKeys.length).toBeGreaterThanOrEqual(14);
    expect(fixtureKeys).toContain('stable-clean');
    expect(fixtureKeys).toContain('content-modified');
    expect(fixtureKeys).toContain('noisy-timestamps');
    expect(fixtureKeys).toContain('anti-bot-challenge');
    expect(fixtureKeys).toContain('http-500-outage');
    expect(fixtureKeys).toContain('http-403-forbidden');
    expect(fixtureKeys).toContain('disallow-robots');
    expect(fixtureKeys).toContain('css-selector-shifts');
    expect(fixtureKeys).toContain('javascript-rendered');
    expect(fixtureKeys).toContain('subresource-heavy');
    expect(fixtureKeys).toContain('empty-dom');
    expect(fixtureKeys).toContain('unstable-flapping');
    expect(fixtureKeys).toContain('noisy-high-volatility');
    expect(fixtureKeys).toContain('websocket-service-worker');
  });

  it('[G] both http_dom and playwright engines yield consistent text and sanitized DOM', async () => {
    const httpDomConfig = computeCaptureFingerprint({ engine: 'http_dom' }).parsed;
    const playwrightConfig = computeCaptureFingerprint({ engine: 'playwright' }).parsed;

    const url = 'fixture://stable-clean';

    const resDom = await executeCapture(url, httpDomConfig);
    const resPw = await executeCapture(url, playwrightConfig);

    expect(resDom.classification.outcome).toBe('OK');
    expect(resPw.classification.outcome).toBe('OK');

    expect(resDom.capture).toBeDefined();
    expect(resPw.capture).toBeDefined();

    // Verify both engines extract the same core text content
    expect(resDom.capture!.rawText).toContain('School of Computer Science & Engineering');
    expect(resPw.capture!.rawText).toContain('School of Computer Science & Engineering');
    expect(resDom.capture!.rawText).toContain('Fall 2026 Curriculum Updates');
    expect(resPw.capture!.rawText).toContain('Fall 2026 Curriculum Updates');

    // Verify scripts, styles, etc. were removed in both
    expect(resDom.capture!.sanitizedDom).not.toContain('<script');
    expect(resPw.capture!.sanitizedDom).not.toContain('<script');
  });

  it('[H] accurately classifies OK, ERROR, and BLOCKED outcomes across fixtures', async () => {
    const config = computeCaptureFingerprint({ engine: 'http_dom' }).parsed;

    // 1. Stable Clean Page -> OK
    const resClean = await executeCapture('fixture://stable-clean', config);
    expect(resClean.classification.outcome).toBe('OK');
    expect(resClean.classification.reason).toBe('SUCCESS');

    // 2. HTTP 500 Outage -> ERROR
    const res500 = await executeCapture('fixture://http-500-outage', config);
    expect(res500.classification.outcome).toBe('ERROR');
    expect(res500.classification.reason).toBe('HTTP_500_SERVER_ERROR');

    // 3. HTTP 403 Forbidden -> BLOCKED
    const res403 = await executeCapture('fixture://http-403-forbidden', config);
    expect(res403.classification.outcome).toBe('BLOCKED');
    expect(res403.classification.reason).toBe('HTTP_403_ACCESS_DENIED_OR_RATE_LIMITED');

    // 4. Anti-Bot / Cloudflare Challenge -> BLOCKED
    const resChallenge = await executeCapture('fixture://anti-bot-challenge', config);
    expect(resChallenge.classification.outcome).toBe('BLOCKED');
    expect(resChallenge.classification.reason).toBe('ANTI_BOT_CHALLENGE_DETECTED');

    // 5. Empty DOM -> ERROR
    const resEmpty = await executeCapture('fixture://empty-dom', config);
    expect(resEmpty.classification.outcome).toBe('ERROR');
    expect(resEmpty.classification.reason).toBe('EMPTY_CONTENT_PAYLOAD');
  });

  it('client-side JS rendered page is executed by Playwright', async () => {
    const pwConfig = computeCaptureFingerprint({
      engine: 'playwright',
      jsEnabled: true,
      waitStrategy: { timeoutMs: 5000 },
    }).parsed;

    const res = await executeCapture('fixture://javascript-rendered', pwConfig);
    expect(res.classification.outcome).toBe('OK');
    expect(res.capture?.rawText).toContain('Dashboard Loaded via Client JavaScript');
    expect(res.capture?.rawText).toContain('Active nodes: 42');
  });
});
