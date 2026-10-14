export class DomainRateLimiter {
  private activeNavigations = new Set<string>();
  private lastFinishedTimestamps = new Map<string, number>();
  private minGapMs: number;

  constructor(minGapMs = 10000) {
    this.minGapMs = minGapMs;
  }

  canNavigate(hostname: string): { allowed: boolean; waitMs?: number } {
    if (this.activeNavigations.has(hostname)) {
      return { allowed: false, waitMs: this.minGapMs };
    }

    const lastFinished = this.lastFinishedTimestamps.get(hostname);
    if (lastFinished) {
      const elapsed = Date.now() - lastFinished;
      if (elapsed < this.minGapMs) {
        return { allowed: false, waitMs: this.minGapMs - elapsed };
      }
    }

    return { allowed: true };
  }

  startNavigation(hostname: string): void {
    this.activeNavigations.add(hostname);
  }

  finishNavigation(hostname: string): void {
    this.activeNavigations.delete(hostname);
    this.lastFinishedTimestamps.set(hostname, Date.now());
  }

  clear(): void {
    this.activeNavigations.clear();
    this.lastFinishedTimestamps.clear();
  }
}

/**
 * Calculates next check time applying ±10% jitter to prevent thundering herd problems.
 */
export function calculateJitteredNextCheck(intervalMinutes: number, fromDate = new Date()): Date {
  const jitterFactor = 0.9 + Math.random() * 0.2; // Range [0.90, 1.10]
  const jitteredMinutes = intervalMinutes * jitterFactor;
  const nextTimeMs = fromDate.getTime() + jitteredMinutes * 60 * 1000;
  return new Date(nextTimeMs);
}
