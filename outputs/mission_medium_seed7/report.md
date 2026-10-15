# WALL-E Mission Report: mission_medium

## 1. Mission Summary
- **Configuration:** `mission_medium` (Master Seed: `7`)
- **Agent Architecture:** `bayes_planner` (Exact Bayesian Grid Filter + EIG Planner)
- **Outcome:** **DECLARED**
- **Duration:** 30 action steps (30 environment ticks)

---

## 2. Final Inferred Answer
- **Inferred Location:** `(4, 12)`
- **Location Confidence:** 99.3% mass within 1.5-cell radius
- **Inferred Status:** `low_power` (Confidence: 100.0%)
- **Status Probabilities:** `active`: 0.0%, `low_power`: 100.0%, `damaged`: 0.0%
- **90% Credible Region:**
  - Encompasses **2 cells**
  - Spatial Bounding Box: `[3, 12]` to `[4, 12]`
- **Calibration Note:** Empirically calibrated: 90% credible regions achieve 93.0% empirical coverage across 200 randomized missions.

---

## 3. Evidence Table
Total pieces of evidence collected: **4**.

### Top Most Influential Observations:
| Rank | Step | Type | Measured Value | Info Gain (bits) | Status | Impact on Belief |
|---|---|---|---|---|---|---|
| 1 | 22 | `scan_signal` | `str=0.392, brg=347.2°` | **4.876** | `trusted` | Updated MAP to (6, 15), entropy=4.34b |
| 2 | 27 | `scan_signal` | `str=0.581, brg=301.0°` | **3.087** | `trusted` | Updated MAP to (4, 12), entropy=1.20b |
| 3 | 0 | `initial_signal` | `str=0.0674419154557822, brg=172.9981741787147°` | **0.500** | `trusted` | Initial prior pointing along bearing 172.9981741787147° |
| 4 | 19 | `scan_signal` | `DROPOUT` | **0.321** | `trusted` | Updated MAP to (4, 15), entropy=8.94b |

---

## 4. Resource Utilization
- **Battery Consumed:** 32 energy units
- **Recharge Cycles:** 0 station dockings
- **Minimum Energy Margin:** 68 battery units remaining (Safe Return guaranteed)
- **Total Distance Travelled:** 26.0 cells
- **Time Budget Consumed:** 30 ticks

---

## 5. Strategy Timeline
Chronological record of high-level autonomous strategy shifts:
| Step | From Strategy | To Strategy | Trigger Rationale |
|---|---|---|---|
| 27 | `EXPLORE` | `TRACK` | location confidence 0.99 >= 0.50, switching to TRACK |
| 28 | `TRACK` | `VERIFY` | location confidence 0.99 >= 0.75, switching to VERIFY |
| 29 | `VERIFY` | `DECLARE` | location conf 0.99 >= 0.90 and status conf 1.00 >= 0.70, DECLARING |

---

## 6. Recommended Next Step
**Primary Action:** Dispatch WALL-E directly to target coordinates (4, 12). Target localization confidence is high (99.3%).

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
