import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { initDatabase } from '../src/server/db/database.js';
import { OriginRobotsCache, getNormalizedOrigin } from '../src/server/core/scheduler/robots-cache.js';
import Database from 'better-sqlite3';

describe('Origin-Scoped Robots.txt Policy & Response Header Retention [E, AC]', () => {
  let db: Database.Database;
  let robotsCache: OriginRobotsCache;

  beforeEach(() => {
    db = initDatabase({ inMemory: true });
    robotsCache = new OriginRobotsCache(db);
  });

  afterEach(() => {
    db.close();
  });

  it('[AC] strictly isolates robots.txt rules between different origins on the same host (http vs https)', async () => {
    const httpOrigin = 'http://example.com:80';
    const httpsOrigin = 'https://example.com:443';

    expect(getNormalizedOrigin('http://example.com/blog')).toBe(httpOrigin);
    expect(getNormalizedOrigin('https://example.com/blog')).toBe(httpsOrigin);

    // Mock httpOrigin disallows /private, allows /public
    robotsCache.setMockRobots(
      httpOrigin,
      `User-agent: *\nDisallow: /private\nAllow: /public\n`,
      200,
      { 'content-type': 'text/plain', 'retry-after': '120', 'etag': '"etag-http"' }
    );

    // Mock httpsOrigin allows everything
    robotsCache.setMockRobots(
      httpsOrigin,
      `User-agent: *\nAllow: /\n`,
      200,
      { 'content-type': 'text/plain', 'etag': '"etag-https"' }
    );

    // Check http://example.com/private -> DISALLOWED
    const httpCheckPrivate = await robotsCache.isAllowed('http://example.com/private');
    expect(httpCheckPrivate.allowed).toBe(false);
    expect(httpCheckPrivate.origin).toBe(httpOrigin);

    // Check https://example.com/private -> ALLOWED (isolated rule!)
    const httpsCheckPrivate = await robotsCache.isAllowed('https://example.com/private');
    expect(httpsCheckPrivate.allowed).toBe(true);
    expect(httpsCheckPrivate.origin).toBe(httpsOrigin);

    // Verify raw header retention in SQLite table
    const rowHttp = robotsCache.getCachedRobots(httpOrigin);
    expect(rowHttp?.response_headers['retry-after']).toBe('120');
    expect(rowHttp?.response_headers['etag']).toBe('"etag-http"');

    const rowHttps = robotsCache.getCachedRobots(httpsOrigin);
    expect(rowHttps?.response_headers['etag']).toBe('"etag-https"');
    expect(rowHttps?.response_headers['retry-after']).toBeUndefined();
  });

  it('[E] evaluates RFC 9309 path prefix precedence and explicit Allow exceptions', async () => {
    const origin = 'https://docs.site.org:443';

    // Disallow /api, but allow /api/v1/public
    robotsCache.setMockRobots(
      origin,
      `User-agent: *\nDisallow: /api\nAllow: /api/v1/public\n`,
      200
    );

    const checkDisallowed = await robotsCache.isAllowed('https://docs.site.org/api/secret');
    expect(checkDisallowed.allowed).toBe(false);

    const checkException = await robotsCache.isAllowed('https://docs.site.org/api/v1/public/items');
    expect(checkException.allowed).toBe(true);
  });

  it('virtual fixture disallow-robots is properly identified as disallowed', async () => {
    const check = await robotsCache.isAllowed('fixture://disallow-robots');
    expect(check.allowed).toBe(false);
    expect(check.reason).toContain('robots.txt fixture rule');
  });
});
