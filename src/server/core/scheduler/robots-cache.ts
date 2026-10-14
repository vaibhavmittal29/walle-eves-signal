import Database from 'better-sqlite3';
import robotsParser from 'robots-parser';
import { pinnedFetch } from '../security/socket-agent.js';
import { isFixtureUrl } from '../capture/fixture-dispatcher.js';

export interface RobotsCheckResult {
  allowed: boolean;
  reason?: string;
  cachedAt?: string;
  origin: string;
}

const RETAINED_HEADERS = ['content-type', 'retry-after', 'etag', 'last-modified', 'cache-control'];

export function getNormalizedOrigin(rawUrl: string): string {
  if (isFixtureUrl(rawUrl)) {
    return 'fixture://local';
  }
  const url = new URL(rawUrl);
  const defaultPort = url.protocol === 'https:' ? '443' : '80';
  const port = url.port || defaultPort;
  return `${url.protocol}//${url.hostname}:${port}`;
}

export class OriginRobotsCache {
  private db: Database.Database;

  constructor(db: Database.Database) {
    this.db = db;
  }

  /**
   * Checks if an origin has an unexpired cached robots.txt entry.
   */
  getCachedRobots(origin: string): {
    raw_content: string;
    http_status: number;
    response_headers: Record<string, string>;
    cached_at: string;
    expires_at: string;
  } | null {
    const row = this.db.prepare(`
      SELECT raw_content, http_status, response_headers, cached_at, expires_at
      FROM robots_cache
      WHERE origin = ? AND expires_at > datetime('now')
    `).get(origin) as any;

    if (!row) return null;

    return {
      raw_content: row.raw_content,
      http_status: row.http_status,
      response_headers: JSON.parse(row.response_headers || '{}'),
      cached_at: row.cached_at,
      expires_at: row.expires_at,
    };
  }

  /**
   * Fetches (or loads from cache) the origin's robots.txt and verifies crawl permission.
   */
  async isAllowed(targetUrl: string, userAgent = 'ChangeWatch/1.0'): Promise<RobotsCheckResult> {
    if (isFixtureUrl(targetUrl)) {
      if (targetUrl.includes('disallow-robots')) {
        return {
          allowed: false,
          reason: 'Explicitly disallowed by robots.txt fixture rule',
          origin: 'fixture://local',
        };
      }
      return { allowed: true, origin: 'fixture://local' };
    }

    const origin = getNormalizedOrigin(targetUrl);
    let cached = this.getCachedRobots(origin);

    if (!cached) {
      cached = await this.refreshRobots(origin);
    }

    // If robots.txt resulted in 404 or empty, allow-all
    if (cached.http_status === 404 || !cached.raw_content.trim()) {
      return { allowed: true, origin, cachedAt: cached.cached_at };
    }

    const robotsUrl = `${origin}/robots.txt`;
    const robots = robotsParser(robotsUrl, cached.raw_content);

    const isAllowed = robots.isAllowed(targetUrl, userAgent) ?? true;

    return {
      allowed: isAllowed,
      reason: isAllowed ? undefined : `Disallowed by origin robots.txt rule at ${origin}`,
      cachedAt: cached.cached_at,
      origin,
    };
  }

  /**
   * Refreshes the robots.txt for a given origin from the network and updates the SQLite cache.
   */
  async refreshRobots(origin: string): Promise<{
    raw_content: string;
    http_status: number;
    response_headers: Record<string, string>;
    cached_at: string;
    expires_at: string;
  }> {
    const robotsUrl = `${origin}/robots.txt`;
    let rawContent = '';
    let httpStatus = 200;
    const retainedHeaders: Record<string, string> = {};

    try {
      const response = await pinnedFetch(robotsUrl, { timeoutMs: 5000 });
      httpStatus = response.statusCode;
      rawContent = response.body;

      // Extract and retain specific audit headers
      for (const h of RETAINED_HEADERS) {
        const val = response.headers[h];
        if (val) {
          retainedHeaders[h] = Array.isArray(val) ? val.join(', ') : String(val);
        }
      }
    } catch {
      // Missing or network error -> treat as 404 non-existent robots.txt
      httpStatus = 404;
      rawContent = '';
    }

    // Cache expiration: 24 hours
    const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();

    this.db.prepare(`
      INSERT INTO robots_cache (origin, raw_content, http_status, response_headers, expires_at)
      VALUES (?, ?, ?, ?, ?)
      ON CONFLICT(origin) DO UPDATE SET
        raw_content = excluded.raw_content,
        http_status = excluded.http_status,
        response_headers = excluded.response_headers,
        cached_at = datetime('now'),
        expires_at = excluded.expires_at
    `).run(origin, rawContent, httpStatus, JSON.stringify(retainedHeaders), expiresAt);

    return {
      raw_content: rawContent,
      http_status: httpStatus,
      response_headers: retainedHeaders,
      cached_at: new Date().toISOString(),
      expires_at: expiresAt,
    };
  }

  /**
   * Helper to manually insert or mock a robots.txt entry (for tests).
   */
  setMockRobots(origin: string, rawContent: string, httpStatus = 200, headers: Record<string, string> = {}): void {
    const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
    this.db.prepare(`
      INSERT INTO robots_cache (origin, raw_content, http_status, response_headers, expires_at)
      VALUES (?, ?, ?, ?, ?)
      ON CONFLICT(origin) DO UPDATE SET
        raw_content = excluded.raw_content,
        http_status = excluded.http_status,
        response_headers = excluded.response_headers,
        cached_at = datetime('now'),
        expires_at = excluded.expires_at
    `).run(origin, rawContent, httpStatus, JSON.stringify(headers), expiresAt);
  }
}
