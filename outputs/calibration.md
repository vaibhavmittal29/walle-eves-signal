# Calibration Evaluation Report

- **Missions Evaluated:** 200
- **Base Seed:** 500
- **Overall 90% Credible Region Empirical Coverage:** 93.0%

## 1. Location Confidence Calibration Bins

| Confidence Bin | Missions (N) | Mean Bin Confidence | Empirical Patch Coverage (<=1.5 cells) | Empirical Credible Region Coverage | Status |
|---|---|---|---|---|---|
| [0.50, 0.70) | 0 | - | - | - | `N/A` |
| [0.70, 0.80) | 0 | - | - | - | `N/A` |
| [0.80, 0.90) | 0 | - | - | - | `N/A` |
| [0.90, 0.95) | 21 | 92.5% | 76.2% | 76.2% | `Over-Confident` |
| [0.95, 1.00) | 179 | 97.5% | 100.0% | 95.0% | `Well-Calibrated` |

## 2. Findings & Mathematical Assessment

- The exact Bayesian grid filter produces empirical credible coverage of **93.0%** for nominal 90% credible regions.
- In the highest confidence bin [0.95, 1.00], the agent's inferred MAP coordinates match true EVE locations with near-perfect spatial precision.
- Decoy discounting prevents false peaks from skewing confidence intervals.
