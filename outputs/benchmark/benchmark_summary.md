# WALL-E Generalization Benchmark Results

## Evaluation Setup
- **Missions Evaluated:** 100 randomized grid worlds (grid: 12-24, obstacles: 4-16%, noise: 0.8-1.5, battery: 60-120)
- **Architectures Tested:**
  1. `RandomAgent`: Random walk with periodic scans, constrained by safe return
  2. `GreedyBearingAgent`: Greedily steps along latest bearing vector, declares on strong proximity
  3. `BayesPlannerAgent` (Ours): Active Bayesian grid filter with Monte-Carlo EIG and guaranteed safe-return reserve
- **Total Execution Time:** 36.8 seconds

---

## Performance Comparison Table

| Architecture | Success Rate | Mean Loc Error (cells) | Median Loc Error | Status Accuracy | Credible Hit (90%) | Mean Battery | Mean Steps | Stranded Rate |
|---|---|---|---|---|---|---|---|---|
| **Random Agent** | **3.0%** | 9.98 | 9.22 | 28.0% | 0.0% | 865.7 | 95.6 | **0.0%** |
| **Greedy Bearing Agent** | **6.0%** | 6.19 | 3.16 | 28.0% | 0.0% | 944.1 | 156.8 | **0.0%** |
| **Bayes Planner Agent (Ours)** | **98.0%** | 0.26 | 0.00 | 100.0% | 94.0% | 36.3 | 32.5 | **0.0%** |

---

## Key Findings
1. **Bayesian Spatial Convergence**: `BayesPlannerAgent` achieved **98.0%** success compared to 6.0% for greedy bearing pursuit and 3.0% for random walk.
2. **Precision Localization**: Mean localization error dropped from 6.19 cells (greedy) to **0.26 cells** (Bayes planner, median 0.00 cells).
3. **Safe Return Invariant Guaranteed**: Across all 100 missions with varying battery limits (60–120 units), `BayesPlannerAgent` sustained a **0.0% stranded rate**, strictly honoring dynamic return reserves.
