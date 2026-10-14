import express, { Request, Response, NextFunction } from 'express';
import cookieParser from 'cookie-parser';
import path from 'path';
import { fileURLToPath } from 'url';
import { initDatabase } from './db/database.js';
import authRouter from './api/auth.js';
import monitorsRouter from './api/monitors.js';
import fixturesRouter from './api/fixtures.js';
import outboxRouter from './api/outbox.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export function createExpressApp() {
  const app = express();

  // Basic security & parsing
  app.use(express.json({ limit: '10mb' }));
  app.use(cookieParser());

  // Security Headers
  app.use((req: Request, res: Response, next: NextFunction) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    res.setHeader('X-XSS-Protection', '1; mode=block');
    next();
  });

  // Health endpoint
  app.get('/api/health', (req: Request, res: Response) => {
    res.json({
      status: 'healthy',
      service: 'changewatch',
      version: '1.0.0',
      timestamp: new Date().toISOString(),
    });
  });

  // API Routes
  app.use('/api/auth', authRouter);
  app.use('/api/monitors', monitorsRouter);
  app.use('/api/fixtures', fixturesRouter);
  app.use('/api/outbox', outboxRouter);

  // Global Error Handler
  app.use((err: any, req: Request, res: Response, next: NextFunction) => {
    console.error('Unhandled server error:', err);
    res.status(500).json({
      error: 'Internal server error',
      message: process.env.NODE_ENV === 'production' ? undefined : err.message,
    });
  });

  return app;
}

export async function startServer(port: number = 3000) {
  // Ensure DB initialized
  initDatabase();

  const app = createExpressApp();

  if (process.env.NODE_ENV !== 'production') {
    try {
      const { createServer: createViteServer } = await import('vite');
      const vite = await createViteServer({
        server: { middlewareMode: true },
        appType: 'spa',
      });
      app.use(vite.middlewares);
    } catch (e) {
      console.warn('Vite middleware not loaded, continuing as API only:', e);
    }
  } else {
    const distPath = path.resolve(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  const server = app.listen(port, () => {
    console.log(`ChangeWatch server running at http://localhost:${port}`);
  });

  return { app, server };
}

// Auto-run if executed directly
const isDirectRun = process.argv[1] && (
  process.argv[1].endsWith('server.ts') || 
  process.argv[1].endsWith('server.js')
);
if (isDirectRun) {
  const PORT = parseInt(process.env.PORT || '3000', 10);
  startServer(PORT);
}

