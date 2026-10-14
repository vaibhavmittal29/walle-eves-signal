import { CheckOutcome } from '../../../shared/types.js';

export interface ClassificationResult {
  outcome: CheckOutcome;
  reason: string;
  httpStatus?: number;
}

const BOT_CHALLENGE_PATTERNS = [
  /attention required!\s*\|\s*cloudflare/i,
  /just a moment\.\.\./i,
  /cf-browser-verification/i,
  /cf-turnstile/i,
  /cf-challenge-running/i,
  /hcaptcha\.com\/1\/api\.js/i,
  /google\.com\/recaptcha\/api\.js/i,
  /<div[^>]+id=["']challenge-stage["']/i,
  /<div[^>]+id=["']cf-please-wait["']/i,
  /access denied\s*\|\s*ddos protection/i,
  /incapsula incident id/i,
  /please verify you are a human/i,
  /checking your browser before accessing/i,
];

export function classifyCaptureResponse(
  httpStatus: number | undefined,
  bodyOrDom: string | undefined,
  networkError?: Error
): ClassificationResult {
  if (networkError) {
    const msg = networkError.message || '';
    if (msg.includes('SSRF Blocked') || msg.includes('not a permitted public destination')) {
      return { outcome: 'BLOCKED', reason: `SSRF_PROTECTION_BLOCKED: ${msg}`, httpStatus };
    }
    if (msg.includes('Robots.txt')) {
      return { outcome: 'BLOCKED', reason: msg, httpStatus };
    }
    return { outcome: 'ERROR', reason: `NETWORK_ERROR: ${msg}`, httpStatus };
  }

  if (httpStatus === undefined || httpStatus === 0) {
    return { outcome: 'ERROR', reason: 'NO_RESPONSE_STATUS' };
  }

  // 5xx Server Errors
  if (httpStatus >= 500 && httpStatus <= 599) {
    return { outcome: 'ERROR', reason: `HTTP_${httpStatus}_SERVER_ERROR`, httpStatus };
  }

  // 401, 403, 429 Forbidden or Rate Limited
  if (httpStatus === 401 || httpStatus === 403 || httpStatus === 429) {
    return { outcome: 'BLOCKED', reason: `HTTP_${httpStatus}_ACCESS_DENIED_OR_RATE_LIMITED`, httpStatus };
  }

  // 4xx Other Client Errors
  if (httpStatus >= 400 && httpStatus <= 499) {
    return { outcome: 'ERROR', reason: `HTTP_${httpStatus}_CLIENT_ERROR`, httpStatus };
  }

  // 2xx or 3xx Content inspection for anti-bot challenges
  const content = bodyOrDom || '';

  for (const pattern of BOT_CHALLENGE_PATTERNS) {
    if (pattern.test(content)) {
      return {
        outcome: 'BLOCKED',
        reason: 'ANTI_BOT_CHALLENGE_DETECTED',
        httpStatus,
      };
    }
  }

  if (content.trim().length === 0) {
    return {
      outcome: 'ERROR',
      reason: 'EMPTY_CONTENT_PAYLOAD',
      httpStatus,
    };
  }

  return {
    outcome: 'OK',
    reason: 'SUCCESS',
    httpStatus,
  };
}
