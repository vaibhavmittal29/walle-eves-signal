export type Sensitivity = 'low' | 'balanced' | 'high';
export type EngineType = 'http_dom' | 'playwright';
export type CheckOutcome = 'OK' | 'ERROR' | 'BLOCKED';
export type ChangeEventType = 'CHANGE' | 'DOWN' | 'RECOVERED' | 'DIGEST';
export type OutboxStatus = 'QUEUED' | 'PENDING_CONFIG' | 'SENT_EXTERNAL' | 'RECORDED_IN_APP' | 'RETRYING' | 'FAILED';
export type NotificationChannel = 'discord' | 'telegram' | 'email' | 'in_app';

export interface ViewportConfig {
  width: number;
  height: number;
}

export interface WaitStrategy {
  waitForSelector?: string;
  timeoutMs: number;
}

export interface CaptureConfig {
  engine: EngineType;
  viewport: ViewportConfig;
  deviceScaleFactor: number;
  jsEnabled: boolean;
  userAgent: string;
  locale?: string;
  timezone?: string;
  waitStrategy: WaitStrategy;
  customHeaders?: Record<string, string>;
  screenshotRequired: boolean;
}

export interface NoiseFilters {
  timestamps: boolean;
  counters: boolean;
  tokens: boolean;
}

export interface KeywordRule {
  keyword: string;
  mode: 'MUST_CONTAIN' | 'MUST_NOT_CONTAIN' | 'ALERT_IF_ADDED' | 'ALERT_IF_REMOVED';
}

export interface UserSession {
  userId: string;
  email: string;
  displayName: string;
  token: string;
  csrfToken: string;
  expiresAt: string;
}
