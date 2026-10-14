export interface FixtureDefinition {
  id: string;
  name: string;
  description: string;
  statusCode: number;
  headers?: Record<string, string>;
  html: string;
}

export const FIXTURES: Record<string, FixtureDefinition> = {
  'stable-clean': {
    id: 'stable-clean',
    name: 'Stable Clean Page',
    description: 'Static semantic webpage with stable text and headings',
    statusCode: 200,
    headers: { 'content-type': 'text/html; charset=utf-8' },
    html: `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Engineering Department Announcements</title>
</head>
<body>
  <header>
    <h1>School of Computer Science & Engineering</h1>
    <nav><a href="#about">About</a> | <a href="#news">News</a></nav>
  </header>
  <main id="content">
    <h2>Fall 2026 Curriculum Updates</h2>
    <p class="announcement">All distributed systems and web security laboratory sessions will start on Monday, November 3.</p>
    <article>
      <h3>Laboratory Assignment 1</h3>
      <p>Please review the protocol specifications before submitting your pull requests.</p>
    </article>
  </main>
  <footer>
    <p>&copy; 2026 Academic Institute. All rights reserved.</p>
  </footer>
</body>
</html>`,
  },

  'content-modified': {
    id: 'content-modified',
    name: 'Content Modified Page',
    description: 'Genuine meaningful content changes to headline and article',
    statusCode: 200,
    headers: { 'content-type': 'text/html; charset=utf-8' },
    html: `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Engineering Department Announcements</title>
</head>
<body>
  <header>
    <h1>School of Computer Science & Engineering</h1>
    <nav><a href="#about">About</a> | <a href="#news">News</a></nav>
  </header>
  <main id="content">
    <h2>Fall 2026 Curriculum Updates (REVISED)</h2>
    <p class="announcement">URGENT: Distributed systems laboratory sessions have been rescheduled to Wednesday, November 5.</p>
    <article>
      <h3>Laboratory Assignment 1 - Deadline Extension</h3>
      <p>Submission deadline has been extended by 48 hours for all sections.</p>
    </article>
  </main>
  <footer>
    <p>&copy; 2026 Academic Institute. All rights reserved.</p>
  </footer>
</body>
</html>`,
  },

  'noisy-timestamps': {
    id: 'noisy-timestamps',
    name: 'Noisy Timestamps & Counters',
    description: 'Page with transient timestamps, random session tokens, and visitor counters',
    statusCode: 200,
    headers: { 'content-type': 'text/html; charset=utf-8' },
    html: `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Live Status</title></head>
<body>
  <h1>Server Cluster Status</h1>
  <div class="metrics">
    <p>Last checked: 2026-10-14T12:38:46.124Z (5 seconds ago)</p>
    <p>Session ID: f9b8c2d1-4e7a-4290-b3fa-9d18e87491bb</p>
    <p>Visitor #48201 has visited this page.</p>
    <span class="token">CSRF_TOKEN: 8f9a2b3c4d5e6f70a1b2c3d4e5f6</span>
  </div>
  <main id="content">
    <h2>Core Service: Operational</h2>
    <p>All database instances and worker queues are operating within normal latencies.</p>
  </main>
</body>
</html>`,
  },

  'anti-bot-challenge': {
    id: 'anti-bot-challenge',
    name: 'Anti-Bot / Cloudflare Challenge',
    description: 'Simulates an active anti-bot challenge page (should classify as BLOCKED)',
    statusCode: 200,
    headers: { 'content-type': 'text/html; charset=utf-8' },
    html: `<!DOCTYPE html>
<html>
<head><title>Just a moment...</title></head>
<body>
  <div id="challenge-stage">
    <h1>Attention Required! | Cloudflare</h1>
    <p>Please verify you are human to access the destination server.</p>
    <div class="cf-turnstile" data-sitekey="0x4AAAAAA"></div>
    <div id="cf-please-wait">Checking your browser before accessing site...</div>
  </div>
</body>
</html>`,
  },

  'http-500-outage': {
    id: 'http-500-outage',
    name: 'HTTP 500 Internal Server Error',
    description: 'Simulates a backend crash/outage (should classify as ERROR)',
    statusCode: 500,
    headers: { 'content-type': 'text/html; charset=utf-8' },
    html: `<!DOCTYPE html>
<html>
<head><title>500 Internal Server Error</title></head>
<body>
  <h1>500 Internal Server Error</h1>
  <p>The upstream database cluster did not respond within the allocated timeout.</p>
</body>
</html>`,
  },

  'http-403-forbidden': {
    id: 'http-403-forbidden',
    name: 'HTTP 403 Forbidden',
    description: 'Simulates an unauthorized/forbidden response (should classify as BLOCKED)',
    statusCode: 403,
    headers: { 'content-type': 'text/html; charset=utf-8' },
    html: `<!DOCTYPE html>
<html>
<head><title>403 Forbidden</title></head>
<body>
  <h1>Access Denied</h1>
  <p>You do not have permission to view this resource.</p>
</body>
</html>`,
  },

  'disallow-robots': {
    id: 'disallow-robots',
    name: 'Robots.txt Disallowed Page',
    description: 'Simulates a page explicitly blocked by RFC 9309 robots.txt',
    statusCode: 200,
    headers: { 'content-type': 'text/html; charset=utf-8' },
    html: `<!DOCTYPE html>
<html>
<head><title>Private Internal Index</title></head>
<body>
  <h1>Confidential Project Documents</h1>
  <p>This path is marked Disallow in robots.txt.</p>
</body>
</html>`,
  },

  'css-selector-shifts': {
    id: 'css-selector-shifts',
    name: 'CSS Selector Layout Shift',
    description: 'Content is identical but DOM tree structure and class wrappers have shifted',
    statusCode: 200,
    headers: { 'content-type': 'text/html; charset=utf-8' },
    html: `<!DOCTYPE html>
<html>
<head><title>Product Catalog</title></head>
<body>
  <div class="wrapper-new-grid">
    <section class="catalog-item-v2" data-id="p-100">
      <span class="title">Wireless Noise-Cancelling Headphones</span>
      <span class="price">$199.99</span>
    </section>
  </div>
</body>
</html>`,
  },

  'javascript-rendered': {
    id: 'javascript-rendered',
    name: 'Client-Side JavaScript Rendered Page',
    description: 'Requires JS execution engine (Playwright) to inject dynamic text into the DOM',
    statusCode: 200,
    headers: { 'content-type': 'text/html; charset=utf-8' },
    html: `<!DOCTYPE html>
<html>
<head><title>SPA Application</title></head>
<body>
  <div id="app">Loading application...</div>
  <script>
    setTimeout(function() {
      document.getElementById('app').innerHTML = '<h2>Dashboard Loaded via Client JavaScript</h2><p>Active nodes: 42</p>';
    }, 50);
  </script>
</body>
</html>`,
  },

  'subresource-heavy': {
    id: 'subresource-heavy',
    name: 'Subresource Heavy Page',
    description: 'Page with multiple stylesheet, image, and font links to test request interception',
    statusCode: 200,
    headers: { 'content-type': 'text/html; charset=utf-8' },
    html: `<!DOCTYPE html>
<html>
<head>
  <title>Subresource Heavy Page</title>
  <link rel="stylesheet" href="/assets/style1.css">
  <link rel="stylesheet" href="/assets/style2.css">
  <script src="/assets/analytics.js"></script>
</head>
<body>
  <h1>Heavy Media Portal</h1>
  <img src="/images/banner1.png" alt="Banner 1">
  <img src="/images/banner2.png" alt="Banner 2">
  <p>Content loaded alongside assets.</p>
</body>
</html>`,
  },

  'empty-dom': {
    id: 'empty-dom',
    name: 'Empty DOM / 0-byte Content',
    description: 'Blank body to verify empty response error handling',
    statusCode: 200,
    headers: { 'content-type': 'text/html; charset=utf-8' },
    html: ``,
  },

  'unstable-flapping': {
    id: 'unstable-flapping',
    name: 'Flapping Page (A/B Alternating)',
    description: 'Page that randomly flips between Version A and Version B',
    statusCode: 200,
    headers: { 'content-type': 'text/html; charset=utf-8' },
    html: `<!DOCTYPE html>
<html>
<body>
  <h1>Stock Ticker</h1>
  <p class="price">Price: $102.50 (Updated)</p>
</body>
</html>`,
  },

  'noisy-high-volatility': {
    id: 'noisy-high-volatility',
    name: 'High Volatility (>70% Noise)',
    description: 'Page where over 70% of lines are constantly mutating',
    statusCode: 200,
    headers: { 'content-type': 'text/html; charset=utf-8' },
    html: `<!DOCTYPE html>
<html>
<body>
  <p>Ticker 1: 59382</p>
  <p>Ticker 2: 12048</p>
  <p>Ticker 3: 94819</p>
  <p>Ticker 4: 38472</p>
  <p>Ticker 5: 19284</p>
  <p>Ticker 6: 48192</p>
  <p>Ticker 7: 84910</p>
  <p>Ticker 8: 39182</p>
  <p>Core Static Title: Market Overview</p>
</body>
</html>`,
  },

  'websocket-service-worker': {
    id: 'websocket-service-worker',
    name: 'WebSocket & Service Worker Test',
    description: 'Attempts to register Service Worker and open WebSocket to verify interception',
    statusCode: 200,
    headers: { 'content-type': 'text/html; charset=utf-8' },
    html: `<!DOCTYPE html>
<html>
<head><title>Interception Test</title></head>
<body>
  <h1>Security Interception Test</h1>
  <div id="sw-status">SW Not Registered</div>
  <div id="ws-status">WS Not Connected</div>
  <script>
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').then(function() {
        document.getElementById('sw-status').innerText = 'SW Registered';
      }).catch(function(e) {
        document.getElementById('sw-status').innerText = 'SW Blocked';
      });
    }
    try {
      var ws = new WebSocket('ws://echo.websocket.events');
      ws.onopen = function() {
        document.getElementById('ws-status').innerText = 'WS Connected';
      };
      ws.onerror = function() {
        document.getElementById('ws-status').innerText = 'WS Closed/Blocked';
      };
    } catch(e) {
      document.getElementById('ws-status').innerText = 'WS Blocked';
    }
  </script>
</body>
</html>`,
  },
};
