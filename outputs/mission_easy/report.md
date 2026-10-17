# WALL-E Mission Report: mission_easy

## 1. Mission Summary
- **Configuration:** `mission_easy` (Master Seed: `42`)
- **Agent Architecture:** `bayes_planner` (Exact Bayesian Grid Filter + EIG Planner)
- **Outcome:** **DECLARED**
- **Duration:** 15 action steps (15 environment ticks)

---

## 2. Final Inferred Answer
- **Inferred Location:** `(7, 11)`
- **Location Confidence:** 99.3% mass within 1.5-cell radius
- **Inferred Status:** `active` (Confidence: 100.0%)
- **Status Probabilities:** `active`: 100.0%, `low_power`: 0.0%, `damaged`: 0.0%
- **90% Credible Region:**
  - Encompasses **3 cells**
  - Spatial Bounding Box: `[7, 10]` to `[8, 11]`
- **Calibration Note:** Empirically calibrated: 90% credible regions achieve 93.0% empirical coverage across 200 randomized missions.

---

## 3. Evidence Table
Total pieces of evidence collected: **2**.

### Top Most Influential Observations:
| Rank | Step | Type | Measured Value | Info Gain (bits) | Status | Impact on Belief |
|---|---|---|---|---|---|---|
| 1 | 12 | `scan_signal` | `str=0.654, brg=124.2°` | **4.797** | `trusted` | Updated MAP to (7, 11), entropy=1.14b |
| 2 | 0 | `initial_signal` | `str=0.17, brg=153.0°` | **1.667** | `trusted` | Initial prior pointing along bearing 153.0° |

---

## 4. Resource Utilization & Safety Verification
- **Battery Consumed by Actions:** 15 energy units
- **Net Battery Change:** 15 energy units (initial - final)
- **Recharge Energy Delivered:** 0 energy units (0 station dockings)
- **Minimum Absolute Battery:** 85 energy units
- **Minimum Energy Margin:** 67 battery units above return reserve
- **Safe-Return Verification:** Verified by pre-execution guard (0 invariant violations detected)
- **Empirical Stranding Rate:** 0.0% stranded across evaluated mission runs
- **Total Distance Travelled:** 13.0 cells
- **Time Budget Consumed:** 15 ticks

---

## 5. Strategy Timeline
Chronological record of high-level autonomous strategy shifts:
| Step | From Strategy | To Strategy | Trigger Rationale |
|---|---|---|---|
| 12 | `EXPLORE` | `TRACK` | location confidence 0.99 >= 0.45, switching to TRACK |
| 13 | `TRACK` | `VERIFY` | location confidence 0.99 >= 0.70, switching to VERIFY |
| 14 | `VERIFY` | `DECLARE` | location conf 0.99 >= 0.85 and status conf 1.00 >= 0.65, DECLARING |

---

## 6. Recommended Next Step
**Primary Action:** Dispatch WALL-E directly to target coordinates (7, 11). Target localization confidence is high (99.3%).

**Standard Protocol:** EVE status is inferred as 'active'. Proceed with standard direct wireless rendezvous and handshake protocol.

---

## 7. Ground Truth Validation (Simulation Only)
> [!IMPORTANT]
> The following validation data is generated from simulator hidden truth and was **never** accessible to the agent.

- **True EVE Location:** `(6, 11)`
- **True Operational Status:** `active`
- **Localization Error:** **1.00 cells**
- **Status Classification Correct:** **YES**
- **Truth Inside 90% Credible Region:** **NO**
- **Overall Mission Objective:** **SUCCESS**

---

## 8. Limitations and Assumptions
1. **Discrete Grid Topology:** Spatial reasoning operates on discrete 4-connected grid coordinates without sub-cell interpolation.
2. **Sensor Noise Model:** Noise processes are assumed to follow stationary zero-mean Gaussian distributions with known distance-dependent variances.
3. **Target Stationarity:** Target EVE is assumed stationary throughout the search unless random walk mobility mode is enabled.
4. **Physical Dynamics Scope:** Continuous motor dynamics, wheel slip, and Gazebo/Webots 3D physics are out of scope for this algorithmic benchmark.
