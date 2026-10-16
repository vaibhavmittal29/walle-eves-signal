# Remediation Status Ledger

This ledger tracks the step-by-step remediation of the WALL-E & EVE's Signal repository as specified in the recruitment evaluation audit.

**Baseline Commit:** `078b6a4`  
**Current Date:** October 2026

| Phase | Description | Status | Tests Run | Commit SHA | Notes |
|---|---|---|---|---|---|
| **Phase 0** | Baseline: Clean env, pip install requirements & editable, baseline pytest | Done | `pytest -q`: 84 passed in 803.75s | `078b6a4` | Environment verified (Python 3.11). Dependencies installed. All 84 tests green at baseline. |
| **Phase 1** | Config validation: Comprehensive boundary & negative audit (Part 6) | Done | `pytest tests/test_config.py -v`: 23/23 passed; full test suite: 92 passed | `498240c` | Full dataclass audit complete. Bools rejected for numeric types. Added InitialSignalConfig.mode. Unified runner AppConfig validation. |
| **Phase 2** | Initial-signal semantics & missing-bearing likelihood (Part 1) | Done | `pytest tests/test_initial_signal.py -v`: 5/5 passed; full test suite: 97 passed | `e5e0089` | Added missing_bearing_reason, fixed strength-only/bearing-only/co-located/dropout likelihoods, integrated generated initial signal mode. |
| **Phase 3** | Mobile-target timing & diffusion prediction (Part 7) | Done | `pytest tests/test_mobile_target.py -v`: 6/6 passed; full test suite: 103 passed | `d2fd584` | Corrected timing order (apply obs at t before predict), explicit stationary/random_walk/diffusion models, wall-aware probability conservation. |
| **Phase 4** | Evidence and information-gain accounting (Part 2) | Done | `pytest tests/test_info_gain.py -v`: 4/4 passed; full test suite: 107 passed | `651c19b` | Removed 0.5 placeholder; exact KL divergence for initial signal; per-update KL tracking; Monte Carlo mutual info EIG with guaranteed non-negativity. |
| **Phase 5** | Area-scan memory (Part 3) | Done | `pytest tests/test_scan_area_radii.py -v`: 5/5 passed; full test suite: 110 passed | `13782f1` | Post-execution mask update on action_succeeded, verified radii 1/2/3 selection under crafted safety/utility conditions, failed/bumped scans rejected. |
| **Phase 6** | Decoy confirmation state machine (Part 4) | Done | `pytest tests/test_decoys_robustness.py -v`: 9/9 passed; full fast suite: 113 passed | `d5f301a` | Implemented full decoy state machine: distinct-cell confirmation requirement, orthogonal viewpoint prioritization (45-135 deg), 3-attempt timeout to confirmed_decoy, strict DECLARE blocking, and trace/report logging. |
| **Phase 7** | Safe-return invariant centralized guard (Part 5) | Done | `pytest tests/test_agent_invariants.py`: 10/10 passed; full fast suite: 119 passed | `dbce11f` | Implemented centralized pre-execution guard in planner and agent, validated all action modalities (MOVE, SCAN_SIGNAL, SCAN_AREA, RECHARGE, DECLARE), baseline margins configured, honest invariant violation logging, and report distinction between verified guard and empirical stranding rate. |
| **Phase 8** | Resource accounting & metrics reconciliation (Part 9) | Done | `pytest tests/test_resource_accounting.py -v`: 5/5 passed; full fast suite: 124 passed | `ec6c41c` | Formula reconciled (`initial + recharge_delivered - final = consumed`), net battery change signed, min_battery_absolute vs min_battery_margin separated, baseline confidence/entropy nullability. |
| **Phase 9** | Production trace replay verifier (Part 8) | Done | `pytest tests/test_verify.py -v`: 5/5 passed; full fast suite: 129 passed | `54ca414` | Implemented independent walle.verify module and CLI entrypoint walle verify; validates energy/time accounting, move adjacency/bounds/walls, recharge on charger, reserve consistency, safe-return invariant, and declaration match. |
| **Phase 10** | Visualization correctness (Part 11) | Done | `pytest tests/test_viz.py -v`: 5/5 passed; full fast suite: 132 passed | `f146629` | Battery capacity y-limits dynamic, clear zero-line baseline, exact 1..N action step labeling, synchronized 1:1 belief frames per step, ground truth strictly revealed only on final frame. |
| **Phase 11** | Test quality & separation enforcement (Part 12) | Done | `pytest tests/test_separation.py -v`: 5/5 passed; full fast suite: 134 passed | Pending | Replaced eval() in test_decoys_robustness.py with json.loads; verified AST zero-eval/exec policy across repository; added runtime proxy interceptor auditing zero private attribute access during execution. |
| **Phase 12** | Final source audit across all modules (Part 13) | Not Started | — | — | Numerical stability, edge-case hardening, dead code removal. |
| **Phase 13** | Calibration & benchmark methodology (Part 10) | Not Started | — | — | Real bin means, explicit metric definitions, paired seeds. |
| **Phase 14** | Regenerate all artifacts from frozen code (Part 14) | Not Started | — | — | Full benchmark ($N=100$), decoy ablation ($N=50$), calibration ($N=200$). |
| **Phase 15** | CI GitHub Actions workflow (Part 15) | Not Started | — | — | Multi-version CI workflow with local command verification. |
| **Phase 16** | Honest documentation & final audit report (Part 16) | Not Started | — | — | README, DESIGN, DECISIONS, AUDIT_REPORT, ENGINEERING_SUMMARY. |

---

## Log of Key Operational Actions & Test Results
- **Phase 0 Baseline:** Initialized ledger.
