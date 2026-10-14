import crypto from 'crypto';

/**
 * Computes deterministic SHA-256 hash of normalized text.
 */
export function computeContentHash(text: string): string {
  return crypto.createHash('sha256').update(text, 'utf8').digest('hex');
}
