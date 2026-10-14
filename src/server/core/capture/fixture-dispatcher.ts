import { FIXTURES, FixtureDefinition } from '../../../fixtures/index.js';

export interface FixtureResponse {
  statusCode: number;
  headers: Record<string, string>;
  body: string;
  finalUrl: string;
}

// In-memory overrides for dynamic test runs (e.g. simulated updates)
const fixtureOverrides = new Map<string, Partial<FixtureDefinition>>();

export function isFixtureUrl(url: string): boolean {
  return url.startsWith('fixture://');
}

export function parseFixtureId(url: string): string {
  const clean = url.replace(/^fixture:\/\//, '');
  const id = clean.split('/')[0].split('?')[0];
  return id;
}

export function setFixtureOverride(id: string, override: Partial<FixtureDefinition>): void {
  fixtureOverrides.set(id, override);
}

export function clearFixtureOverrides(): void {
  fixtureOverrides.clear();
}

export function dispatchFixture(url: string): FixtureResponse {
  const id = parseFixtureId(url);
  const baseFixture = FIXTURES[id];

  if (!baseFixture) {
    throw new Error(`Fixture not found for ID "${id}" in URL: ${url}`);
  }

  const override = fixtureOverrides.get(id);
  const fixture = { ...baseFixture, ...override };

  return {
    statusCode: fixture.statusCode,
    headers: fixture.headers || { 'content-type': 'text/html; charset=utf-8' },
    body: fixture.html,
    finalUrl: url,
  };
}
