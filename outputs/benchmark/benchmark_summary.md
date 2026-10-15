# WALL-E Generalization Benchmark Results

## Evaluation Setup
- **Missions Evaluated:** 100 randomized grid worlds (grid: 12-24, obstacles: 4-16%, noise: 0.8-1.5, battery: 60-120)
- **Architectures Tested:**
  1. `RandomAgent`: Random walk with periodic scans, constrained by safe return
  2. `GreedyBearingAgent`: Greedily steps along latest bearing vector, declares on strong proximity
  3. `BayesPlannerAgent` (Ours): Active Bayesian grid filter with Monte-Carlo EIG and guaranteed safe-return reserve
- **Total Execution Time:** 160.4 seconds

---

## Performance Comparison Table

| Architecture | Success Rate | Mean Loc Error (cells) | Median Loc Error | Status Accuracy | Credible Hit (90%) | Mean Battery | Mean Recharges | Mean Ticks | Stranded Rate |
|---|---|---|---|---|---|---|---|---|---|
| **Random Agent** | **3.0%** | 9.98 | 9.22 | 28.0% | 0.0% | 865.7 | 42.0 | 137.5 | **0.0%** |
| **Greedy Bearing Agent** | **6.0%** | 6.19 | 3.16 | 28.0% | 0.0% | 944.1 | 46.0 | 202.8 | **0.0%** |
| **Bayes Planner Agent (Ours)** | **99.0%** | 0.30 | 0.00 | 100.0% | 95.0% | 37.6 | 0.3 | 34.3 | **0.0%** |

> **Note on Battery & Resource Metrics:**
> `RandomAgent` and `GreedyBearingAgent` frequently wander into charging stations and recharge multiple times across their missions (or run until the 250-tick timeout), resulting in cumulative gross energy consumption exceeding nominal single-charge battery capacity (60–120 units). In contrast, `BayesPlannerAgent` localizes EVE efficiently with active information gathering, declaring completion in far fewer steps without unnecessary recharge loops.

---

## Key Findings
1. **Bayesian Spatial Convergence**: `BayesPlannerAgent` achieved **99.0%** success compared to 6.0% for greedy bearing pursuit and 3.0% for random walk.
2. **Precision Localization**: Mean localization error dropped from 6.19 cells (greedy) to **0.30 cells** (Bayes planner, median 0.00 cells).
3. **Safe Return Invariant Guaranteed**: Across all 100 missions with varying battery limits (60–120 units), `BayesPlannerAgent` sustained a **0.0% stranded rate**, strictly honoring dynamic return reserves.
