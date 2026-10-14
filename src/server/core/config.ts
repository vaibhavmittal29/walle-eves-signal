import { z } from 'zod';
import crypto from 'crypto';

export const CaptureConfigBaseSchema = z.object({
  engine: z.enum(['http_dom', 'playwright']).default('http_dom'),
  viewport: z.object({
    width: z.number().int().min(320).max(3840).default(1280),
    height: z.number().int().min(240).max(2160).default(720),
  }).default({ width: 1280, height: 720 }),
  deviceScaleFactor: z.number().min(1).max(3).default(1),
  jsEnabled: z.boolean().default(true),
  userAgent: z.string().min(1).default('ChangeWatch/1.0 (Student Project; VIT Vellore; +contact)'),
  locale: z.string().optional(),
  timezone: z.string().optional(),
  waitStrategy: z.object({
    waitForSelector: z.string().optional(),
    timeoutMs: z.number().int().min(1000).max(30000).default(10000),
  }).default({ timeoutMs: 10000 }),
  customHeaders: z.record(z.string()).optional(),
  screenshotRequired: z.boolean().default(false),
});

export const CaptureConfigSchema = CaptureConfigBaseSchema.superRefine((data, ctx) => {
  if (data.screenshotRequired && data.engine === 'http_dom') {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Screenshots require the Playwright browser engine; incompatible with http_dom',
      path: ['screenshotRequired'],
    });
  }
});

export type CaptureConfig = z.infer<typeof CaptureConfigSchema>;

/**
 * Recursively sorts keys and filters out undefined values for deterministic serialization.
 */
export function canonicalize(obj: any): any {
  if (obj === null || typeof obj !== 'object') {
    return obj;
  }
  if (Array.isArray(obj)) {
    return obj.map(canonicalize);
  }
  const sortedKeys = Object.keys(obj).sort();
  const result: Record<string, any> = {};
  for (const key of sortedKeys) {
    const val = obj[key];
    if (val !== undefined) {
      result[key] = canonicalize(val);
    }
  }
  return result;
}

export function canonicalStringify(obj: any): string {
  return JSON.stringify(canonicalize(obj));
}

export function computeCaptureFingerprint(rawConfig: unknown = {}): {
  parsed: CaptureConfig;
  fingerprint: string;
  canonicalJson: string;
} {
  const parsed = CaptureConfigSchema.parse(rawConfig);
  const canonicalJson = canonicalStringify(parsed);
  const fingerprint = crypto.createHash('sha256').update(canonicalJson).digest('hex');
  return { parsed, fingerprint, canonicalJson };
}
