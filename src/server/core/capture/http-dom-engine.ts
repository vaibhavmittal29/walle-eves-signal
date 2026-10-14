import * as cheerio from 'cheerio';
import { CaptureConfig } from '../config.js';
import { pinnedFetch } from '../security/socket-agent.js';
import { isFixtureUrl, dispatchFixture } from './fixture-dispatcher.js';

export interface RawDomCaptureOutput {
  engine: 'http_dom';
  finalUrl: string;
  httpStatus: number;
  sanitizedDom: string;
  rawText: string;
  subresourceCount: number;
  renderingFingerprint: {
    title: string;
    contentLength: number;
    subresources: number;
    timestamp: string;
  };
  durationMs: number;
}

export function sanitizeHtmlDom(html: string): { sanitizedDom: string; rawText: string; title: string; subresourceCount: number } {
  const $ = cheerio.load(html);

  const title = $('title').text().trim();
  
  // Count subresources before stripping
  const scripts = $('script[src]').length;
  const links = $('link[rel="stylesheet"]').length;
  const imgs = $('img[src]').length;
  const subresourceCount = scripts + links + imgs;

  // Sanitize DOM: Strip non-content and executable tags
  $('script, style, noscript, svg, iframe, canvas, meta, link').remove();

  // Insert newlines for block-level elements and line breaks
  $('br').replaceWith('\n');
  $('p, div, h1, h2, h3, h4, h5, h6, li, section, article, header, footer, tr, table').each((_, el) => {
    $(el).append('\n');
  });

  // Clean raw text
  const bodyText = $('body').length > 0 ? $('body').text() : $.text();
  const rawText = bodyText
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 0)
    .join('\n');

  const sanitizedDom = $('body').length > 0 ? $('body').html() || '' : $.html();

  return {
    sanitizedDom,
    rawText,
    title,
    subresourceCount,
  };
}

export async function captureWithHttpDom(
  url: string,
  config: CaptureConfig
): Promise<RawDomCaptureOutput> {
  const startTime = Date.now();

  let httpStatus: number;
  let rawHtml: string;
  let finalUrl: string;

  if (isFixtureUrl(url)) {
    const fixture = dispatchFixture(url);
    httpStatus = fixture.statusCode;
    rawHtml = fixture.body;
    finalUrl = fixture.finalUrl;
  } else {
    const response = await pinnedFetch(url, {
      headers: {
        'User-Agent': config.userAgent,
        ...(config.customHeaders || {}),
      },
      timeoutMs: config.waitStrategy.timeoutMs,
    });
    httpStatus = response.statusCode;
    rawHtml = response.body;
    finalUrl = response.finalUrl;
  }

  const { sanitizedDom, rawText, title, subresourceCount } = sanitizeHtmlDom(rawHtml);
  const durationMs = Date.now() - startTime;

  return {
    engine: 'http_dom',
    finalUrl,
    httpStatus,
    sanitizedDom,
    rawText,
    subresourceCount,
    renderingFingerprint: {
      title,
      contentLength: rawHtml.length,
      subresources: subresourceCount,
      timestamp: new Date().toISOString(),
    },
    durationMs,
  };
}
