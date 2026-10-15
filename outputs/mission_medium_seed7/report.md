# WALL-E Mission Report: mission_medium

## 1. Mission Summary
- **Configuration:** `mission_medium` (Master Seed: `7`)
- **Agent Architecture:** `bayes_planner` (Exact Bayesian Grid Filter + EIG Planner)
- **Outcome:** **DECLARED**
- **Duration:** 24 action steps (24 environment ticks)

---

## 2. Final Inferred Answer
- **Inferred Location:** `(4, 12)`
- **Location Confidence:** 100.0% mass within 1.5-cell radius
- **Inferred Status:** `low_power` (Confidence: 100.0%)
- **Status Probabilities:** `active`: 0.0%, `low_power`: 100.0%, `damaged`: 0.0%
- **90% Credible Region:**
  - Encompasses **2 cells**
  - Spatial Bounding Box: `[3, 11]` to `[4, 12]`
- **Calibration Note:** In 90% of calibrated runs, EVE's true coordinate falls inside this region.

---

## 3. Evidence Table
Total pieces of evidence collected: **4**.

### Top 5 Most Influential Observations:
| Rank | Step | Type | Measured Value | Info Gain (bits) | Status | Impact on Belief |
|---|---|---|---|---|---|---|
| 1 | 22 | `scan_signal` | `str=0.596, brg=347.1°` | **3.937** | `trusted` | Updated MAP to (4, 12), entropy=4.07b |
| 2 | 13 | `scan_signal` | `DROPOUT` | **1.230** | `trusted` | Updated MAP to (5, 14), entropy=8.85b |
| 3 | 17 | `scan_signal` | `str=0.533, brg=163.5°` | **0.518** | `trusted` | Updated MAP to (4, 10), entropy=8.65b |
| 4 | 0 | `initial_signal` | `str=0.16, brg=168.0°` | **0.500** | `trusted` | Initial prior pointing along bearing 168.0° |

---

## 4. Resource Utilization
- **Battery Consumed:** 26 energy units
- **Recharge Cycles:** 0 station dockings
- **Minimum Energy Margin:** 74 battery units remaining (Safe Return guaranteed)
- **Total Distance Travelled:** 20.0 cells
- **Time Budget Consumed:** 24 ticks

---

## 5. Strategy Timeline
Chronological record of high-level autonomous strategy shifts:
| Step | From Strategy | To Strategy | Trigger Rationale |
|---|---|---|---|
| 17 | `EXPLORE` | `TRACK` | location confidence 0.64 >= 0.50, switching to TRACK |
| 22 | `TRACK` | `VERIFY` | location confidence 1.00 >= 0.75, switching to VERIFY |
| 23 | `VERIFY` | `DECLARE` | location conf 1.00 >= 0.90 and status conf 1.00 >= 0.70, DECLARING |

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
