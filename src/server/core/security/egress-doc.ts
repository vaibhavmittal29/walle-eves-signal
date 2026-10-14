/**
 * Deployment-Level Network Egress Rules & Hardening Documentation
 *
 * In production environments, application-level SSRF defenses (ipaddr.js + socket pinning)
 * MUST be reinforced with operating system and cloud network layer egress boundaries.
 */

export const DEPLOYMENT_EGRESS_POLICY = {
  description: 'Strict Linux Host and Container Network Egress Rules for ChangeWatch Worker Nodes',

  linuxIptablesRules: `
# 1. Flush existing OUTPUT chain
iptables -F OUTPUT

# 2. Allow established and related connections
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# 3. Allow loopback traffic on local interfaces ONLY
iptables -A OUTPUT -o lo -j ACCEPT

# 4. Explicitly block link-local cloud metadata (AWS, GCP, Azure, DigitalOcean)
iptables -A OUTPUT -d 169.254.169.254 -j DROP
iptables -A OUTPUT -d 169.254.0.0/16 -j DROP

# 5. Block private RFC1918 subnets
iptables -A OUTPUT -d 10.0.0.0/8 -j DROP
iptables -A OUTPUT -d 172.16.0.0/12 -j DROP
iptables -A OUTPUT -d 192.168.0.0/16 -j DROP

# 6. Block carrier-grade NAT (RFC6598) and multicast
iptables -A OUTPUT -d 100.64.0.0/10 -j DROP
iptables -A OUTPUT -d 224.0.0.0/4 -j DROP

# 7. Allow outbound DNS (UDP/TCP 53) and HTTP/HTTPS (TCP 80, 443) to public internet
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 80 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT

# 8. Drop all other outbound traffic
iptables -A OUTPUT -j DROP
`,

  linuxIp6tablesRules: `
# IPv6 Egress Rules
ip6tables -F OUTPUT
ip6tables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
ip6tables -A OUTPUT -o lo -j ACCEPT

# Block IPv6 link-local, unique-local (fc00::/7), and multicast
ip6tables -A OUTPUT -d fe80::/10 -j DROP
ip6tables -A OUTPUT -d fc00::/7 -j DROP
ip6tables -A OUTPUT -d ff00::/8 -j DROP

# Allow HTTP and HTTPS
ip6tables -A OUTPUT -p tcp --dport 80 -j ACCEPT
ip6tables -A OUTPUT -p tcp --dport 443 -j ACCEPT
ip6tables -A OUTPUT -j DROP
`,

  dockerHardeningFlags: [
    '--cap-drop=NET_RAW',       // Prevents raw socket creation and ICMP/spoofing
    '--cap-drop=NET_ADMIN',     // Prevents network routing alteration
    '--security-opt=no-new-privileges',
    '--read-only',              // Read-only root filesystem
    '--tmpfs /tmp:rw,noexec,nosuid',
  ],

  kubernetesNetworkPolicy: `
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: changewatch-worker-egress
  namespace: changewatch
spec:
  podSelector:
    matchLabels:
      app: changewatch-worker
  policyTypes:
  - Egress
  egress:
  - to:
    - ipBlock:
        cidr: 0.0.0.0/0
        except:
        - 10.0.0.0/8
        - 172.16.0.0/12
        - 192.168.0.0/16
        - 169.254.0.0/16
        - 100.64.0.0/10
    ports:
    - protocol: TCP
      port: 80
    - protocol: TCP
      port: 443
    - protocol: UDP
      port: 53
`,
};
