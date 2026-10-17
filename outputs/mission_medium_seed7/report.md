# WALL-E Mission Report: mission_medium

## 1. Mission Summary
- **Configuration:** `mission_medium` (Master Seed: `7`)
- **Agent Architecture:** `bayes_planner` (Exact Bayesian Grid Filter + EIG Planner)
- **Outcome:** **DECLARED**
- **Duration:** 21 action steps (21 environment ticks)

---

## 2. Final Inferred Answer
- **Inferred Location:** `(4, 12)`
- **Location Confidence:** 95.7% mass within 1.5-cell radius
- **Inferred Status:** `low_power` (Confidence: 99.8%)
- **Status Probabilities:** `active`: 0.2%, `low_power`: 99.8%, `damaged`: 0.0%
- **90% Credible Region:**
  - Encompasses **3 cells**
  - Spatial Bounding Box: `[3, 11]` to `[4, 12]`
- **Calibration Note:** Empirically calibrated: 90% credible regions achieve 93.0% empirical coverage across 200 randomized missions.

---

## 3. Evidence Table
Total pieces of evidence collected: **3**.

### Top Most Influential Observations:
| Rank | Step | Type | Measured Value | Info Gain (bits) | Status | Impact on Belief |
|---|---|---|---|---|---|---|
| 1 | 18 | `scan_signal` | `str=0.575, brg=323.8°` | **5.272** | `trusted` | Updated MAP to (4, 12), entropy=1.88b |
| 2 | 0 | `initial_signal` | `str=0.16, brg=168.0°` | **1.230** | `trusted` | Initial prior pointing along bearing 168.0° |
| 3 | 16 | `scan_signal` | `DROPOUT` | **0.518** | `trusted` | Updated MAP to (4, 10), entropy=8.65b |

---

## 4. Resource Utilization & Safety Verification
- **Battery Consumed by Actions:** 22 energy units
- **Net Battery Change:** 22 energy units (initial - final)
- **Recharge Energy Delivered:** 0 energy units (0 station dockings)
- **Minimum Absolute Battery:** 78 energy units
- **Minimum Energy Margin:** 61 battery units above return reserve
- **Safe-Return Verification:** Verified by pre-execution guard (0 invariant violations detected)
- **Empirical Stranding Rate:** 0.0% stranded across evaluated mission runs
- **Total Distance Travelled:** 18.0 cells
- **Time Budget Consumed:** 21 ticks

---

## 5. Strategy Timeline
Chronological record of high-level autonomous strategy shifts:
| Step | From Strategy | To Strategy | Trigger Rationale |
|---|---|---|---|
| 18 | `EXPLORE` | `TRACK` | location confidence 0.96 >= 0.50, switching to TRACK |
| 19 | `TRACK` | `VERIFY` | location confidence 0.96 >= 0.75, switching to VERIFY |
| 20 | `VERIFY` | `DECLARE` | location conf 0.96 >= 0.90 and status conf 1.00 >= 0.70, DECLARING |

---

## 6. Recommended Next Step
**Primary Action:** Dispatch WALL-E directly to target coordinates (4, 12). Target localization confidence is high (95.7%).

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
