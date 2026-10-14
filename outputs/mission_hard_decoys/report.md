# WALL-E Mission Report: mission_hard_decoys

## 1. Mission Summary
- **Configuration:** `mission_hard_decoys` (Master Seed: `99`)
- **Agent Architecture:** `bayes_planner` (Exact Bayesian Grid Filter + EIG Planner)
- **Outcome:** **DECLARED**
- **Duration:** 111 action steps (116 environment ticks)

---

## 2. Final Inferred Answer
- **Inferred Location:** `(19, 5)`
- **Location Confidence:** 98.7% mass within 1.5-cell radius
- **Inferred Status:** `low_power` (Confidence: 99.4%)
- **Status Probabilities:** `active`: 0.3%, `low_power`: 99.4%, `damaged`: 0.4%
- **90% Credible Region:**
  - Encompasses **2 cells**
  - Spatial Bounding Box: `[19, 4]` to `[19, 5]`
- **Calibration Note:** In 90% of calibrated runs, EVE's true coordinate falls inside this region.

---

## 3. Evidence Table
Total pieces of evidence collected: **19**.

### Top 5 Most Influential Observations:
| Rank | Step | Type | Measured Value | Info Gain (bits) | Impact on Belief |
|---|---|---|---|---|---|
| 1 | 98 | `scan_signal` | `DROPOUT` | **2.321** | Updated MAP to (19, 7), entropy=3.44b |
| 2 | 23 | `scan_signal` | `DROPOUT` | **2.022** | Updated MAP to (0, 14), entropy=8.43b |
| 3 | 80 | `scan_signal` | `str=1.000, brg=258.9°` | **1.784** | Updated MAP to (19, 9), entropy=3.11b |
| 4 | 76 | `scan_signal` | `DROPOUT` | **1.762** | Updated MAP to (19, 11), entropy=5.01b |
| 5 | 35 | `scan_signal` | `str=0.053, brg=42.4°` | **1.623** | Updated MAP to (7, 10), entropy=8.93b |

---

## 4. Resource Utilization
- **Battery Consumed:** 127 energy units
- **Recharge Cycles:** 5 station dockings
- **Minimum Energy Margin:** 4 battery units remaining (Safe Return guaranteed)
- **Total Distance Travelled:** 87.0 cells
- **Time Budget Consumed:** 116 ticks

---

## 5. Strategy Timeline
Chronological record of high-level autonomous strategy shifts:
| Step | From Strategy | To Strategy | Trigger Rationale |
|---|---|---|---|
| 78 | `EXPLORE` | `TRACK` | location confidence 0.79 >= 0.50, switching to TRACK |
| 79 | `TRACK` | `VERIFY` | location confidence 0.79 >= 0.75, switching to VERIFY |
| 80 | `VERIFY` | `RETURN` | battery 8 near reserve 8 (+ cost 1), initiating RETURN |
| 84 | `RETURN` | `RECHARGE` | docked at charger with battery 4/100, initiating RECHARGE |
| 89 | `RECHARGE` | `VERIFY` | battery replenished (100/100), resuming VERIFY |
| 110 | `VERIFY` | `DECLARE` | location conf 0.99 >= 0.90 and status conf 0.99 >= 0.70, DECLARING |

---

## 6. Recommended Next Step
**Primary Action:** Dispatch WALL-E directly to target coordinates (19, 5). Target localization confidence is high (98.7%).

**Rescue Precaution:** EVE status is inferred as 'low_power'. Approach equipped with an auxiliary charging payload and hardware repair kit.

---

## 7. Ground Truth Validation (Simulation Only)
> [!IMPORTANT]
> The following validation data is generated from simulator hidden truth and was **never** accessible to the agent.

- **True EVE Location:** `(19, 5)`
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
