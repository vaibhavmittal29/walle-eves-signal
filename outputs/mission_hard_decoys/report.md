# WALL-E Mission Report: mission_hard_decoys

## 1. Mission Summary
- **Configuration:** `mission_hard_decoys` (Master Seed: `99`)
- **Agent Architecture:** `bayes_planner` (Exact Bayesian Grid Filter + EIG Planner)
- **Outcome:** **DECLARED**
- **Duration:** 122 action steps (127 environment ticks)

---

## 2. Final Inferred Answer
- **Inferred Location:** `(19, 6)`
- **Location Confidence:** 100.0% mass within 1.5-cell radius
- **Inferred Status:** `low_power` (Confidence: 100.0%)
- **Status Probabilities:** `active`: 0.0%, `low_power`: 100.0%, `damaged`: 0.0%
- **90% Credible Region:**
  - Encompasses **1 cells**
  - Spatial Bounding Box: `[19, 6]` to `[19, 6]`
- **Calibration Note:** Empirically calibrated: 90% credible regions achieve 93.0% empirical coverage across 200 randomized missions.

---

## 3. Evidence Table
Total pieces of evidence collected: **21**.

### Top Most Influential Observations:
| Rank | Step | Type | Measured Value | Info Gain (bits) | Status | Impact on Belief |
|---|---|---|---|---|---|---|
| 1 | 79 | `scan_signal` | `str=0.238, brg=9.9°` | **2.229** | `trusted` | Updated MAP to (18, 12), entropy=6.30b |
| 2 | 110 | `scan_signal` | `str=0.404, brg=65.1°` | **2.129** | `trusted` | Updated MAP to (19, 9), entropy=3.18b |
| 3 | 14 | `scan_signal` | `str=0.189, brg=222.8°` | **2.022** | `trusted` | Updated MAP to (0, 14), entropy=8.43b |
| 4 | 28 | `scan_signal` | `str=0.104, brg=51.1°` | **1.691** | `trusted` | Updated MAP to (7, 10), entropy=8.93b |
| 5 | 47 | `scan_signal` | `str=0.053, brg=132.4°` | **1.383** | `trusted` | Updated MAP to (19, 17), entropy=8.06b |

### Discounted / Suspected Decoy Readings:
- **Step 99**: `scan_signal` (`str=0.400, brg=13.3°`) — status: `discounted` (flagged contradictory >3σ under current MAP; scheduled confirmation scan).
- **Step 102**: `scan_signal` (`str=1.000, brg=33.0°`) — status: `discounted` (flagged contradictory >3σ under current MAP; scheduled confirmation scan).
- **Step 104**: `scan_signal` (`str=0.325, brg=59.6°`) — status: `discounted` (flagged contradictory >3σ under current MAP; scheduled confirmation scan).
- **Step 113**: `scan_signal` (`str=0.049, brg=240.5°`) — status: `discounted` (flagged contradictory >3σ under current MAP; scheduled confirmation scan).
- **Step 116**: `scan_signal` (`str=0.579, brg=17.1°`) — status: `discounted` (flagged contradictory >3σ under current MAP; scheduled confirmation scan).

---

## 4. Resource Utilization
- **Battery Consumed:** 136 energy units
- **Recharge Cycles:** 5 station dockings
- **Minimum Energy Margin:** 4 battery units remaining (Safe Return guaranteed)
- **Total Distance Travelled:** 96.0 cells
- **Time Budget Consumed:** 127 ticks

---

## 5. Strategy Timeline
Chronological record of high-level autonomous strategy shifts:
| Step | From Strategy | To Strategy | Trigger Rationale |
|---|---|---|---|
| 79 | `EXPLORE` | `RETURN` | battery 12 near reserve 12 (+ cost 1), initiating RETURN |
| 87 | `RETURN` | `RECHARGE` | docked at charger with battery 4/100, initiating RECHARGE |
| 92 | `RECHARGE` | `EXPLORE` | battery replenished (100/100), resuming EXPLORE |
| 110 | `EXPLORE` | `TRACK` | location confidence 0.66 >= 0.50, switching to TRACK |
| 118 | `TRACK` | `VERIFY` | location confidence 0.96 >= 0.75, switching to VERIFY |
| 121 | `VERIFY` | `DECLARE` | location conf 1.00 >= 0.90 and status conf 1.00 >= 0.70, DECLARING |

---

## 6. Recommended Next Step
**Primary Action:** Dispatch WALL-E directly to target coordinates (19, 6). Target localization confidence is high (100.0%).

**Rescue Precaution:** EVE status is inferred as 'low_power'. Approach equipped with an auxiliary charging payload and hardware repair kit.

---

## 7. Ground Truth Validation (Simulation Only)
> [!IMPORTANT]
> The following validation data is generated from simulator hidden truth and was **never** accessible to the agent.

- **True EVE Location:** `(19, 5)`
- **True Operational Status:** `low_power`
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
