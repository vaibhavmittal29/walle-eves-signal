# ChangeWatch — Project Notes & Verification Log

## Project Overview
- **Project**: ChangeWatch — Intelligent Website Change Detector
- **Environment**: Windows (PowerShell) / Node.js v24.20.0 / npm 11.19.0
- **Database**: SQLite 3 (WAL mode via `better-sqlite3`)
- **Dual-Engine Core**: Tier 1 (Socket-pinned Cheerio/HTTP) + Tier 2 (Hardened Playwright Chromium)

---

## Acceptance Criteria & Test Verification Matrix

| Ref | Requirement | Verification Method | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **A** | User authentication & monitor ownership | Registration, login, and ownership isolation tests | **PASSED** | Phase 1 (tests/auth.test.ts) |
| **B** | SSRF protection & socket-level IP pinning | Test IP pinning against loopback & metadata | **PASSED** | Phase 2 (tests/ssrf.test.ts) |
| **C** | Browser request interception & egress limits | Subresource blocking & `routeWebSocket` tests | **PASSED** | Phase 2 (tests/ssrf.test.ts, tests/engine-classifier.test.ts) |
| **D** | Enforceable check intervals & next-run state | Interval validation and `next_check_at` test | **PASSED** | Phase 1 & 3 (tests/durable-queue.test.ts) |
| **E** | Respectful crawling & raw origin Robots.txt | Distinct origin blocking test using `robots-parser` with Allow/Disallow | **PASSED** | Phase 3 (tests/robots-origin.test.ts) |
| **F** | Per-domain rate limiting & jitter | Domain concurrency & 10s gap test | **PASSED** | Phase 3 (tests/durable-queue.test.ts) |
| **G** | Dual-engine capture consistency | Unified extraction contract verification | **PASSED** | Phase 2 (tests/engine-classifier.test.ts) |
| **H** | Accurate OK, ERROR, BLOCKED classification | 500 error, 403, and CAPTCHA classification tests | **PASSED** | Phase 2 (tests/engine-classifier.test.ts) |
| **I** | Strict baseline protection on failures | Outage capture leaves previous baseline intact | **PASSED** | Phase 4 (tests/hashing-noise.test.ts) |
| **J** | 3-failure outage & recovery alert flow | Consecutive failure counter & recovery test | **PASSED** | Phase 5 (tests/confirmation-candidate.test.ts) |
| **K** | Deterministic SHA-256 hashing | Hash stability test over identical text | **PASSED** | Phase 4 (tests/hashing-noise.test.ts) |
| **L** | Unchanged page creates zero new versions | 5 repeated runs on stable fixture | **PASSED** | Phase 4 (tests/hashing-noise.test.ts) |
| **M** | Meaningful change creates sequential version | Headline modification test | **PASSED** | Phase 4 (tests/hashing-noise.test.ts) |
| **N** | Multi-format timestamp & counter noise filters | Regex filter unit test on noisy fixture | **PASSED** | Phase 5 (tests/confirmation-candidate.test.ts) |
| **O** | Volatility probe & suggested noise rules | 2-capture volatility detector test | **PASSED** | Phase 5 (tests/confirmation-candidate.test.ts) |
| **P** | Two-check change confirmation | Candidate persistence & `pending_observation_id` test | **PASSED** | Phase 5 (tests/confirmation-candidate.test.ts) |
| **Q** | 6-hour alert cooldown & noisy-page flag | Cooldown enforcement & >70% volatility test | **PASSED** | Phase 5 (tests/confirmation-candidate.test.ts) |
| **R** | Durable SQLite queue with crash recovery | Startup recovery test for expired leases | **PASSED** | Phase 3 (tests/durable-queue.test.ts) |
| **S** | 200 subscriptions on same URL trigger 1 fetch | Concurrency benchmark execution with compatible fingerprints | **PASSED** | Phase 10 (tests/concurrency-200.test.ts & scripts/benchmark-200.ts) |
| **T** | Myers text diff & screenshot visual diff | Text additions/deletions & pixelmatch test | **PASSED** | Phase 6 (tests/diff-engine.test.ts) |
| **U** | Visual region picker & CSS selector extraction | Canvas overlay selector extraction test | **PASSED** | Phase 9 (tests/region-picker.test.ts) |
| **V** | Multi-channel outbox with truthful states | Discord, Telegram, and in-app delivery audit | **PASSED** | Phase 7 (tests/notification-outbox.test.ts) |
| **W** | Idempotency suppresses duplicate alerts | Composite key test across multiple channels | **PASSED** | Phase 7 (tests/notification-outbox.test.ts) |
| **X** | Masked credentials & CSRF protection | Payload audit & CSRF header verification | **PASSED** | Phase 1 (tests/auth.test.ts) |
| **Y** | Controlled testbed covering 14+ edge cases | Live fixture switcher verification | **PASSED** | Phase 2 (tests/engine-classifier.test.ts) |
| **Z** | Observation retention & version survival | 30-day unreferenced cleanup & candidate preservation test | **PASSED** | Phase 4 & 10 (tests/hashing-noise.test.ts) |
| **AA**| Due-only subscription evaluation | Test shared fetch evaluating only due subscribers | **PASSED** | Phase 3 (tests/durable-queue.test.ts) |
| **AB**| Config-aware capture deduplication | Test incompatible capture configs execute separate fetches | **PASSED** | Phase 3 (tests/durable-queue.test.ts) |
| **AC**| Origin-scoped raw robots caching test | Verify separate origins on same host have isolated rules and preserved response headers | **PASSED** | Phase 3 (tests/robots-origin.test.ts) |
| **AD**| Single source of truth capture engine test | Test generated required_engine matches capture_config | **PASSED** | Phase 1 (tests/config-fingerprint.test.ts) |
| **AE**| CaptureConfig cross-field validation test | Test explicit rejection of `screenshotRequired: true` with `engine: 'http_dom'` | **PASSED** | Phase 1 (tests/config-fingerprint.test.ts) |
| **AF**| Semantic equivalence fingerprint test | Test omitted defaults vs explicit defaults and reordered keys generate identical SHA-256 | **PASSED** | Phase 1 (tests/config-fingerprint.test.ts) |
| **AG**| Material difference fingerprint test | Test changes in viewport, UA, headers, waitStrategy generate distinct SHA-256 | **PASSED** | Phase 1 (tests/config-fingerprint.test.ts) |
| **AH**| Automated smoke test script (`smoke.ts`) | End-to-end command-line verification | **PASSED** | Phase 10 (scripts/smoke.ts) |

---

## Phase Execution Roadmap
- [x] **Phase 0: Planning & Environment Readiness**
- [x] **Phase 1: Foundation, SQLite WAL DB, Auth & Session Lifecycle**
- [x] **Phase 2: SSRF Guard, Socket Pinning, Classifier & Fixture Testbed**
- [x] **Phase 3: Durable Queue, Origin Robots Cache & Config-Aware Capture**
- [x] **Phase 4: Hashing, Snapshot Rules & Version History**
- [x] **Phase 5: Noise Filters, Volatility Probe, Confirmation & Cooldown**
- [x] **Phase 6: Myers Text Diff & Screenshot Visual Diff Engine**
- [x] **Phase 7: Truthful Notification Outbox, Webhooks & Daily Digest**
- [x] **Phase 8: High-Density Fleet Dashboard & Subscription Lifecycle**
- [x] **Phase 9: Visual Region Picker Overlay & CSS Selector Generator**
- [x] **Phase 10: 200-Subscription Concurrency Benchmark & Smoke Test Suite**
- [x] **Phase 11: Final Polish, Architecture Docs & Technical Mentorship Notes**
