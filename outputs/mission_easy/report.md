# WALL-E Mission Report: mission_easy

## 1. Mission Summary
- **Configuration:** `mission_easy` (Master Seed: `42`)
- **Agent Architecture:** `bayes_planner` (Exact Bayesian Grid Filter + EIG Planner)
- **Outcome:** **DECLARED**
- **Duration:** 20 action steps (20 environment ticks)

---

## 2. Final Inferred Answer
- **Inferred Location:** `(6, 11)`
- **Location Confidence:** 100.0% mass within 1.5-cell radius
- **Inferred Status:** `active` (Confidence: 100.0%)
- **Status Probabilities:** `active`: 100.0%, `low_power`: 0.0%, `damaged`: 0.0%
- **90% Credible Region:**
  - Encompasses **1 cells**
  - Spatial Bounding Box: `[6, 11]` to `[6, 11]`
- **Calibration Note:** Empirically calibrated: 90% credible regions achieve 93.0% empirical coverage across 200 randomized missions.

---

## 3. Evidence Table
Total pieces of evidence collected: **3**.

### Top Most Influential Observations:
| Rank | Step | Type | Measured Value | Info Gain (bits) | Status | Impact on Belief |
|---|---|---|---|---|---|---|
| 1 | 13 | `scan_signal` | `str=0.631, brg=168.9°` | **4.174** | `trusted` | Updated MAP to (6, 9), entropy=2.07b |
| 2 | 17 | `scan_signal` | `str=0.901, brg=232.1°` | **3.751** | `trusted` | Updated MAP to (6, 11), entropy=0.16b |
| 3 | 0 | `initial_signal` | `str=0.17, brg=153.0°` | **0.500** | `trusted` | Initial prior pointing along bearing 153.0° |

---

## 4. Resource Utilization
- **Battery Consumed:** 21 energy units
- **Recharge Cycles:** 0 station dockings
- **Minimum Energy Margin:** 79 battery units remaining (Safe Return guaranteed)
- **Total Distance Travelled:** 17.0 cells
- **Time Budget Consumed:** 20 ticks

---

## 5. Strategy Timeline
Chronological record of high-level autonomous strategy shifts:
| Step | From Strategy | To Strategy | Trigger Rationale |
|---|---|---|---|
| 17 | `EXPLORE` | `TRACK` | location confidence 1.00 >= 0.45, switching to TRACK |
| 18 | `TRACK` | `VERIFY` | location confidence 1.00 >= 0.70, switching to VERIFY |
| 19 | `VERIFY` | `DECLARE` | location conf 1.00 >= 0.85 and status conf 1.00 >= 0.65, DECLARING |

---

## 6. Recommended Next Step
**Primary Action:** Dispatch WALL-E directly to target coordinates (6, 11). Target localization confidence is high (100.0%).

**Standard Protocol:** EVE status is inferred as 'active'. Proceed with standard direct wireless rendezvous and handshake protocol.

---

## 7. Ground Truth Validation (Simulation Only)
> [!IMPORTANT]
> The following validation data is generated from simulator hidden truth and was **never** accessible to the agent.

- **True EVE Location:** `(6, 11)`
- **True Operational Status:** `active`
- **Localization Error:** **0.00 cells**
- **Status Classification Correct:** **YES**
- **Truth Inside 90% Credible Region:** **YES**
- **Overall Mission Objective:** **SUCCESS**

---

## 8. Limitations and Assumptions
1. **Discrete Grid Topology:** Spatial reasoning operates on discrete 4-connected grid coordinates without sub-cell interpolation.
2. **Sensor Noise Model:** Noise processes are assumed to follow stationary zero-mean Gaussian distributions with known distance-dependent variances.
3. **Target Stationarity:** Target EVE is assumed stationary throughout the search unless random walk mobility mode is enabled.
4. **Physical Dynamics Scope:** Continuous motor dynamics, wheel slip, and Gazebo/Webots 3D physics are out of scope for this algorithmic benchmark.
