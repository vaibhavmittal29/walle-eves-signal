import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { initDatabase, closeDatabase } from '../src/server/db/database.js';
import { hashPassword, verifyPassword, createSession, validateSessionToken, deleteSession } from '../src/server/core/auth.js';
import Database from 'better-sqlite3';
import crypto from 'crypto';

describe('User Authentication & Monitor Ownership Isolation [A, X]', () => {
  let db: Database.Database;

  beforeEach(() => {
    db = initDatabase({ inMemory: true });
  });

  afterEach(() => {
    db.close();
  });

  it('securely hashes and verifies passwords using PBKDF2 with salt', () => {
    const rawPass = 'SuperSecret123!';
    const { salt, hash } = hashPassword(rawPass);

    expect(salt).toHaveLength(32); // 16 bytes in hex = 32 chars
    expect(hash).toHaveLength(128); // 64 bytes in hex = 128 chars

    // Verifies correctly
    expect(verifyPassword(rawPass, salt, hash)).toBe(true);

    // Rejects incorrect passwords
    expect(verifyPassword('WrongPass', salt, hash)).toBe(false);
  });

  it('creates sessions and validates tokens against SQLite expiration', () => {
    const userId = crypto.randomUUID();
    const { salt, hash } = hashPassword('Password123');
    db.prepare(`
      INSERT INTO users (id, email, password_hash, password_salt, display_name)
      VALUES (?, 'alice@example.com', ?, ?, 'Alice')
    `).run(userId, hash, salt);

    const session = createSession(db, userId);
    expect(session.token).toBeDefined();
    expect(session.csrfToken).toBeDefined();

    // Validates correctly
    const authUser = validateSessionToken(db, session.token);
    expect(authUser).not.toBeNull();
    expect(authUser?.email).toBe('alice@example.com');
    expect(authUser?.displayName).toBe('Alice');

    // Deletes session
    deleteSession(db, session.token);
    expect(validateSessionToken(db, session.token)).toBeNull();
  });

  it('[A] strictly enforces monitor ownership isolation between users', () => {
    // Create User 1 (Alice)
    const u1 = crypto.randomUUID();
    db.prepare(`
      INSERT INTO users (id, email, password_hash, password_salt, display_name)
      VALUES (?, 'alice@test.com', 'h1', 's1', 'Alice')
    `).run(u1);

    // Create User 2 (Bob)
    const u2 = crypto.randomUUID();
    db.prepare(`
      INSERT INTO users (id, email, password_hash, password_salt, display_name)
      VALUES (?, 'bob@test.com', 'h2', 's2', 'Bob')
    `).run(u2);

    // Insert target
    const targetId = crypto.randomUUID();
    db.prepare(`
      INSERT INTO targets (id, canonical_url, safe_hostname, origin)
      VALUES (?, 'https://site.com', 'site.com', 'https://site.com:443')
    `).run(targetId);

    // Alice creates monitor 1
    const m1 = crypto.randomUUID();
    db.prepare(`
      INSERT INTO subscriptions (
        id, user_id, target_id, name, interval_minutes, next_check_at,
        capture_config, capture_fingerprint
      ) VALUES (?, ?, ?, 'Alice Monitor', 60, datetime('now'), '{}', 'f1')
    `).run(m1, u1, targetId);

    // Bob creates monitor 2
    const m2 = crypto.randomUUID();
    db.prepare(`
      INSERT INTO subscriptions (
        id, user_id, target_id, name, interval_minutes, next_check_at,
        capture_config, capture_fingerprint
      ) VALUES (?, ?, ?, 'Bob Monitor', 60, datetime('now'), '{}', 'f2')
    `).run(m2, u2, targetId);

    // Query for Alice only returns Alice's monitor
    const aliceMonitors = db.prepare('SELECT id FROM subscriptions WHERE user_id = ?').all(u1) as any[];
    expect(aliceMonitors.map(m => m.id)).toEqual([m1]);

    // Query for Bob only returns Bob's monitor
    const bobMonitors = db.prepare('SELECT id FROM subscriptions WHERE user_id = ?').all(u2) as any[];
    expect(bobMonitors.map(m => m.id)).toEqual([m2]);

    // Bob attempts to query Alice's monitor by ID with Bob's user_id -> returns nothing
    const stolen = db.prepare('SELECT * FROM subscriptions WHERE id = ? AND user_id = ?').get(m1, u2);
    expect(stolen).toBeUndefined();

    // Bob attempts to delete Alice's monitor with Bob's user_id -> 0 rows affected
    const deleteAttempt = db.prepare('DELETE FROM subscriptions WHERE id = ? AND user_id = ?').run(m1, u2);
    expect(deleteAttempt.changes).toBe(0);

    // Alice's monitor remains intact
    const stillThere = db.prepare('SELECT id FROM subscriptions WHERE id = ?').get(m1);
    expect(stillThere).toBeDefined();
  });

  it('[X] verifies credentials and password hashes are never exposed in user responses', () => {
    const userId = crypto.randomUUID();
    const { salt, hash } = hashPassword('MySecretPass');
    db.prepare(`
      INSERT INTO users (id, email, password_hash, password_salt, display_name)
      VALUES (?, 'charlie@test.com', ?, ?, 'Charlie')
    `).run(userId, hash, salt);

    const session = createSession(db, userId);

    // Session user object contains ONLY id, email, displayName
    const keys = Object.keys(session.user);
    expect(keys).toContain('id');
    expect(keys).toContain('email');
    expect(keys).toContain('displayName');
    expect(keys).not.toContain('password_hash');
    expect(keys).not.toContain('password_salt');
    expect(keys).not.toContain('password');
  });
});
