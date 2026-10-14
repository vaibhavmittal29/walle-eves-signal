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
