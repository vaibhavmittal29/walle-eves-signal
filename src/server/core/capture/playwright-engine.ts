import { chromium, Browser, BrowserContext, Page } from 'playwright';
import path from 'path';
import crypto from 'crypto';
import fs from 'fs';
import { CaptureConfig } from '../config.js';
import { isFixtureUrl, dispatchFixture } from './fixture-dispatcher.js';
import { sanitizeHtmlDom } from './http-dom-engine.js';
import { validatePublicIp } from '../security/ip-validator.js';

let sharedBrowser: Browser | null = null;

export async function getPlaywrightBrowser(): Promise<Browser> {
  if (!sharedBrowser || !sharedBrowser.isConnected()) {
    sharedBrowser = await chromium.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    });
  }
  return sharedBrowser;
}

export async function closePlaywrightBrowser(): Promise<void> {
  if (sharedBrowser) {
    await sharedBrowser.close();
    sharedBrowser = null;
  }
}

export interface PlaywrightCaptureOutput {
  engine: 'playwright';
  finalUrl: string;
  httpStatus: number;
  sanitizedDom: string;
  rawText: string;
  screenshotPath?: string;
  subresourceCount: number;
  renderingFingerprint: {
    title: string;
    contentLength: number;
    subresources: number;
    timestamp: string;
  };
  durationMs: number;
}

export async function captureWithPlaywright(
  url: string,
  config: CaptureConfig,
  screenshotDir?: string
): Promise<PlaywrightCaptureOutput> {
  const startTime = Date.now();
  const browser = await getPlaywrightBrowser();

  const context: BrowserContext = await browser.newContext({
    viewport: config.viewport,
    deviceScaleFactor: config.deviceScaleFactor,
    userAgent: config.userAgent,
    locale: config.locale,
    timezoneId: config.timezone,
    javaScriptEnabled: config.jsEnabled,
    serviceWorkers: 'block', // Hardened against service worker persistence
    extraHTTPHeaders: config.customHeaders,
  });

  const page: Page = await context.newPage();
  let subresourceCount = 0;
  let responseStatus = 200;

  try {
    // 1. Intercept & close all WebSocket connections prior to navigation
    await page.routeWebSocket('**/*', (wsRoute) => {
      wsRoute.close();
    });

    // 2. Request interception for SSRF protection and fixture dispatching
    await page.route('**/*', async (route) => {
      const req = route.request();
      const reqUrl = req.url();

      if (req.isNavigationRequest() && isFixtureUrl(reqUrl)) {
        const fixture = dispatchFixture(reqUrl);
        responseStatus = fixture.statusCode;
        await route.fulfill({
          status: fixture.statusCode,
          contentType: fixture.headers['content-type'] || 'text/html; charset=utf-8',
          headers: fixture.headers,
          body: fixture.body,
        });
        return;
      }

      if (isFixtureUrl(reqUrl)) {
        await route.fulfill({ status: 200, contentType: 'text/plain', body: '' });
        return;
      }

      // Check subresource URL safety
      try {
        const parsed = new URL(reqUrl);
        if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
          const directCheck = validatePublicIp(parsed.hostname);
          if (directCheck.reason !== 'INVALID_IP_FORMAT' && !directCheck.valid) {
            await route.abort('blockedbyclient');
            return;
          }
        }
      } catch {
        await route.abort('blockedbyclient');
        return;
      }

      subresourceCount++;
      await route.continue();
    });

    // 3. Navigation with waitStrategy (virtual fixture via setContent or live URL via goto)
    if (isFixtureUrl(url)) {
      const fixture = dispatchFixture(url);
      responseStatus = fixture.statusCode;
      await page.setContent(fixture.body, {
        timeout: config.waitStrategy.timeoutMs,
        waitUntil: 'domcontentloaded',
      });
    } else {
      const response = await page.goto(url, {
        timeout: config.waitStrategy.timeoutMs,
        waitUntil: 'domcontentloaded',
      });
      if (response) {
        responseStatus = response.status();
      }
    }

    // Wait for custom selector if specified
    if (config.waitStrategy.waitForSelector) {
      await page.waitForSelector(config.waitStrategy.waitForSelector, {
        timeout: config.waitStrategy.timeoutMs,
      });
    }

    // Optional short settling time for client JS execution
    if (config.jsEnabled) {
      await page.waitForTimeout(100);
    }

    // Capture screenshot if required
    let screenshotPath: string | undefined;
    if (config.screenshotRequired) {
      const targetDir = screenshotDir || path.resolve(process.cwd(), 'data', 'screenshots');
      if (!fs.existsSync(targetDir)) {
        fs.mkdirSync(targetDir, { recursive: true });
      }
      const filename = `shot_${crypto.randomUUID()}.png`;
      screenshotPath = path.join(targetDir, filename);
      await page.screenshot({ path: screenshotPath, fullPage: true });
    }

    const html = await page.content();
    const finalUrl = isFixtureUrl(url) ? url : page.url();

    const { sanitizedDom, rawText, title, subresourceCount: domSubresources } = sanitizeHtmlDom(html);
    const durationMs = Date.now() - startTime;

    return {
      engine: 'playwright',
      finalUrl,
      httpStatus: responseStatus,
      sanitizedDom,
      rawText,
      screenshotPath,
      subresourceCount: Math.max(subresourceCount, domSubresources),
      renderingFingerprint: {
        title,
        contentLength: html.length,
        subresources: Math.max(subresourceCount, domSubresources),
        timestamp: new Date().toISOString(),
      },
      durationMs,
    };
  } finally {
    await context.close();
  }
}
