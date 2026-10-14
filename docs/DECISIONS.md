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
