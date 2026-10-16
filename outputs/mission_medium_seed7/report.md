# WALL-E Mission Report: mission_medium

## 1. Mission Summary
- **Configuration:** `mission_medium` (Master Seed: `7`)
- **Agent Architecture:** `bayes_planner` (Exact Bayesian Grid Filter + EIG Planner)
- **Outcome:** **DECLARED**
- **Duration:** 27 action steps (27 environment ticks)

---

## 2. Final Inferred Answer
- **Inferred Location:** `(4, 12)`
- **Location Confidence:** 100.0% mass within 1.5-cell radius
- **Inferred Status:** `low_power` (Confidence: 100.0%)
- **Status Probabilities:** `active`: 0.0%, `low_power`: 100.0%, `damaged`: 0.0%
- **90% Credible Region:**
  - Encompasses **1 cells**
  - Spatial Bounding Box: `[4, 12]` to `[4, 12]`
- **Calibration Note:** Empirically calibrated: 90% credible regions achieve 93.0% empirical coverage across 200 randomized missions.

---

## 3. Evidence Table
Total pieces of evidence collected: **4**.

### Top Most Influential Observations:
| Rank | Step | Type | Measured Value | Info Gain (bits) | Status | Impact on Belief |
|---|---|---|---|---|---|---|
| 1 | 20 | `scan_signal` | `str=0.575, brg=233.8°` | **4.809** | `trusted` | Updated MAP to (4, 12), entropy=3.12b |
| 2 | 25 | `scan_signal` | `str=0.581, brg=31.0°` | **1.306** | `trusted` | Updated MAP to (4, 12), entropy=0.12b |
| 3 | 16 | `scan_signal` | `DROPOUT` | **0.518** | `trusted` | Updated MAP to (4, 10), entropy=8.65b |
| 4 | 0 | `initial_signal` | `str=0.16, brg=168.0°` | **0.500** | `trusted` | Initial prior pointing along bearing 168.0° |

---

## 4. Resource Utilization
- **Battery Consumed:** 29 energy units
- **Recharge Cycles:** 0 station dockings
- **Minimum Energy Margin:** 71 battery units remaining (Safe Return guaranteed)
- **Total Distance Travelled:** 23.0 cells
- **Time Budget Consumed:** 27 ticks

---

## 5. Strategy Timeline
Chronological record of high-level autonomous strategy shifts:
| Step | From Strategy | To Strategy | Trigger Rationale |
|---|---|---|---|
| 20 | `EXPLORE` | `TRACK` | location confidence 0.69 >= 0.50, switching to TRACK |
| 25 | `TRACK` | `VERIFY` | location confidence 1.00 >= 0.75, switching to VERIFY |
| 26 | `VERIFY` | `DECLARE` | location conf 1.00 >= 0.90 and status conf 1.00 >= 0.70, DECLARING |

---

## 6. Recommended Next Step
**Primary Action:** Dispatch WALL-E directly to target coordinates (4, 12). Target localization confidence is high (100.0%).

**Rescue Precaution:** EVE status is inferred as 'low_power'. Approach equipped with an auxiliary charging payload and hardware repair kit.

---

## 7. Ground Truth Validation (Simulation Only)
> [!IMPORTANT]
> The following validation data is generated from simulator hidden truth and was **never** accessible to the agent.

- **True EVE Location:** `(4, 12)`
- **True Operational Status:** `low_power`
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
