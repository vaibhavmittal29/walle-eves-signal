# Mission Configuration Reference

Every field in the YAML mission configuration file is typed, validated, and documented below.

## 1. `mission` Section
- `name` *(string)*: Unique identifier for the mission profile (e.g. `mission_medium`).
- `seed` *(int)*: Master random seed for environment and world generation (walls, EVE location, clue placements).
- `grid`:
  - `width` *(int, >=3)*: Number of horizontal columns. Default: 20.
  - `height` *(int, >=3)*: Number of vertical rows. Default: 20.
- `start` *([int, int])*: WALL-E's starting coordinate `[x, y]`. Must be a free cell.
- `obstacles`:
  - `mode` *(string: `random` | `explicit` | `ascii`)*: Obstacle generation mode.
  - `density` *(float, [0.0, 0.8))*: Obstacle density used when mode is `random`.
  - `explicit` *(list of [int, int])*: Explicit list of wall coordinates when mode is `explicit`.
  - `ascii` *(list of strings)*: ASCII grid representation (`#` wall, `.` free) when mode is `ascii`.
- `chargers` *(list of [int, int])*: Locations of battery charging stations. Start cell is automatically included if omitted.
- `eve`:
  - `location` *(string `random` or [int, int])*: True location of EVE. If `random`, chosen on reachable cell >= `min_distance_from_start`.
  - `status` *(string: `random` | `active` | `low_power` | `damaged`)*: EVE's operational condition.
  - `mobility` *(string: `static` | `random_walk`)*: Whether EVE is stationary or diffuses over time.
  - `min_distance_from_start` *(int)*: Minimum Euclidean distance from start when `location: random`.
- `clues`:
  - `count` *(int, >=0)*: Number of hidden clue objects placed across reachable free cells.
  - `placement` *(string: `random` | `explicit`)*: Clue placement strategy.
  - `type_mix` *(mapping)*: Categorical distribution of clue types (`bearing`, `range`, `status`). Must sum to 1.0.

## 2. `initial_signal` Section
- `bearing_deg` *(float or null)*: Initial noisy compass bearing towards EVE in degrees [0, 360).
- `coordinates` *([int, int] or null)*: Optional rough 2D coordinate hint.
- `coordinates_sigma` *(float)*: Standard deviation of coordinate hint Gaussian prior.
- `strength` *(float or null)*: Initial received signal strength indicator (RSSI).
- `timestamp` *(int)*: Initial observation time tick (default 0).
*Note: At least one of `bearing_deg`, `coordinates`, or `strength` must be non-null.*

## 3. `resources` Section
- `battery_capacity` *(int)*: Maximum energy unit storage. Default 100.
- `battery_initial` *(int)*: Energy units at mission start (<= capacity).
- `time_budget` *(int)*: Total allowed time ticks before forced termination.
- `costs`:
  - `move`: `{battery: int, time: int}` per cell movement.
  - `scan_signal`: `{battery: int, time: int}` for a directional antenna sweep.
  - `scan_area`: `{battery_base: int, battery_per_radius: int, time_base: int, time_per_radius: int, max_radius: int}`.
  - `recharge`: `{battery_gain: int, time: int}` units replenished per charge action at a station.

## 4. `sensor` Section
- `noise_scale` *(float)*: Global multiplier scaling all noise parameters (useful for stress testing).
- `strength_sigma` *(float)*: Standard deviation of signal strength Gaussian observation noise.
- `bearing_sigma_base_deg` *(float)*: Base bearing noise in degrees.
- `bearing_sigma_per_cell_deg` *(float)*: Additional bearing noise per cell of distance from target.
- `d0` *(float)*: Characteristic half-power distance scale in `mu(d) = A / (1 + (d/d0)^2)`.
- `amplitude`: Signal transmission amplitude per status (`active`: 1.0, `low_power`: 0.6, `damaged`: 0.35).
- `dropout`: Probability of sensor packet loss / null reading per status.
- `decoys`:
  - `count` *(int)*: Number of spoofing decoy transmitters in the world.
  - `spoof_probability` *(float)*: Probability that a SCAN_SIGNAL returns a decoy reading.
- `clue_noise`:
  - `bearing_sigma_deg` *(float)*: Gaussian noise on bearing clues.
  - `range_sigma` *(float)*: Gaussian noise on range clues.
  - `status_accuracy` *(float)*: Probability that a status clue reports the true status.
  - `detect_probability` *(float)*: Probability of detecting a clue within scan radius.
  - `false_clue_probability` *(float)*: Probability of a corrupt/false clue observation.

## 5. `agent` Section
- `type` *(string)*: Agent controller (`bayes_planner`, `random`, `greedy_bearing`).
- `seed` *(int)*: Agent internal seed for Monte-Carlo sampling.
- `assumed_spoof_rate` *(float)*: Prior mixture weight for robust Bayesian filtering against decoys.
- `mc_samples` *(int)*: Number of belief particles sampled for Expected Information Gain (EIG).
- `max_candidates` *(int)*: Maximum viewpoint candidates evaluated per decision tick.
- `thresholds`:
  - `track` *(float)*: Location confidence required to switch from EXPLORE to TRACK.
  - `verify` *(float)*: Location confidence required to switch from TRACK to VERIFY.
  - `declare_location` *(float)*: Location confidence required to declare final answer.
  - `declare_status` *(float)*: Status confidence required to declare final answer.
- `safety`:
  - `margin_fraction` *(float)*: Extra fractional battery buffer on return reserve (e.g. 0.10 for 10%).
  - `margin_flat` *(int)*: Flat extra battery buffer on return reserve.
