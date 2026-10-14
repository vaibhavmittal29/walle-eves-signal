import { Router, Response } from 'express';
import crypto from 'crypto';
import { z } from 'zod';
import { getDatabase } from '../db/database.js';
import { requireAuth, AuthenticatedRequest } from '../core/auth.js';

const router = Router();

const DestinationSchema = z.object({
  channel: z.enum(['discord', 'telegram', 'email', 'in_app']),
  destination_config: z.record(z.any()),
  enabled: z.boolean().default(true),
});

// GET /api/outbox - List notification outbox for user
router.get('/', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const db = getDatabase();
  const userId = req.user!.id;

  const rows = db.prepare(`
    SELECT no.*, ce.event_type, ce.summary, s.name as monitor_name
    FROM notification_outbox no
    JOIN change_events ce ON no.change_event_id = ce.id
    JOIN subscriptions s ON ce.subscription_id = s.id
    WHERE no.user_id = ?
    ORDER BY no.created_at DESC
    LIMIT 50
  `).all(userId);

  const formatted = rows.map((r: any) => ({
    ...r,
    payload: JSON.parse(r.payload || '{}'),
  }));

  res.json({ outbox: formatted });
});

// GET /api/destinations - List configured destinations
router.get('/destinations', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const db = getDatabase();
  const userId = req.user!.id;

  const rows = db.prepare(`
    SELECT id, channel, destination_config, enabled, created_at
    FROM notification_destinations
    WHERE user_id = ?
  `).all(userId);

  const formatted = rows.map((d: any) => {
    const cfg = JSON.parse(d.destination_config || '{}');
    // Mask sensitive tokens / webhook URLs for security
    const masked: Record<string, string> = {};
    for (const [k, v] of Object.entries(cfg)) {
      if (typeof v === 'string' && v.length > 8) {
        masked[k] = `${v.slice(0, 4)}...${v.slice(-4)}`;
      } else {
        masked[k] = '***';
      }
    }
    return {
      ...d,
      destination_config: masked,
      enabled: Boolean(d.enabled),
    };
  });

  res.json({ destinations: formatted });
});

// POST /api/destinations - Add or update a destination
router.post('/destinations', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  const parse = DestinationSchema.safeParse(req.body);
  if (!parse.success) {
    res.status(400).json({ error: parse.error.errors[0].message });
    return;
  }

  const { channel, destination_config, enabled } = parse.data;
  const db = getDatabase();
  const userId = req.user!.id;

  const existing = db.prepare(`
    SELECT id FROM notification_destinations WHERE user_id = ? AND channel = ?
  `).get(userId, channel) as { id: string } | undefined;

  if (existing) {
    db.prepare(`
      UPDATE notification_destinations
      SET destination_config = ?, enabled = ?
      WHERE id = ?
    `).run(JSON.stringify(destination_config), enabled ? 1 : 0, existing.id);
  } else {
    const id = crypto.randomUUID();
    db.prepare(`
      INSERT INTO notification_destinations (id, user_id, channel, destination_config, enabled)
      VALUES (?, ?, ?, ?, ?)
    `).run(id, userId, channel, JSON.stringify(destination_config), enabled ? 1 : 0);
  }

  res.json({ success: true, message: `Destination configured for ${channel}` });
});

export default router;
