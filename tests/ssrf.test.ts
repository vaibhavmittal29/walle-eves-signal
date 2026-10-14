import { describe, it, expect } from 'vitest';
import { validatePublicIp } from '../src/server/core/security/ip-validator.js';
import { pinnedFetch, resolveAndValidateHostname } from '../src/server/core/security/socket-agent.js';

describe('SSRF Guard & Socket-Level IP Pinning [B, C]', () => {
  it('strictly blocks IPv4 loopback and local addresses', () => {
    const res1 = validatePublicIp('127.0.0.1');
    expect(res1.valid).toBe(false);
    expect(res1.reason).toBe('BLOCKED_RANGE_LOOPBACK');

    const res2 = validatePublicIp('127.128.0.1');
    expect(res2.valid).toBe(false);
    expect(res2.reason).toBe('BLOCKED_RANGE_LOOPBACK');
  });

  it('strictly blocks cloud metadata (169.254.169.254) and link-local subnets', () => {
    const meta = validatePublicIp('169.254.169.254');
    expect(meta.valid).toBe(false);
    expect(meta.reason).toMatch(/BLOCKED_CLOUD_METADATA|BLOCKED_RANGE_LINKLOCAL/);

    const linkLocal = validatePublicIp('169.254.1.1');
    expect(linkLocal.valid).toBe(false);
    expect(linkLocal.reason).toMatch(/BLOCKED_CLOUD_METADATA|BLOCKED_RANGE_LINKLOCAL/);
  });

  it('strictly blocks private RFC1918 subnets (10.x, 172.16-31.x, 192.168.x)', () => {
    expect(validatePublicIp('10.0.0.1').valid).toBe(false);
    expect(validatePublicIp('10.255.255.255').valid).toBe(false);
    expect(validatePublicIp('172.16.0.1').valid).toBe(false);
    expect(validatePublicIp('172.31.255.255').valid).toBe(false);
    expect(validatePublicIp('192.168.1.1').valid).toBe(false);
  });

  it('strictly blocks carrier-grade NAT, multicast, broadcast, and reserved', () => {
    expect(validatePublicIp('100.64.0.1').valid).toBe(false); // CGNAT
    expect(validatePublicIp('224.0.0.1').valid).toBe(false);  // Multicast
    expect(validatePublicIp('240.0.0.1').valid).toBe(false);  // Reserved
    expect(validatePublicIp('255.255.255.255').valid).toBe(false); // Broadcast
  });

  it('strictly blocks IPv6 loopback, link-local, unique-local, and IPv4-mapped forms', () => {
    expect(validatePublicIp('::1').valid).toBe(false);          // Loopback
    expect(validatePublicIp('fe80::1').valid).toBe(false);      // Link-local
    expect(validatePublicIp('fc00::1').valid).toBe(false);      // Unique-local
    expect(validatePublicIp('ff02::1').valid).toBe(false);      // Multicast

    // IPv4-mapped IPv6 representations
    expect(validatePublicIp('::ffff:127.0.0.1').valid).toBe(false);
    expect(validatePublicIp('::ffff:169.254.169.254').valid).toBe(false);
    expect(validatePublicIp('::ffff:10.0.0.1').valid).toBe(false);
  });

  it('permits genuine public IPv4 and IPv6 destinations', () => {
    expect(validatePublicIp('8.8.8.8').valid).toBe(true);
    expect(validatePublicIp('1.1.1.1').valid).toBe(true);
    expect(validatePublicIp('93.184.216.34').valid).toBe(true);
    expect(validatePublicIp('2606:4700:4700::1111').valid).toBe(true);
  });

  it('[B] pinnedFetch throws an SSRF error when targeted at loopback or metadata', async () => {
    await expect(pinnedFetch('http://127.0.0.1/admin')).rejects.toThrow(/SSRF Blocked/);
    await expect(pinnedFetch('http://169.254.169.254/latest/meta-data')).rejects.toThrow(/SSRF Blocked/);
    await expect(pinnedFetch('http://10.0.0.1/secret')).rejects.toThrow(/SSRF Blocked/);
  });

  it('resolveAndValidateHostname rejects domains resolving to private/loopback IPs', async () => {
    await expect(resolveAndValidateHostname('localhost')).rejects.toThrow(/SSRF Blocked/);
  });
});
