import { Router, Request, Response } from 'express';
import crypto from 'crypto';
import { z } from 'zod';
import { getDatabase } from '../db/database.js';
import { hashPassword, verifyPassword, createSession, deleteSession, requireAuth, AuthenticatedRequest } from '../core/auth.js';

const router = Router();

const RegisterSchema = z.object({
  email: z.string().email().toLowerCase(),
  password: z.string().min(8, 'Password must be at least 8 characters long'),
  displayName: z.string().min(2, 'Display name must be at least 2 characters'),
});

const LoginSchema = z.object({
  email: z.string().email().toLowerCase(),
  password: z.string().min(1, 'Password is required'),
});

router.post('/register', (req: Request, res: Response) => {
  const parseResult = RegisterSchema.safeParse(req.body);
  if (!parseResult.success) {
    res.status(400).json({ error: parseResult.error.errors[0].message });
    return;
  }

  const { email, password, displayName } = parseResult.data;
  const db = getDatabase();

  const existing = db.prepare('SELECT id FROM users WHERE email = ?').get(email);
  if (existing) {
    res.status(409).json({ error: 'User with this email already exists' });
    return;
  }

  const userId = crypto.randomUUID();
  const { salt, hash } = hashPassword(password);

  db.prepare(`
    INSERT INTO users (id, email, password_hash, password_salt, display_name)
    VALUES (?, ?, ?, ?, ?)
  `).run(userId, email, hash, salt, displayName);

  const session = createSession(db, userId);

  res.cookie('changewatch_session', session.token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 7 * 24 * 60 * 60 * 1000,
  });

  res.status(201).json({
    user: session.user,
    token: session.token,
    csrfToken: session.csrfToken,
    expiresAt: session.expiresAt,
  });
});

router.post('/login', (req: Request, res: Response) => {
  const parseResult = LoginSchema.safeParse(req.body);
  if (!parseResult.success) {
    res.status(400).json({ error: parseResult.error.errors[0].message });
    return;
  }

  const { email, password } = parseResult.data;
  const db = getDatabase();

  const user = db.prepare('SELECT id, email, password_hash, password_salt, display_name FROM users WHERE email = ?').get(email) as any;
  if (!user || !verifyPassword(password, user.password_salt, user.password_hash)) {
    res.status(401).json({ error: 'Invalid email or password' });
    return;
  }

  const session = createSession(db, user.id);

  res.cookie('changewatch_session', session.token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 7 * 24 * 60 * 60 * 1000,
  });

  res.json({
    user: session.user,
    token: session.token,
    csrfToken: session.csrfToken,
    expiresAt: session.expiresAt,
  });
});

router.post('/logout', (req: Request, res: Response) => {
  const rawToken = req.headers.authorization?.startsWith('Bearer ')
    ? req.headers.authorization.substring(7).trim()
    : req.cookies?.changewatch_session;

  if (rawToken) {
    const db = getDatabase();
    deleteSession(db, rawToken);
  }

  res.clearCookie('changewatch_session');
  res.json({ success: true, message: 'Logged out successfully' });
});

router.get('/me', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  res.json({
    user: req.user,
  });
});

export default router;
