import ipaddr from 'ipaddr.js';

export interface IpValidationResult {
  valid: boolean;
  ip: string;
  reason?: string;
}

/**
 * Validates whether an IP address (IPv4 or IPv6) is strictly a publicly-routable internet destination.
 * Any non-public, loopback, private, link-local, multicast, cloud metadata, or reserved IP is rejected.
 */
export function validatePublicIp(ipString: string): IpValidationResult {
  let addr: ipaddr.IPv4 | ipaddr.IPv6;

  try {
    addr = ipaddr.parse(ipString);
  } catch {
    return { valid: false, ip: ipString, reason: 'INVALID_IP_FORMAT' };
  }

  // Handle IPv4-mapped IPv6 addresses (e.g. ::ffff:127.0.0.1 or ::ffff:169.254.169.254)
  if (addr.kind() === 'ipv6') {
    const ipv6 = addr as ipaddr.IPv6;
    if (ipv6.isIPv4MappedAddress()) {
      addr = ipv6.toIPv4Address();
    }
  }

  const range = addr.range();

  // Explicitly blocked ranges for IPv4 and IPv6
  const disallowedRanges = new Set([
    'loopback',         // 127.0.0.0/8, ::1/128
    'private',          // 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7
    'linkLocal',        // 169.254.0.0/16, fe80::/10
    'multicast',        // 224.0.0.0/4, ff00::/8
    'carrierGradeNat',  // 100.64.0.0/10
    'reserved',         // 240.0.0.0/4, etc.
    'broadcast',        // 255.255.255.255
    'uniqueLocal',      // fc00::/7
    'unspecified',      // 0.0.0.0/8, ::/128
  ]);

  if (disallowedRanges.has(range)) {
    return {
      valid: false,
      ip: addr.toString(),
      reason: `BLOCKED_RANGE_${range.toUpperCase()}`,
    };
  }

  // Explicit check for cloud metadata IP 169.254.169.254 or link-local subnet
  if (addr.kind() === 'ipv4') {
    const octets = (addr as ipaddr.IPv4).toByteArray();
    if (octets[0] === 169 && octets[1] === 254) {
      return {
        valid: false,
        ip: addr.toString(),
        reason: 'BLOCKED_CLOUD_METADATA_OR_LINK_LOCAL',
      };
    }
  }

  return {
    valid: true,
    ip: addr.toString(),
  };
}
