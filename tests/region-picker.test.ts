import { describe, it, expect } from 'vitest';
import * as cheerio from 'cheerio';
import { extractNormalizedText } from '../src/server/core/analysis/normalizer.js';

describe('Visual Region Picker & CSS Selector Extraction [U]', () => {
  const sampleHtml = `
    <html>
      <body>
        <div id="page-wrapper">
          <header class="site-header">
            <h1 id="brand-title">ChangeWatch Institute</h1>
          </header>
          <div class="sidebar">
            <ul class="nav-links">
              <li><a href="/home">Home</a></li>
            </ul>
          </div>
          <main id="content" class="content-body">
            <article class="primary-announcement">
              <h2 class="headline">New Research Grant Announced</h2>
              <p class="summary">The 2026 grant cycle is now open for applicants.</p>
            </article>
          </main>
          <footer class="site-footer">
            <p>&copy; 2026 Institute</p>
          </footer>
        </div>
      </body>
    </html>
  `;

  it('[U] extracts targeted text strictly from isolated CSS selector regions', () => {
    // 1. Slicing with include_selectors targeting only #content .headline
    const headlineOnly = extractNormalizedText(sampleHtml, {
      includeSelectors: ['#content .headline'],
    });
    expect(headlineOnly).toBe('New Research Grant Announced');
    expect(headlineOnly).not.toContain('Home');
    expect(headlineOnly).not.toContain('Institute');

    // 2. Slicing with include_selectors targeting #content, but ignoring .summary
    const contentWithoutSummary = extractNormalizedText(sampleHtml, {
      includeSelectors: ['#content'],
      ignoreSelectors: ['.summary'],
    });
    expect(contentWithoutSummary).toContain('New Research Grant Announced');
    expect(contentWithoutSummary).not.toContain('The 2026 grant cycle is now open');

    // 3. Whole page extraction with ignore_selectors stripping sidebar and footer
    const cleanedPage = extractNormalizedText(sampleHtml, {
      ignoreSelectors: ['.sidebar', '.site-footer'],
    });
    expect(cleanedPage).toContain('ChangeWatch Institute');
    expect(cleanedPage).toContain('New Research Grant Announced');
    expect(cleanedPage).not.toContain('Home');
    expect(cleanedPage).not.toContain('&copy;');
  });

  it('evaluates CSS selector stability scores and flags fragile attributes', () => {
    const isFragile = (sel: string) => {
      if ((sel.match(/:nth-child\(\d+\)/g) || []).length >= 2) return true;
      if (/\b(?:css-|sc-|_)[a-z0-9]{5,}\b/i.test(sel)) return true;
      return false;
    };

    // Stable selectors
    expect(isFragile('#content')).toBe(false);
    expect(isFragile('article.primary-announcement h2')).toBe(false);
    expect(isFragile('main#content > .headline')).toBe(false);

    // Fragile selectors (deep nth-child chains or random hashed classes)
    expect(isFragile('div:nth-child(2) > div:nth-child(4) > p:nth-child(1)')).toBe(true);
    expect(isFragile('.sc-bdVaJa.css-1a2b3c4d')).toBe(true);
  });
});
