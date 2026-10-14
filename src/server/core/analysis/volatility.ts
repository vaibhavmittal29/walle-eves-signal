import * as diff from 'diff';
import { extractNormalizedText } from './normalizer.js';
import { executeCapture } from '../capture/capture-engine.js';
import { computeCaptureFingerprint } from '../config.js';

export interface VolatilityProbeResult {
  isNoisy: boolean;
  volatilityPercentage: number;
  unstableLines: string[];
  suggestedFilters: {
    timestamps: boolean;
    counters: boolean;
    tokens: boolean;
  };
  totalLines: number;
  changedLinesCount: number;
}

export function detectUnstableLines(textA: string, textB: string): {
  volatilityPercentage: number;
  unstableLines: string[];
  isNoisy: boolean;
  totalLines: number;
  changedLinesCount: number;
} {
  const lineDiff = diff.diffLines(textA, textB);
  const unstableLines: string[] = [];
  let totalLines = 0;
  let changedLinesCount = 0;

  for (const part of lineDiff) {
    const lines = part.value.split('\n').filter(l => l.trim().length > 0);
    totalLines += lines.length;

    if (part.added || part.removed) {
      changedLinesCount += lines.length;
      for (const line of lines) {
        if (!unstableLines.includes(line)) {
          unstableLines.push(line);
        }
      }
    }
  }

  const volatilityPercentage = totalLines > 0 ? (changedLinesCount / totalLines) * 100 : 0;
  const isNoisy = volatilityPercentage > 70;

  return {
    volatilityPercentage: Math.round(volatilityPercentage * 100) / 100,
    unstableLines,
    isNoisy,
    totalLines,
    changedLinesCount,
  };
}

/**
 * Runs two quick captures back-to-back to probe for intrinsic DOM volatility and suggest filters.
 */
export async function runVolatilityProbe(
  url: string,
  rawConfig: unknown = {},
  delayMs = 500
): Promise<VolatilityProbeResult> {
  const { parsed } = computeCaptureFingerprint(rawConfig);

  // Capture 1
  const cap1 = await executeCapture(url, parsed);
  if (!cap1.capture) {
    throw new Error(`Probe failed on first capture: ${cap1.classification.reason}`);
  }

  // Inter-capture settling delay
  if (delayMs > 0) {
    await new Promise(r => setTimeout(r, delayMs));
  }

  // Capture 2
  const cap2 = await executeCapture(url, parsed);
  if (!cap2.capture) {
    throw new Error(`Probe failed on second capture: ${cap2.classification.reason}`);
  }

  const text1 = extractNormalizedText(cap1.capture.sanitizedDom);
  const text2 = extractNormalizedText(cap2.capture.sanitizedDom);

  const analysis = detectUnstableLines(text1, text2);

  // Inspect unstable lines for timestamp, counter, or token patterns
  const sample = analysis.unstableLines.join('\n');
  const hasTimestamps = /\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}|ago|recently|just now)\b/i.test(sample);
  const hasCounters = /\b(?:visitor|views?|visits?|#\d+|\d+\s*active)\b/i.test(sample);
  const hasTokens = /\b(?:[0-9a-f]{8}-[0-9a-f]{4}|csrf|session|token|[0-9a-f]{32,})\b/i.test(sample);

  return {
    ...analysis,
    suggestedFilters: {
      timestamps: hasTimestamps,
      counters: hasCounters,
      tokens: hasTokens,
    },
  };
}
