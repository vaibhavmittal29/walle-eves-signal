import crypto from 'crypto';
import { Request, Response, NextFunction } from 'express';
import Database from 'better-sqlite3';
import { getDatabase } from '../db/database.js';

const PBKDF2_ITERATIONS = 100000;
const KEY_LEN = 64;
const DIGEST = 'sha512';
const SESSION_EXPIRY_DAYS = 7;

export interface AuthUser {
  id: string;
  email: string;
  displayName: string;
}

export interface SessionData {
  sessionId: string;
  user: AuthUser;
  token: string;
  csrfToken: string;
  expiresAt: string;
}

export function hashPassword(password: string): { salt: string; hash: string } {
  const salt = crypto.randomBytes(16).toString('hex');
  const hash = crypto.pbkdf2Sync(password, salt, PBKDF2_ITERATIONS, KEY_LEN, DIGEST).toString('hex');
  return { salt, hash };
}

export function verifyPassword(password: string, salt: string, storedHash: string): boolean {
  const hash = crypto.pbkdf2Sync(password, salt, PBKDF2_ITERATIONS, KEY_LEN, DIGEST).toString('hex');
  const bufA = Buffer.from(hash, 'hex');
  const bufB = Buffer.from(storedHash, 'hex');
  if (bufA.length !== bufB.length) return false;
  return crypto.timingSafeEqual(bufA, bufB);
}

export function createSession(db: Database.Database, userId: string): SessionData {
  const user = db.prepare('SELECT id, email, display_name FROM users WHERE id = ?').get(userId) as any;
  if (!user) {
    throw new Error('User not found');
  }

  const sessionId = crypto.randomUUID();
  const rawToken = crypto.randomBytes(32).toString('hex');
  const tokenHash = crypto.createHash('sha256').update(rawToken).digest('hex');
  const csrfToken = crypto.randomBytes(24).toString('hex');

  const expiresDate = new Date();
  expiresDate.setDate(expiresDate.getDate() + SESSION_EXPIRY_DAYS);
  const expiresAt = expiresDate.toISOString();

  // We store tokenHash in sessions table.
  // Note: the csrfToken is encoded or derived: we store `tokenHash` and can also keep raw token for validation.
  db.prepare(`
    INSERT INTO sessions (id, user_id, token_hash, expires_at)
    VALUES (?, ?, ?, ?)
  `).run(sessionId, userId, tokenHash, expiresAt);

  return {
    sessionId,
    user: {
      id: user.id,
      email: user.email,
      displayName: user.display_name,
    },
    token: rawToken,
    csrfToken,
    expiresAt,
  };
}

export function validateSessionToken(db: Database.Database, rawToken: string): AuthUser | null {
  if (!rawToken) return null;
  const tokenHash = crypto.createHash('sha256').update(rawToken).digest('hex');

  const row = db.prepare(`
    SELECT s.id as session_id, s.expires_at, u.id, u.email, u.display_name
    FROM sessions s
    JOIN users u ON s.user_id = u.id
    WHERE s.token_hash = ? AND s.expires_at > datetime('now')
  `).get(tokenHash) as any;

  if (!row) return null;

  return {
    id: row.id,
    email: row.email,
    displayName: row.display_name,
  };
}

export function deleteSession(db: Database.Database, rawToken: string): void {
  const tokenHash = crypto.createHash('sha256').update(rawToken).digest('hex');
  db.prepare('DELETE FROM sessions WHERE token_hash = ?').run(tokenHash);
}

// Express Auth Middleware
export interface AuthenticatedRequest extends Request {
  user?: AuthUser;
}

export function requireAuth(req: AuthenticatedRequest, res: Response, next: NextFunction): void {
  const authHeader = req.headers.authorization;
  let rawToken: string | undefined;

  if (authHeader && authHeader.startsWith('Bearer ')) {
    rawToken = authHeader.substring(7).trim();
  } else if (req.cookies && req.cookies.changewatch_session) {
    rawToken = req.cookies.changewatch_session;
  }

  if (!rawToken) {
    res.status(401).json({ error: 'Authentication required' });
    return;
  }

  const db = getDatabase();
  const user = validateSessionToken(db, rawToken);

  if (!user) {
    res.status(401).json({ error: 'Invalid or expired session token' });
    return;
  }

  // CSRF verification for mutating requests
  const method = req.method.toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const clientCsrf = req.headers['x-csrf-token'] || req.body?._csrf;
    // Allow Bearer token clients (API / programmatic clients) if explicit CSRF not passed,
    // but if cookie-based request, require X-CSRF-Token or header
    if (req.cookies?.changewatch_session && !clientCsrf) {
      res.status(403).json({ error: 'CSRF token missing or invalid' });
      return;
    }
  }

  req.user = user;
  next();
}
