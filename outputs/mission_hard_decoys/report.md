# WALL-E Mission Report: mission_hard_decoys

## 1. Mission Summary
- **Configuration:** `mission_hard_decoys` (Master Seed: `99`)
- **Agent Architecture:** `bayes_planner` (Exact Bayesian Grid Filter + EIG Planner)
- **Outcome:** **DECLARED**
- **Duration:** 146 action steps (151 environment ticks)

---

## 2. Final Inferred Answer
- **Inferred Location:** `(19, 5)`
- **Location Confidence:** 98.0% mass within 1.5-cell radius
- **Inferred Status:** `low_power` (Confidence: 99.9%)
- **Status Probabilities:** `active`: 0.1%, `low_power`: 99.9%, `damaged`: 0.0%
- **90% Credible Region:**
  - Encompasses **2 cells**
  - Spatial Bounding Box: `[19, 4]` to `[19, 5]`
- **Calibration Note:** Empirically calibrated: 90% credible regions achieve 93.0% empirical coverage across 200 randomized missions.

---

## 3. Evidence Table
Total pieces of evidence collected: **22**.

### Top Most Influential Observations:
| Rank | Step | Type | Measured Value | Info Gain (bits) | Status | Impact on Belief |
|---|---|---|---|---|---|---|
| 1 | 120 | `scan_signal` | `str=0.523, brg=65.8°` | **3.015** | `trusted` | Updated MAP to (19, 6), entropy=3.79b |
| 2 | 123 | `scan_signal` | `str=0.032, brg=236.0°` | **2.310** | `trusted` | Updated MAP to (19, 6), entropy=6.83b |
| 3 | 131 | `scan_signal` | `str=0.416, brg=68.7°` | **2.236** | `trusted` | Updated MAP to (19, 7), entropy=2.48b |
| 4 | 72 | `scan_signal` | `str=0.281, brg=239.2°` | **2.214** | `trusted` | Updated MAP to (12, 19), entropy=6.14b |
| 5 | 14 | `scan_signal` | `str=0.141, brg=230.9°` | **1.860** | `trusted` | Updated MAP to (0, 13), entropy=8.49b |

### Discounted / Suspected Decoy Readings:
| Step | Type | Measured Value | Info Gain (bits) | Status | Rejection / Discount Rationale |
|---|---|---|---|---|---|
| 78 | `scan_signal` | `str=0.149, brg=35.2°` | **0.213** | `discounted` | Discounted suspected decoy (bearing mismatch > 3σ); scheduled confirmation scan |
| 101 | `scan_signal` | `str=0.455, brg=3.0°` | **0.185** | `discounted` | Discounted suspected decoy (bearing mismatch > 3σ); scheduled confirmation scan |
| 139 | `scan_signal` | `str=0.611, brg=354.3°` | **1.239** | `discounted` | Discounted suspected decoy (bearing mismatch > 3σ); scheduled confirmation scan |

---

## 4. Resource Utilization & Safety Verification
- **Battery Consumed by Actions:** 161 energy units
- **Net Battery Change:** 64 energy units (initial - final)
- **Recharge Energy Delivered:** 97 energy units (5 station dockings)
- **Minimum Absolute Battery:** 3 energy units
- **Minimum Energy Margin:** 1 battery units above return reserve
- **Safe-Return Verification:** Verified by pre-execution guard (0 invariant violations detected)
- **Empirical Stranding Rate:** 0.0% stranded across evaluated mission runs
- **Total Distance Travelled:** 119.0 cells
- **Time Budget Consumed:** 151 ticks

---

## 5. Strategy Timeline
Chronological record of high-level autonomous strategy shifts:
| Step | From Strategy | To Strategy | Trigger Rationale |
|---|---|---|---|
| 86 | `EXPLORE` | `RETURN` | battery 3 near reserve 3 (+ cost 1), initiating RETURN |
| 87 | `RETURN` | `RECHARGE` | docked at charger with battery 23/100, initiating RECHARGE |
| 91 | `RECHARGE` | `EXPLORE` | battery replenished (100/100), resuming EXPLORE |
| 120 | `EXPLORE` | `TRACK` | location confidence 0.73 >= 0.50, switching to TRACK |
| 123 | `TRACK` | `EXPLORE` | belief collapsed/conflicting evidence (0.16 < 0.30), falling back to EXPLORE |
| 131 | `EXPLORE` | `TRACK` | location confidence 0.80 >= 0.50, switching to TRACK |
| 132 | `TRACK` | `VERIFY` | location confidence 0.80 >= 0.75, switching to VERIFY |
| 145 | `VERIFY` | `DECLARE` | location conf 0.98 >= 0.90 and status conf 1.00 >= 0.70, DECLARING |

---

## 6. Recommended Next Step
**Primary Action:** Dispatch WALL-E directly to target coordinates (19, 5). Target localization confidence is high (98.0%).

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
