import * as cheerio from 'cheerio';
import { NoiseFilters } from '../../../shared/types.js';

// Noise filter regex patterns
export const TIMESTAMP_PATTERNS = [
  /\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b/gi, // ISO 8601
  /\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\s+\d{2}:\d{2}:\d{2}\s+(?:GMT|UTC|[+-]\d{4})\b/gi, // RFC 2822
  /\b\d{1,2}\s+(?:seconds|minutes|hours|days|weeks|months|years)\s+ago\b/gi, // Relative times
  /\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)\b/g, // 12-hour time
  /\b(?:just now|a moment ago|recently updated)\b/gi,
];

export const COUNTER_PATTERNS = [
  /\b(?:visitor|views?|visits?|hits?|downloads?)\s*(?:#|count|:)?\s*[\d,.]+/gi,
  /\b#?\d{1,3}(?:,\d{3})+\s*(?:visitors?|views?)\b/gi,
  /\b\d+\s*active\s*(?:users?|nodes?|sessions?)\b/gi,
];

export const TOKEN_PATTERNS = [
  /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi, // UUID
  /\b(?:csrf[_-]?token|session[_-]?id|nonce|auth[_-]?token|api[_-]?key)[:=]\s*["']?[a-zA-Z0-9_\-+/]{16,}["']?/gi,
  /\b[0-9a-f]{32,64}\b/gi, // Long hex hashes/tokens
];

export function applyNoiseFilterRules(text: string, filters: NoiseFilters): string {
  let cleaned = text;

  if (filters.timestamps) {
    for (const pattern of TIMESTAMP_PATTERNS) {
      cleaned = cleaned.replace(pattern, '[TIMESTAMP]');
    }
  }

  if (filters.counters) {
    for (const pattern of COUNTER_PATTERNS) {
      cleaned = cleaned.replace(pattern, '[COUNTER]');
    }
  }

  if (filters.tokens) {
    for (const pattern of TOKEN_PATTERNS) {
      cleaned = cleaned.replace(pattern, '[TOKEN]');
    }
  }

  return cleaned;
}

export function extractNormalizedText(
  sanitizedDom: string,
  options: {
    includeSelectors?: string[];
    ignoreSelectors?: string[];
    noiseFilters?: NoiseFilters;
  } = {}
): string {
  const includeSelectors = options.includeSelectors || [];
  const ignoreSelectors = options.ignoreSelectors || [];
  const noiseFilters = options.noiseFilters;

  const $ = cheerio.load(sanitizedDom);

  // 1. Remove ignore_selectors from the DOM
  for (const sel of ignoreSelectors) {
    if (sel && sel.trim()) {
      $(sel).remove();
    }
  }

  // 2. Insert newlines for block-level elements and line breaks
  $('br').replaceWith('\n');
  $('p, div, h1, h2, h3, h4, h5, h6, li, section, article, header, footer, tr, table').each((_, el) => {
    $(el).append('\n');
  });

  // 3. Extract text from include_selectors or entire body
  let rawExtracted = '';
  if (includeSelectors.length > 0) {
    const parts: string[] = [];
    for (const sel of includeSelectors) {
      if (sel && sel.trim()) {
        $(sel).each((_, el) => {
          parts.push($(el).text());
        });
      }
    }
    rawExtracted = parts.join('\n');
  } else {
    rawExtracted = $('body').length > 0 ? $('body').text() : $.text();
  }

  // 3. Normalize lines (trim and collapse consecutive whitespace)
  const lines = rawExtracted
    .split('\n')
    .map(line => line.replace(/[ \t]+/g, ' ').trim())
    .filter(line => line.length > 0);

  let normalized = lines.join('\n');

  // 4. Apply noise filters if requested
  if (noiseFilters) {
    normalized = applyNoiseFilterRules(normalized, noiseFilters);
    // Re-clean whitespace after replacements
    normalized = normalized
      .split('\n')
      .map(line => line.replace(/[ \t]+/g, ' ').trim())
      .filter(line => line.length > 0)
      .join('\n');
  }

  return normalized;
}
