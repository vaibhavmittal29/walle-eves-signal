# Architectural & Implementation Decision Log

This document records all architectural choices, assumptions, and key decisions made during the development of WALL-E and EVE's Signal.

## Phase 0: Scaffold & Ground Rules
- **Coordinate convention**: Grid coordinates are `(x, y)` where `x = column` (horizontal, 0 to W-1) and `y = row` (vertical, 0 to H-1, increasing downwards).
- **Bearing convention**: Standard navigation compass bearings in degrees `[0, 360)`:
  - 0° = North (up, -y)
  - 90° = East (right, +x)
  - 180° = South (down, +y)
  - 270° = West (left, -x)
  - Formula: `bearing = atan2(dx, -dy) mod 360` where `dx = x2 - x1`, `dy = y2 - y1`.
- **Angle difference wrapping**: Differences are wrapped into `(-180, 180]`.
- **Environment and Agent Separation**: Agent receives only `PublicMissionInfo` and `Observation`. All true world state (EVE true location/status, true clues, decoys) remains private in `World` / `Environment`.
- **Determinism**: Separate `numpy.random.Generator` instances for environment generation and agent Monte-Carlo estimation to guarantee reproducible runs given the same seeds.

## Phase 1: Config Schema & World Generation
- **Config Schema**: Strictly validated with custom `ConfigError` raising actionable diagnostic messages.
- **Connectivity Guarantee**: In random mode, world generation uses BFS to check 4-connected reachability from `start`. If isolated pockets are formed by random wall placement, derived seeds are tried up to 50 times.
- **Clue Ground Truth**: Clues are pre-placed on free reachable cells (never on start, chargers, or walls) and ground-truth values are computed based on true EVE state.
- **Strict Separation Enforced**: `PublicMissionInfo` strictly separates agent-visible data from hidden `GroundTruth`. Verified by AST analysis in `test_separation.py`.

## Phase 2: Signal Model & Environment API
- **Action Set**: `MOVE_N/E/S/W`, `SCAN_SIGNAL`, `SCAN_AREA(r)`, `RECHARGE`, `DECLARE(x,y,status)`.
- **Wall Bumps**: Move attempts into obstacles or boundaries deduct battery and time, leave position unchanged, and set `bumped=True`.
- **Recharge Mechanics**: Only allowed while standing on a charger cell. Off-charger attempts fail (`action_succeeded=False`) but consume time.
- **Clue Discovery**: Revealed clues are remembered in environment state so subsequent scans return them deterministically without re-rolling detection probabilities.
- **Termination Invariants**: Mission ends upon `DECLARE`, `stranded` (battery reaches 0 while off-charger), or `timeout` (time budget exhausted or max steps ceiling exceeded).

## Phase 3: Belief Engine
- **Belief Tensor**: Exact Bayesian filtering over 3D tensor $B[y, x, k]$ representing the joint probability over cell coordinates $(x, y)$ and operational status $k \in \{\text{active}, \text{low\_power}, \text{damaged}\}$.
- **Vectorized Likelihoods**: Likelihood builders precompute Euclidean distances and compass bearings using NumPy meshgrids, zeroing out walls and normalizing across status dimensions.
- **Robust Mixture**: When `assumed_spoof_rate > 0`, likelihood is mixed with a uniform baseline $L_{robust} = (1 - \epsilon) L + \epsilon \cdot \frac{1}{|Free| \times K}$ to prevent total mass collapse on decoy readings.
- **Contradiction Fallback**: In the rare event of contradictory measurements collapsing total mass below $10^{-12}$, the belief safely falls back to a 90/10 blend with the uniform prior and logs a contradiction.
- **Deduplicated Clues**: `apply_observation` ensures each clue observation is incorporated exactly once into the belief, preventing overcounting of static evidence.

## Phase 4: Planner, Safe Return, & Information Gain
- **BFS Shortest Paths**: Precomputes shortest 4-connected grid distances from chargers and arbitrary goals, avoiding walls.
- **Safe-Return Invariant**: Explicitly enforced via `is_action_safe(current_battery, pos_after, action_cost, chargers, ...)`. Rejects any action if the resulting battery is less than `ceil(dist_to_nearest_charger * move_battery_cost * (1 + margin_fraction) + margin_flat)`.
- **Triangulation Optimization**: Monte-Carlo EIG estimation mathematically favors orthogonal viewpoints that maximize angular diversity over redundant collinear positions along existing bearing lines.
- **Candidate Viewpoints**: Combines local 4-neighbors, charging stations, proximity to the MAP hypothesis, an annulus around the belief mean, and angular diversity relative to scan history.

## Phase 5: Autonomous Agent & Strategy State Machine
- **State Machine Transitions**: Transitions cleanly between `EXPLORE`, `TRACK`, `VERIFY`, `RETURN`, `RECHARGE`, and `DECLARE` according to calibrated location confidence and status confidence thresholds.
- **Plan Persistence**: Once a candidate viewpoint is selected, the agent executes the planned navigation leg towards the viewpoint before re-evaluating, preventing erratic dithering while moving.
- **Physical Sensor Consistency**: When a directional bearing is observed, the likelihood of the target being directly on the agent's current cell ($d=0$) is set to 0.0, reflecting the physical reality that a directional bearing requires non-zero displacement.
- **100-Seed Safety Invariant**: Across 100 randomized seeds, the agent successfully avoided getting stranded 100% of the time, guaranteeing zero battery exhaustion away from chargers.
