import { Router, Request, Response } from 'express';
import { FIXTURES } from '../../fixtures/index.js';
import { setFixtureOverride, clearFixtureOverrides } from '../core/capture/fixture-dispatcher.js';

const router = Router();

// GET /api/fixtures - List all available test fixtures
router.get('/', (req: Request, res: Response) => {
  const list = Object.values(FIXTURES).map(f => ({
    id: f.id,
    name: f.name,
    description: f.description,
    statusCode: f.statusCode,
    url: `fixture://${f.id}`,
  }));
  res.json({ fixtures: list });
});

// GET /api/fixtures/:id - Get raw HTML of a fixture
router.get('/:id', (req: Request, res: Response) => {
  const fixtureId = String(req.params.id);
  const fixture = FIXTURES[fixtureId];
  if (!fixture) {
    res.status(404).json({ error: 'Fixture not found' });
    return;
  }
  res.json({ fixture });
});

// POST /api/fixtures/:id/mutate - Simulate dynamic content mutation for test runs
router.post('/:id/mutate', (req: Request, res: Response) => {
  const fixtureId = String(req.params.id);
  const { html, statusCode } = req.body;
  setFixtureOverride(fixtureId, { html, statusCode });
  res.json({ success: true, message: `Fixture ${fixtureId} mutated` });
});

// POST /api/fixtures/reset - Reset all overrides
router.post('/reset', (req: Request, res: Response) => {
  clearFixtureOverrides();
  res.json({ success: true, message: 'All fixture overrides reset' });
});

export default router;
