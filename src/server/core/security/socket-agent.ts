import http from 'http';
import https from 'https';
import net from 'net';
import tls from 'tls';
import dns from 'dns/promises';
import { validatePublicIp } from './ip-validator.js';

export interface PinnedFetchOptions {
  method?: string;
  headers?: Record<string, string>;
  timeoutMs?: number;
  maxRedirects?: number;
}

export interface PinnedFetchResponse {
  statusCode: number;
  statusMessage: string;
  headers: Record<string, string | string[] | undefined>;
  body: string;
  finalUrl: string;
  resolvedIp: string;
}

/**
 * Resolves a hostname and asserts all resolved IPv4 and IPv6 addresses are public.
 */
export async function resolveAndValidateHostname(hostname: string): Promise<string> {
  // If hostname is directly an IP literal
  const directCheck = validatePublicIp(hostname);
  if (directCheck.reason !== 'INVALID_IP_FORMAT') {
    if (!directCheck.valid) {
      throw new Error(`SSRF Blocked: IP ${hostname} is not a permitted public destination (${directCheck.reason})`);
    }
    return directCheck.ip;
  }

  // Lookup all addresses (both IPv4 and IPv6)
  let addresses: Array<{ address: string; family: number }>;
  try {
    addresses = await dns.lookup(hostname, { all: true });
  } catch (err: any) {
    throw new Error(`DNS resolution failed for hostname "${hostname}": ${err.message}`);
  }

  if (!addresses || addresses.length === 0) {
    throw new Error(`DNS resolution returned no addresses for hostname "${hostname}"`);
  }

  // Check EVERY returned IP
  for (const item of addresses) {
    const val = validatePublicIp(item.address);
    if (!val.valid) {
      throw new Error(`SSRF Blocked: Hostname "${hostname}" resolved to blocked IP ${item.address} (${val.reason})`);
    }
  }

  // Pick the first validated IP
  return addresses[0].address;
}

/**
 * Performs a socket-pinned HTTP/HTTPS request.
 * Directly pins the TCP/TLS socket to the pre-validated IP to eliminate DNS-rebinding attacks.
 */
export async function pinnedFetch(
  rawUrl: string,
  options: PinnedFetchOptions = {},
  redirectCount = 0
): Promise<PinnedFetchResponse> {
  const maxRedirects = options.maxRedirects ?? 5;
  if (redirectCount > maxRedirects) {
    throw new Error(`Exceeded maximum redirect limit of ${maxRedirects}`);
  }

  const url = new URL(rawUrl);
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new Error(`Unsupported URL protocol "${url.protocol}". Only http: and https: are supported.`);
  }

  const isHttps = url.protocol === 'https:';
  const defaultPort = isHttps ? 443 : 80;
  const port = url.port ? parseInt(url.port, 10) : defaultPort;
  const hostname = url.hostname;

  // Resolve and validate IP
  const pinnedIp = await resolveAndValidateHostname(hostname);

  const timeoutMs = options.timeoutMs ?? 15000;
  const method = options.method || 'GET';
  const headers = {
    'User-Agent': 'ChangeWatch/1.0 (Student Project; VIT Vellore; +contact)',
    Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    ...options.headers,
    Host: hostname, // Explicit host header for vhosts
  };

  return new Promise<PinnedFetchResponse>((resolve, reject) => {
    let finished = false;

    // Custom socket connection directly to pinned IP
    const createConnection = () => {
      if (isHttps) {
        return tls.connect({
          host: pinnedIp,
          port,
          servername: hostname, // TLS SNI
          rejectUnauthorized: true,
        });
      } else {
        return net.connect({
          host: pinnedIp,
          port,
        });
      }
    };

    const reqOptions: http.RequestOptions = {
      protocol: url.protocol,
      hostname: pinnedIp, // connect to pinned IP
      port,
      path: url.pathname + url.search,
      method,
      headers,
      createConnection,
      timeout: timeoutMs,
    };

    const client = isHttps ? https : http;
    const req = client.request(reqOptions, async (res) => {
      // Handle redirects
      if (res.statusCode && [301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location) {
        if (finished) return;
        finished = true;
        req.destroy();

        const redirectUrl = new URL(res.headers.location, url).toString();
        try {
          const redirectResponse = await pinnedFetch(redirectUrl, options, redirectCount + 1);
          resolve(redirectResponse);
        } catch (e) {
          reject(e);
        }
        return;
      }

      const chunks: Buffer[] = [];
      res.on('data', (chunk) => chunks.push(Buffer.from(chunk)));
      res.on('end', () => {
        if (finished) return;
        finished = true;
        const body = Buffer.concat(chunks).toString('utf8');
        resolve({
          statusCode: res.statusCode || 200,
          statusMessage: res.statusMessage || '',
          headers: res.headers as Record<string, string | string[] | undefined>,
          body,
          finalUrl: url.toString(),
          resolvedIp: pinnedIp,
        });
      });
      res.on('error', (err) => {
        if (!finished) {
          finished = true;
          reject(err);
        }
      });
    });

    req.on('timeout', () => {
      req.destroy();
      if (!finished) {
        finished = true;
        reject(new Error(`Socket pinned request to ${hostname} timed out after ${timeoutMs}ms`));
      }
    });

    req.on('error', (err) => {
      if (!finished) {
        finished = true;
        reject(err);
      }
    });

    req.end();
  });
}
