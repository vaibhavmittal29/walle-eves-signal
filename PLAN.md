# WALL-E and EVE's Signal — Implementation Plan for Antigravity

> **Project:** Autonomous search agent (Vinnovate IT, VIT Vellore — AI/ML Round 1, Task 2)
> **Builder:** First-year CSE student. Code must be simple to read, well commented and explainable in an interview.
> **Deadline:** 15 Oct, 11:59 PM. Target submission: **15 Oct, 6 PM** (5+ hours of buffer).
> **Stack:** Python 3.10+, NumPy, PyYAML, Matplotlib, Pillow/imageio, pytest. No heavy frameworks.

---

## 0. How to use this document

1. Open an empty folder in Antigravity named `walle-eve-signal`.
2. Put this file in the folder root as `PLAN.md`.
3. Paste the **Master Prompt (Section 2)** into the agent first. Then work **one phase at a time** (Section 6). Each phase has a ready-to-paste prompt, a file list and acceptance criteria.
4. After every phase: run the tests, read the code the agent wrote, ask it to explain anything you do not understand, and commit to git.
5. Do not skip the review step. You will be asked about this code in later rounds. You must be able to explain the belief update, the utility function and the safe-return rule in your own words (see Section 11).

---

## 1. Project brief and requirement mapping

### 1.1 The task (from the portal)

Build an autonomous agent that explores a simulated environment, gathers clues and manages limited resources to locate EVE and decide WALL-E's next move.

**Input:** a mission config (JSON/YAML) defining the map or seed, the initial signal reading (direction/coordinates, strength, timestamp), the resource budget (battery, time, action costs) and clue placement or seed. The agent must learn clue locations **only through interaction**.

**Deliverables:** code repo with README (environment design, config format, run instructions), at least one sample config with its traces and report, and visualization output if attempted.

### 1.2 Requirement-to-evidence map (this is what the judges will check)

| # | Requirement | Where it lives | Evidence we ship |
|---|---|---|---|
| 1 | Simulated environment loads config and returns observations for each action | `config.py`, `world.py`, `environment.py` | `configs/*.yaml`, env unit tests |
| 2 | Autonomous agent chooses where to move, what to scan, when to recharge or turn back | `agent.py`, `planner.py`, `strategies.py` | Trace showing MOVE / SCAN_SIGNAL / SCAN_AREA / RECHARGE / RETURN decisions |
| 3 | Belief updates about EVE's location and status, plans adapt to new evidence | `belief.py`, `signal_model.py` | Belief heatmaps per step, entropy curve, strategy-change log |
| 4 | Full action trace: actions, observations, decisions, reasoning | `trace.py` | `trace.jsonl` + human-readable `trace.txt` |
| 5 | Final mission report: evidence, inferred location/status, confidence, recommended next step | `report.py` | `report.md` + `report.json` |
| B1 | Visualize path, clue locations, strategy changes | `viz.py` | ASCII frames, PNG summary, GIF |
| B2 | Decoy / spoofed signals, noisy sensors | `signal_model.py`, config `sensor:` | `mission_hard_decoys.yaml` run |
| B3 | Generalization benchmark across random missions | `benchmark.py` | `benchmark_results.csv` + chart |
| B4 | Classical planner vs baselines (LLM optional) | `baselines.py` | Comparison table in README |
| B5 | Gazebo / Webots physics | **Out of scope** (state this in README) | — |

---

## 2. MASTER PROMPT (paste this into Antigravity first)

```text
You are my senior engineering partner. We are building "WALL-E and EVE's Signal",
a recruitment project for the Vinnovate IT club (AI/ML). I am a first-year CSE student,
so keep code simple, typed, well commented and easy to explain.

PROJECT SUMMARY
An autonomous agent (WALL-E) searches a 2D grid world to find a hidden target (EVE).
It starts with a noisy initial signal reading. It has limited battery and time.
It must learn clue locations only by interacting (scanning). It maintains a Bayesian
belief over EVE's (location, status), plans actions to gather information while
staying able to return to a charger, logs a full action trace, and produces a final
mission report with inferred location/status, confidence and recommended next step.

HARD RULES
1. Read PLAN.md fully before writing code. It is the source of truth for specs,
   file layout, formulas, defaults and acceptance criteria. If something is ambiguous,
   choose the simplest option, write the decision in docs/DECISIONS.md, and continue.
2. Work phase by phase. At the end of each phase: run `pytest -q`, run the relevant
   demo command, summarize what changed, and STOP for my review. Do not start the next phase.
3. Strict separation: the agent code may ONLY see the `Observation` and `PublicMissionInfo`
   objects. It must never import from or access `world.py` hidden state (EVE location,
   clue positions, true status, decoys). Add a test that enforces this.
4. Determinism: every random choice uses a seeded `numpy.random.Generator`.
   The environment and the agent use SEPARATE generators. Same seed => identical trace.
5. Python 3.10+, type hints, dataclasses, docstrings on every public function,
   no global mutable state, no unnecessary dependencies (numpy, pyyaml, matplotlib,
   pillow, pytest only; imageio optional).
6. Coordinates are (x, y) with x = column, y = row, y increases DOWNWARD.
   Bearings are compass bearings in degrees: 0 = North (up, -y), 90 = East, 180 = South,
   270 = West. bearing = atan2(dx, -dy) mod 360. Put this in one helper function and
   reuse it everywhere.
7. Reasoning strings in the trace must be generated from real numbers (entropy, scores,
   battery, reserve) using templates. Never invent reasoning.
8. Keep functions small. Prefer clarity over cleverness. No premature optimization.
9. Commit-ready code: format with black-style spacing, no dead code, no TODO left behind.

Confirm you understood by replying with: (a) a 10-line summary of the system,
(b) the repo tree you will create, (c) any questions. Then wait for "start Phase 0".
```

---

## 3. Key design decisions (fixed — do not let the agent redesign these)

| Decision | Choice | Why |
|---|---|---|
| World | 2D grid, default 20×20, 4-connected moves, walls block movement | Simple, visualizable, fast |
| Map knowledge | Agent knows walls and charger positions. It does **not** know clue positions, EVE's position/status or decoys | Matches "learn clue locations only through interaction" |
| Belief | Joint tensor `B[y, x, k]` over location and status `k ∈ {active, low_power, damaged}` | Exact Bayesian update, tiny (20×20×3), easy to explain |
| Sensors | Noisy signal strength + noisy bearing + dropouts, status-dependent | Makes status inference real and gives a reason to triangulate |
| Clues | Hidden objects revealed by SCAN_AREA. Types: bearing, range, status | Gives "what to scan" meaning |
| Planning | One-step lookahead with Monte-Carlo expected information gain, next-best-viewpoint selection, safe-return constraint, re-plan every step | Classical, explainable, no training needed |
| Strategies | `EXPLORE → TRACK → VERIFY → DECLARE`, plus `RETURN` and `RECHARGE` as interrupts | Gives clear "strategy changes" to log and visualize |
| Output | JSONL trace, readable text trace, JSON + Markdown report, PNG + GIF | Covers all deliverables |

### 3.1 Default parameters (all overridable in YAML)

| Group | Parameter | Default |
|---|---|---|
| Grid | width × height | 20 × 20 |
| Grid | obstacle density | 0.10 (map must stay fully connected) |
| Battery | capacity / initial | 100 / 100 |
| Time | budget (ticks) | 250 |
| Costs | MOVE | 1 battery, 1 tick |
| Costs | SCAN_SIGNAL | 2 battery, 1 tick |
| Costs | SCAN_AREA radius r (1–3) | (2 + 2r) battery, (1 + r) ticks |
| Costs | RECHARGE (only on a charger) | +20 battery, 2 ticks per action (capped at capacity) |
| Chargers | count | start cell + 1 more |
| Signal | amplitude per status `A_k` | active 1.0, low_power 0.6, damaged 0.35 |
| Signal | range scale `d0` | 6.0 |
| Signal | strength noise `sigma_s` | 0.05 |
| Signal | bearing noise | `sigma_theta = 8° + 2°·d` (d = distance to EVE) |
| Signal | dropout probability per status | active 0.05, low_power 0.25, damaged 0.50 |
| Clues | count | 5 |
| Clues | type mix | bearing 50%, range 30%, status 20% |
| Clues | noise | bearing 15°, range 2.0 cells, status accuracy 0.8 |
| Clues | detection chance inside scan radius | 0.9 |
| Decoys (bonus) | spoof probability per SCAN_SIGNAL | 0.0 default, 0.15 in hard mission |
| Agent | confidence to enter TRACK | 0.50 |
| Agent | confidence to enter VERIFY | 0.75 |
| Agent | confidence to DECLARE | 0.90 location and 0.70 status |
| Agent | safety margin on return reserve | 10% + 3 battery |
| Agent | Monte-Carlo samples for info gain | 40 |
| Agent | candidate viewpoints per decision | ≤ 25 |

---

## 4. Architecture and repository layout

```text
                +----------------+       Action        +-----------------------+
 config.yaml -> |  Environment   | <------------------ |        Agent          |
                |  (hidden truth)| ------------------> |  Belief + Planner +   |
                +----------------+  Observation only   |  Strategy + Logger    |
                        |                              +-----------+-----------+
                        |                                          |
                        v                                          v
                 ground truth (debug/viz only)           trace.jsonl, report.md,
                                                         frames, GIF
```

```text
walle-eve-signal/
├── PLAN.md
├── README.md
├── requirements.txt
├── pyproject.toml                 # optional, for `pip install -e .`
├── configs/
│   ├── mission_easy.yaml
│   ├── mission_medium.yaml
│   ├── mission_hard_decoys.yaml
│   └── CONFIG_REFERENCE.md
├── src/walle/
│   ├── __init__.py
│   ├── geometry.py        # bearing(), distance(), wrap_angle()
│   ├── config.py          # dataclasses + YAML loading + validation
│   ├── world.py           # map generation, hidden ground truth
│   ├── actions.py         # Action enum + ActionSpec
│   ├── observations.py    # Observation, ClueReading, PublicMissionInfo
│   ├── signal_model.py    # forward sensor model + likelihood builders
│   ├── environment.py     # Env: reset(), step(action) -> Observation
│   ├── belief.py          # Belief class (Bayesian update, stats)
│   ├── planner.py         # BFS/A*, reachability, safe-return reserve
│   ├── info_gain.py       # Monte-Carlo expected information gain
│   ├── strategies.py      # Strategy state machine + weights
│   ├── agent.py           # Main autonomous agent
│   ├── baselines.py       # RandomAgent, GreedyBearingAgent
│   ├── trace.py           # TraceLogger (jsonl + txt)
│   ├── report.py          # Final mission report generator
│   ├── viz.py             # ASCII + matplotlib + GIF
│   ├── runner.py          # run_mission(config, agent) -> RunResult
│   ├── benchmark.py       # many random missions, metrics
│   └── cli.py             # `python -m walle ...`
├── tests/
│   ├── test_config.py
│   ├── test_world.py
│   ├── test_environment.py
│   ├── test_signal_model.py
│   ├── test_belief.py
│   ├── test_planner.py
│   ├── test_agent_invariants.py
│   ├── test_separation.py
│   ├── test_trace_report.py
│   └── test_determinism.py
├── outputs/                        # committed sample runs
│   └── mission_medium_seed7/
│       ├── trace.jsonl
│       ├── trace.txt
│       ├── report.md
│       ├── report.json
│       ├── summary.png
│       └── run.gif
├── docs/
│   ├── DECISIONS.md
│   ├── DESIGN.md
│   └── images/
└── scripts/
    ├── run_all_samples.sh
    └── make_gif.py
```

---

## 5. Detailed technical specifications

### 5.1 Mission config (YAML)

```yaml
mission:
  name: mission_medium
  seed: 7
  grid:
    width: 20
    height: 20
  start: [2, 2]
  obstacles:
    mode: random            # random | explicit | ascii
    density: 0.10
    # explicit: [[5,5],[5,6]]
    # ascii: ["....#...", "..#....."]   # '#' wall, 'C' charger, 'S' start
  chargers: [[2, 2], [15, 9]]
  eve:
    location: random        # random | [x, y]
    status: random          # random | active | low_power | damaged
    mobility: static        # static | random_walk   (random_walk is a bonus)
  clues:
    count: 5
    placement: random       # random | explicit
    # explicit: [{pos: [8,8], type: bearing}, ...]
    type_mix: {bearing: 0.5, range: 0.3, status: 0.2}

initial_signal:
  bearing_deg: 60           # optional (compass bearing from start)
  coordinates: null         # optional [x, y] noisy position hint
  coordinates_sigma: 4.0
  strength: 0.35
  timestamp: 0

resources:
  battery_capacity: 100
  battery_initial: 100
  time_budget: 250
  costs:
    move:        {battery: 1, time: 1}
    scan_signal: {battery: 2, time: 1}
    scan_area:   {battery_base: 2, battery_per_radius: 2, time_base: 1, time_per_radius: 1, max_radius: 3}
    recharge:    {battery_gain: 20, time: 2}

sensor:
  noise_scale: 1.0          # multiplies all noise sigmas (bonus: raise for harder missions)
  strength_sigma: 0.05
  bearing_sigma_base_deg: 8
  bearing_sigma_per_cell_deg: 2
  d0: 6.0
  amplitude: {active: 1.0, low_power: 0.6, damaged: 0.35}
  dropout:   {active: 0.05, low_power: 0.25, damaged: 0.50}
  decoys:
    count: 0                # bonus
    spoof_probability: 0.0
  clue_noise:
    bearing_sigma_deg: 15
    range_sigma: 2.0
    status_accuracy: 0.8
    detect_probability: 0.9
    false_clue_probability: 0.0   # bonus

agent:
  type: bayes_planner       # bayes_planner | random | greedy_bearing
  seed: 123
  assumed_spoof_rate: 0.0   # robustness: set ~0.15 in the decoy mission
  mc_samples: 40
  max_candidates: 25
  thresholds:
    track: 0.50
    verify: 0.75
    declare_location: 0.90
    declare_status: 0.70
  safety: {margin_fraction: 0.10, margin_flat: 3}
```

Validation rules (raise a clear `ConfigError`): start is not a wall; all chargers/start on free cells; probabilities sum to 1; costs ≥ 0; `battery_initial ≤ capacity`; at least one of `bearing_deg`, `coordinates`, `strength` is present; the map is fully connected (regenerate with the next derived seed up to 50 times in `random` mode, else error).

### 5.2 Actions

| Action | Parameters | Effect | Observation returned |
|---|---|---|---|
| `MOVE_N/E/S/W` | — | Move one cell if free, else bump (still pays cost) | position, `bumped` flag |
| `SCAN_SIGNAL` | — | Take a signal reading at current cell | strength, bearing (or `None` on dropout) |
| `SCAN_AREA` | `radius ∈ {1,2,3}` | Reveal clues within the radius (each with detect probability) | list of `ClueReading` |
| `RECHARGE` | — | Only on a charger: `+battery_gain`, capped | new battery |
| `DECLARE` | `x, y, status` | Ends the mission with the agent's final answer | terminal flag |

"Turn back" is **not** an environment action. It is an agent strategy (`RETURN`) that plans a shortest path to the nearest charger and issues MOVE actions.

Episode ends when: `DECLARE` is called, battery reaches 0 away from a charger (**stranded** = failure), time runs out (agent is auto-declared with its last best estimate flagged as `forced`), or the agent exceeds `max_steps = 2 × time_budget`.

### 5.3 Observation and public info (the only things the agent may see)

```python
@dataclass(frozen=True)
class PublicMissionInfo:          # given once at reset()
    width: int; height: int
    walls: frozenset[tuple[int,int]]
    chargers: tuple[tuple[int,int], ...]
    start: tuple[int,int]
    battery_capacity: int; battery_initial: int; time_budget: int
    costs: CostTable
    initial_signal: InitialSignal
    sensor_prior: SensorPrior     # the sensor model constants the agent is allowed to assume

@dataclass(frozen=True)
class Observation:                # returned after every step
    step: int
    position: tuple[int,int]
    battery: int
    time_left: int
    action_succeeded: bool
    bumped: bool
    on_charger: bool
    signal: SignalReading | None  # present after SCAN_SIGNAL
    clues: tuple[ClueReading, ...]# present after SCAN_AREA (new + repeated clues)
    done: bool
    done_reason: str | None       # declared | stranded | timeout
```

`SignalReading = (strength: float | None, bearing_deg: float | None, dropout: bool)`
`ClueReading = (clue_id: int, position: (x,y), type: str, value: float|str)` where value is a bearing (deg), a distance (cells) or a status label.

### 5.4 Forward sensor model (environment side)

For true EVE location `e`, status `k`, agent position `p`, `d = ‖e − p‖₂`:

```text
mu(d, k)       = A_k / (1 + (d / d0)^2)
dropout?       ~ Bernoulli(P_drop[k])
strength_obs   = clip(mu + N(0, sigma_s * noise_scale), 0, 1)
sigma_theta(d) = (b_base + b_per_cell * d) * noise_scale          # degrees
bearing_obs    = (bearing(p -> e) + N(0, sigma_theta(d))) mod 360
```

If the agent stands on EVE's cell, bearing is undefined: return `bearing=None` and a very strong strength reading. Decoy spoof (bonus): with probability `spoof_probability` the reading is generated from a random decoy location with `A = 1.0` instead of the real EVE.

Clues (generated at reset, hidden until revealed):

```text
bearing clue at c : value = bearing(c -> e) + N(0, clue_bearing_sigma)
range clue   at c : value = ‖e - c‖₂ + N(0, clue_range_sigma)  (clipped >= 0)
status clue  at c : label = true status w.p. q, else a uniformly random wrong status
false clue (bonus): with prob p_false, the value is replaced by a random value
```

### 5.5 Inference model (agent side) — likelihood builders

All builders return an array of shape `(H, W, K)` with the likelihood of the observation under each hypothesis `(x, y, k)`. Everything is vectorized with precomputed coordinate grids. Walls and unreachable cells get likelihood 0 (EVE cannot be inside a wall).

```text
L_strength(s | x,y,k)  = N(s ; mu(d, k), sigma_s)            where d = dist(agent, (x,y))
L_bearing(θ | x,y,k)   = N(wrap(θ − bearing(agent -> (x,y))) ; 0, sigma_theta(d))
L_dropout(k)           = P_drop[k]                            (observation = dropout)
L_nodropout(k)         = 1 − P_drop[k]    (multiply with the strength and bearing likelihoods)
L_range(r | x,y)       = N(r ; dist(clue, (x,y)), sigma_range)
L_cluebearing(φ | x,y) = N(wrap(φ − bearing(clue -> (x,y))) ; 0, sigma_clue_bearing)
L_status(label | k)    = q if label == k else (1 − q)/2
```

Robust mixture for decoys / false clues (use when `assumed_spoof_rate = ε > 0`):

```text
L_robust = (1 − ε) * L_true + ε * L_uniform      # L_uniform = a small constant, e.g. 1/(H*W)
```

Initial signal handling (no special code path): treat it as the **first observation taken at the start cell at timestamp 0** (bearing + strength). If `coordinates` is given, multiply the prior by a Gaussian centred on it with `coordinates_sigma`.

Optional (bonus, `mobility = random_walk`): before every update call `belief.predict(drift_sigma)` which blurs the location marginal with a small Gaussian kernel (convolution) and respects walls. Use the observation timestamp to scale the blur.

### 5.6 Belief class (`belief.py`)

```python
class Belief:
    def __init__(self, info: PublicMissionInfo, status_prior: dict[str,float] | None = None): ...
    def update(self, likelihood: np.ndarray) -> float:
        """Bayes rule: B <- normalize(B * L). Return KL(new || old) in bits (information gained).
        If the total mass collapses to ~0 (contradiction), fall back: B <- 0.9*old + 0.1*uniform, set self.contradiction_count += 1."""
    def predict(self, drift_sigma: float) -> None: ...       # bonus
    def location_marginal(self) -> np.ndarray                # (H,W)
    def status_marginal(self) -> dict[str,float]
    def entropy(self) -> float                               # joint entropy, bits
    def map_estimate(self) -> tuple[int,int]
    def mean_location(self) -> tuple[float,float]
    def mass_within(self, center, radius) -> float           # location confidence
    def credible_region(self, mass=0.90) -> list[tuple[int,int]]
    def second_mode(self, exclude_radius=3) -> tuple[tuple[int,int], float]
    def snapshot(self) -> dict                               # compact dict for the trace
```

Location confidence used everywhere = `mass_within(MAP, radius=1.5)`. Status confidence = max of `status_marginal()`.

### 5.7 Planner (`planner.py`)

* `bfs_distances(source, walls, size) -> dict/array`: shortest path lengths (4-connected).
* `shortest_path(a, b)`: returns list of cells. Cache BFS from each charger at reset.
* `nearest_charger(pos) -> (charger, dist)`.
* `return_reserve(pos, costs, safety)`: `dist_to_nearest_charger(pos) * move_battery_cost`, then `reserve = ceil(that * (1 + margin_fraction) + margin_flat)`.
* **Safety invariant (the most important rule in the project):** the agent may only choose an action `a` if, after paying its battery cost and arriving at the resulting position, `battery_after >= return_reserve(position_after)`. If no informative action satisfies it, the agent chooses `RETURN` (move toward a charger) and, once on the charger, `RECHARGE`. The only exception is a `forced final dash`, which is disabled by default.

### 5.8 Expected information gain (`info_gain.py`)

```text
EIG_signal(p):
    sample M hypotheses (x,y,k) from the current belief (agent's own RNG)
    for each: simulate a reading at agent position p using the forward model with the *assumed* sensor constants
    compute the posterior with the likelihood builders
    EIG = H(current belief) − mean(H(posterior))            # bits
EIG_area(p, r):
    proxy = expected_remaining_clues * (unscanned_free_cells_within_r / unscanned_free_cells_total) * clue_gain_bits
    where clue_gain_bits defaults to 1.0 and expected_remaining_clues = max(0, expected_total − found)
```

The agent tracks `scanned_mask` (cells covered by earlier SCAN_AREA) and `clues_found` itself, from observations only.

### 5.9 Strategy state machine and utility (`strategies.py`, `agent.py`)

States: `EXPLORE`, `TRACK`, `VERIFY`, `RETURN`, `RECHARGE`, `DECLARE`.

```text
INIT      -> EXPLORE
EXPLORE   -> TRACK      when location_confidence >= thresholds.track
TRACK     -> EXPLORE    when location_confidence < 0.30 (hysteresis; log "belief collapsed / conflicting evidence")
TRACK     -> VERIFY     when location_confidence >= thresholds.verify
VERIFY    -> DECLARE    when location_conf >= declare_location AND status_conf >= declare_status
ANY       -> RETURN     when the safety invariant rejects every non-return action or battery < reserve + cost of the cheapest useful action
RETURN    -> RECHARGE   when standing on a charger and battery < 90% of capacity
RECHARGE  -> previous   when battery >= 90% of capacity (or enough for the next planned leg + reserve)
ANY       -> DECLARE    (forced) when time_left <= forced_declare_time (default 8 ticks + path-free) or no affordable useful action exists
```

Decision procedure at every step (receding horizon, re-plan each tick):

```text
1. Update belief with the latest observation (all builders for that observation).
2. Update strategy state; if it changed, record "strategy_change" with from, to and trigger numbers.
3. If DECLARE: build the final answer and return DECLARE(x, y, status).
4. Build candidate goals:
     a. SCAN_SIGNAL here                         (if standing at a useful viewpoint)
     b. SCAN_AREA(r) here for r in 1..3
     c. GO_TO viewpoint v for v in <= 25 candidates (see below), followed by a scan there
     d. RETURN to nearest charger (+ RECHARGE if on charger)
5. Candidate viewpoints (deduplicated, reachable, safe):
     - current position and its 4 neighbours
     - ring of cells 4-8 away from the belief mean at different compass angles (triangulation baseline)
     - cells that maximize angular separation from earlier scan positions as seen from the belief mean
     - cells near MAP (for TRACK/VERIFY) at distance 1-3
     - the chargers
     - a few random reachable cells (the agent's own RNG)
6. Score each candidate:
        gain     = w_info * EIG  (+ w_clue * EIG_area  for area scans)
        progress = w_prog * (reduction in expected distance to belief mean after reaching v)
        cost     = battery_cost/capacity + time_cost/time_budget  (including the travel leg)
        U        = (gain + progress) / (1 + w_cost * cost)
        reject if the safety invariant fails
7. Take the best candidate; execute only the FIRST action of its plan (MOVE or the scan).
8. Log the top-5 candidates with their EIG, cost and score, plus the template reasoning string.
```

Strategy weights:

| State | w_info | w_clue | w_prog | w_cost |
|---|---|---|---|---|
| EXPLORE | 1.0 | 0.6 | 0.1 | 1.5 |
| TRACK | 0.7 | 0.2 | 0.5 | 1.5 |
| VERIFY | 1.0 | 0.0 | 0.3 | 1.0 |
| RETURN | pure shortest path to the nearest charger | | | |

Anti-dithering rule: if the same two cells alternate for 4 consecutive moves, penalize the revisited cell (`-0.2` utility per revisit) and log "loop detected".

### 5.10 Baselines (`baselines.py`) — needed for the benchmark

* `RandomAgent`: random moves, scans every ~5 steps, declares at a random time with the last bearing line's midpoint or the grid centre. Still obeys the safe-return rule (else it just strands).
* `GreedyBearingAgent`: follows the last measured bearing greedily, scans every 3 steps, declares when strength > 0.8.
* Both use the same `Agent` protocol: `reset(info)`, `act(obs) -> (Action, Decision)`.

### 5.11 Trace format (`trace.jsonl`, one JSON per step)

```json
{
  "step": 12,
  "tick": 27,
  "strategy": "EXPLORE",
  "strategy_change": null,
  "state_before": {"pos": [3, 4], "battery": 71, "time_left": 223, "reserve": 14},
  "decision": {
    "action": "SCAN_SIGNAL",
    "plan": ["MOVE_E", "MOVE_E", "SCAN_SIGNAL"],
    "top_candidates": [
      {"goal": "SCAN_SIGNAL@(5,4)", "eig_bits": 1.31, "cost": 0.05, "utility": 1.22, "safe": true},
      {"goal": "SCAN_AREA(2)@(3,4)", "eig_bits": 0.40, "cost": 0.07, "utility": 0.37, "safe": true}
    ],
    "reasoning": "Entropy 6.1 bits; best next viewpoint (5,4) gives 1.31 bits for 4 battery; reserve 14 satisfied (71-4=67)."
  },
  "observation": {"pos": [4, 4], "battery": 69, "signal": null, "clues": [], "bumped": false},
  "belief_after": {
    "map": [14, 16], "map_prob": 0.04, "entropy_bits": 5.8, "info_gain_bits": 0.31,
    "location_confidence": 0.12, "status_probs": {"active": 0.5, "low_power": 0.3, "damaged": 0.2}
  }
}
```

The text trace (`trace.txt`) prints the same data as readable lines (`[step 012 | EXPLORE] ...`). Heavy arrays (full belief grids) are saved every N steps to `belief_frames.npz` for visualization, not in the JSONL.

### 5.12 Mission report (`report.md` and `report.json`)

Sections:
1. **Mission summary:** config name, seed, outcome (`declared` / `forced_declare` / `stranded` / `timeout`), steps, ticks used.
2. **Final answer:** inferred location `(x, y)`, 90% credible region (size and bounding box), inferred status with probabilities, **confidence** (location and status) and a calibration note.
3. **Evidence table:** every piece of evidence in order (step, type: signal / bearing clue / range clue / status clue, raw value, information gain in bits, effect on belief, e.g. "moved MAP from (9,9) to (13,15)"). Sort the top 5 most influential.
4. **Resource usage:** battery used, recharges, time used, scans by type, distance travelled, minimum battery margin.
5. **Strategy timeline:** each strategy change with its trigger.
6. **Recommended next step** (generated by rules):
   * Confident: "Dispatch WALL-E to (x,y), path length N, battery needed B, recharge at charger C first (battery now b)."
   * Not confident: "Gather more evidence: scan from viewpoint v (best EIG g bits); alternative hypothesis at (x2,y2) with probability p2."
   * Status low_power/damaged: add a rescue note ("approach with a charging payload").
7. **Ground-truth check (simulation only, clearly labelled):** true location, true status, error in cells, whether the truth was inside the 90% region.
8. **Limitations and assumptions.**

### 5.13 Metrics (used by the tests and the benchmark)

`success` = declared location within 2 cells of truth **and** correct status · `location_error` · `status_correct` · `steps` · `battery_used` · `stranded` · `forced_declare` · `clues_found` · `credible_hit` (truth inside the 90% region) · `final_entropy`.

---

## 6. Phases

> **Time boxes assume Antigravity writes most of the code.** Your job is to give the prompt, review, run, and commit. Each phase ends with a checklist. Do not move on until it is green.

---

### Phase 0 — Project scaffold and ground rules (≈ 30 min)

**Goal:** Empty but runnable package, tooling, docs skeleton.

**Tasks**
- Create the repo tree in Section 4 with empty modules containing docstrings only.
- `requirements.txt`: `numpy`, `pyyaml`, `matplotlib`, `pillow`, `imageio`, `pytest`.
- `pyproject.toml` so `pip install -e .` works; `python -m walle --help` prints a help text.
- `docs/DECISIONS.md` (decision log) and `docs/DESIGN.md` (to be filled later).
- `.gitignore`, `git init`, first commit.
- `geometry.py`: `distance(a, b)`, `bearing(a, b)` (compass, 0 = N), `wrap_angle(delta)` into (−180, 180], plus tests for 8 compass directions and wrap-around.

**Acceptance criteria**
- `pip install -r requirements.txt` works in a fresh venv.
- `pytest -q` passes (geometry tests only).
- `python -m walle --help` works.

**Antigravity prompt**
```text
Start Phase 0 from PLAN.md. Create the full repo skeleton from Section 4, requirements.txt,
pyproject.toml (src layout), .gitignore, docs/DECISIONS.md, and implement geometry.py
(distance, bearing with compass convention 0=North, wrap_angle) with tests covering N/E/S/W,
the four diagonals, and the 359->1 degree wrap. Add a minimal cli.py with argparse and a
--help text. Run pytest and show me the output. Then stop.
```

---

### Phase 1 — Config schema and world generation (≈ 1.5 h)

**Goal:** Load and validate a mission config, then build the hidden world from the seed.

**Tasks**
- `config.py`: dataclasses mirroring the YAML in 5.1, `load_config(path)`, `validate(cfg)`, helpful `ConfigError` messages, defaults for omitted fields.
- `world.py`:
  - generate obstacles (`random` / `explicit` / `ascii`), ensure connectivity with BFS (retry with derived seeds);
  - place chargers, EVE (random free reachable cell at least 8 cells from start by default), status, clues (random free reachable cells, not on start/charger/EVE), decoys;
  - expose `World` with **private** ground-truth fields and a `public_info()` method that returns `PublicMissionInfo`.
- Write `configs/mission_easy.yaml` (small 12×12 grid, few walls, strong initial signal, 1 charger), `mission_medium.yaml` (the default 20×20 example) and `CONFIG_REFERENCE.md` describing every field.

**Acceptance criteria**
- Invalid configs produce a readable error (test at least 6 invalid cases).
- Same seed gives an identical world; different seeds give different worlds.
- Every free cell is reachable from the start; EVE and clues are never in walls.
- `public_info()` contains no hidden truth (assert in a test).

**Antigravity prompt**
```text
Start Phase 1 from PLAN.md (sections 5.1, 5.3 and 6/Phase 1). Implement config.py,
world.py, observations.py (dataclasses only), the three YAML files and CONFIG_REFERENCE.md.
Hidden truth must live only inside World private attributes. Write tests: invalid configs,
seed determinism, connectivity, hidden-truth-not-in-public-info. Show me an ASCII print of
the generated medium world (with truth marked) as a debug helper in world.py. Stop after tests pass.
```

---

### Phase 2 — Signal model and environment API (≈ 2 h)

**Goal:** A working simulator: `reset()` and `step(action)` return observations; costs and rules are enforced.

**Tasks**
- `actions.py`: `ActionType` enum + `Action` dataclass (`type`, optional `radius`, optional `declare_x/y/status`) and `cost_of(action, costs)`.
- `signal_model.py` (forward model part): `expected_strength(d, status)`, `sample_signal(...)`, `sample_clue_value(...)` as in 5.4, with a helper `noise_scale`.
- `environment.py`: class `Environment(config)` with:
  - `reset() -> (PublicMissionInfo, Observation)` (includes the initial signal as given in the config);
  - `step(action) -> Observation` implementing movement/bump, scanning, clue reveal with detect probability, recharge-only-on-charger, battery and time accounting, termination reasons, a stranded rule, forced declare on timeout;
  - `ground_truth()` for the runner and report only (documented as "never pass to the agent").
- Clues are revealed **only** if within the scan radius and detected; revealed clues are remembered by the env (`revealed` set) so repeated scans return them again without extra detection rolls.

**Acceptance criteria**
- Moving into a wall costs resources and keeps position, with `bumped = True`.
- Battery/time never go negative; `RECHARGE` off-charger is rejected (`action_succeeded=False`, cost still applies, documented).
- Statistics test: with 2000 samples at a fixed distance, the mean strength matches `mu(d, k)` within 3 standard errors.
- Scan at distance exactly beyond the radius never reveals a clue; inside the radius reveals roughly 90% of the time.
- Same seed and the same action list give the same observations.

**Antigravity prompt**
```text
Start Phase 2 from PLAN.md (5.2, 5.4, Phase 2). Implement actions.py, signal_model.py
(forward model only), environment.py. Enforce all rules from the spec: costs, bump, charger-only
recharge, termination reasons, stranded, forced declare on timeout, clue reveal by scan radius with
detect probability. Add tests for each rule plus statistical tests of the sensor model with a fixed
seed. Add a tiny script scripts/manual_play.py that lets me type actions in the terminal and prints
observations so I can feel the environment. Stop after tests pass.
```

---

### Phase 3 — Belief engine (≈ 2 h)

**Goal:** Correct Bayesian inference over `(x, y, status)`.

**Tasks**
- `signal_model.py` (inference part): likelihood builders from 5.5, vectorized over the grid, with robust mixture support.
- `belief.py`: the `Belief` class from 5.6 including KL information gain, entropy, MAP, mean, `mass_within`, `credible_region`, `second_mode`, `snapshot`, and the contradiction fallback.
- Helper `apply_observation(belief, obs, agent_pos, info)` that picks the right builders for a signal reading, dropout, or clue readings and updates in the right order.
- Initial belief: uniform on free cells × status prior, then the initial-signal observation applied at the start cell.

**Acceptance criteria (the tests that prove it works)**
- Belief always sums to 1 within 1e-9 and is exactly 0 on walls.
- With **noise-free** synthetic observations from 3 different positions, the MAP equals the true cell.
- With realistic noise, after 6 signal scans from spread-out positions, the median error over 50 seeds is ≤ 2 cells.
- Entropy never increases on average after an informative observation (statistically, over many trials).
- Dropouts shift probability toward `damaged` / `low_power` after repeated dropouts (test).
- Status clue with accuracy 0.8 moves the status marginal in the expected direction.
- A deliberately wrong (decoy) bearing with `ε = 0.15` does not collapse the belief to zero mass on the truth (robust test).

**Antigravity prompt**
```text
Start Phase 3 from PLAN.md (5.5, 5.6, Phase 3). Implement the likelihood builders in
signal_model.py and the Belief class in belief.py exactly as specified, vectorized with NumPy.
Write the tests listed under Phase 3 acceptance criteria. Also create a notebook-free demo script
scripts/belief_demo.py that simulates a few scans and saves a PNG with 4 panels showing the belief
heatmap after 0, 1, 3 and 6 scans (truth marked) so I can visually confirm it converges. Stop after tests pass.
```

---

### Phase 4 — Planner, safe return and information gain (≈ 2 h)

**Goal:** All "thinking tools" for the agent, tested separately.

**Tasks**
- `planner.py`: BFS distance maps, shortest paths, nearest charger, `return_reserve`, `is_safe(action_plan, state)` implementing the invariant in 5.7.
- `info_gain.py`: `eig_signal(belief, position, rng, info)` Monte-Carlo as in 5.8 and `eig_area(...)` proxy.
- Candidate-viewpoint generator described in 5.9 (step 5) as a pure function: `generate_candidates(state, belief, scan_history, info, rng)`.

**Acceptance criteria**
- Shortest paths match a brute-force BFS on random maps (property test).
- `return_reserve` is monotonic in distance.
- `eig_signal` is higher at a position that is a good triangulation baseline than at a position collinear with the previous scan and the belief mean (construct a test belief by hand).
- `eig_signal` ≥ 0 within Monte-Carlo noise and is reproducible with the same seed.
- The candidate generator never returns walls, unreachable cells, or more than `max_candidates` items.

**Antigravity prompt**
```text
Start Phase 4 from PLAN.md (5.7, 5.8, 5.9 step 5, Phase 4). Implement planner.py, info_gain.py
and the candidate generator. Write the property tests and the hand-constructed triangulation test
from the acceptance criteria. Keep every function pure (inputs -> outputs, no hidden state) so it is
unit-testable. Stop after tests pass.
```

---

### Phase 5 — Autonomous agent and strategy state machine (≈ 3 h)

**Goal:** A complete agent that runs a mission end to end using only observations.

**Tasks**
- `strategies.py`: `Strategy` enum, transition function `next_strategy(state, belief_stats, resources, thresholds)` that returns `(new_strategy, trigger_text)`.
- `agent.py`: class `BayesPlannerAgent` implementing `reset(info)` and `act(obs) -> (Action, Decision)` as in 5.9, including:
  - belief update from the observation,
  - strategy transitions with log text,
  - candidate scoring, safe filtering, execution of the first action of the plan,
  - plan persistence (keep a multi-step plan until its target is reached or new evidence flips the best candidate by a margin > 15%),
  - loop detection and revisit penalty,
  - RETURN and RECHARGE handling,
  - DECLARE with the final `(x, y, status)` from the belief.
- `runner.py`: `run_mission(config_path, agent_type, out_dir) -> RunResult` ties the environment and the agent together, passes **only** `Observation` / `PublicMissionInfo` to the agent, and calls the trace logger (stub allowed until Phase 6).
- `cli.py`: `python -m walle run --config configs/mission_medium.yaml --out outputs/`.

**Acceptance criteria**
- On `mission_easy.yaml` the agent declares within 3 cells of the truth in ≥ 8 of 10 seeds.
- **Safety property test:** over 100 random seeds the agent is **never** stranded.
- The agent uses all of: MOVE, SCAN_SIGNAL, SCAN_AREA, RECHARGE and DECLARE across the test missions (check at least one mission forces a recharge by using a small battery).
- Strategy transitions occur in the order `EXPLORE → TRACK → VERIFY → DECLARE` in normal runs, and `RETURN/RECHARGE` appear when the battery is low.
- `test_separation.py`: static check that `agent.py`, `strategies.py`, `planner.py`, `info_gain.py` and `belief.py` do not import `world`/`environment` internals, and the agent receives no attribute that exposes ground truth.

**Antigravity prompt**
```text
Start Phase 5 from PLAN.md (5.9, 5.10, Phase 5). Implement strategies.py, agent.py, runner.py
and the CLI `run` command. The agent receives only PublicMissionInfo and Observation. Follow the
decision procedure in 5.9 exactly: belief update -> strategy update -> candidate generation ->
safety filter -> utility scoring -> execute first action -> log. Add the safety property test
(100 seeds, never stranded), the separation test, and an easy-mission success test. If success
is below target, tune weights/thresholds in config (not in code) and document each change in
docs/DECISIONS.md with the before/after numbers. Stop after tests pass and show me the final
state of one run in the terminal.
```

---

### Phase 6 — Trace logging and final report (≈ 1.5 h)

**Goal:** Deliverables #4 and #5 from the task.

**Tasks**
- `trace.py`: `TraceLogger` writing `trace.jsonl` (schema 5.11) and `trace.txt`; saves belief grids every 2 steps to `belief_frames.npz`; includes `strategy_change` events, the top-5 candidates and reasoning strings generated from real numbers.
- `report.py`: build `report.json` and `report.md` per 5.12, including the evidence table with per-observation information gain and the rule-generated recommended next step.
- Credible region + calibration note: "truth inside the 90% region: yes/no".
- Hook both into `runner.py`.

**Acceptance criteria**
- Every step has exactly one JSONL line with all schema fields (schema test).
- Replaying the trace's actions on a fresh environment with the same seed reproduces the same observations (replay test).
- The report always contains all 8 sections, and the numbers in the report match `RunResult` (test).
- Recommended-next-step text differs correctly between the confident and the unconfident cases (two tests with crafted beliefs).
- Same seed run twice produces byte-identical `trace.jsonl` (determinism test).

**Antigravity prompt**
```text
Start Phase 6 from PLAN.md (5.11, 5.12, Phase 6). Implement trace.py and report.py and wire them
into runner.py. Reasoning strings must be template-based from real numbers. Add the schema test,
replay test, report-section test and determinism test. Then run the medium mission with seed 7 and
save the outputs under outputs/mission_medium_seed7/. Show me the first 15 lines of trace.txt and
the full report.md. Stop.
```

---

### Phase 7 — Visualization (≈ 2 h)

**Goal:** Clear visuals of the path, clue locations, belief and strategy changes.

**Tasks**
- `viz.py`:
  1. **ASCII renderer** (`render_ascii(state, belief, show_truth=False)`): `#` wall, `C` charger, `W` WALL-E, `!` discovered clue, `E` true EVE (only when `show_truth=True`, post-mission), belief intensity with the ramp `" .:-=+*#%@"` for empty cells; legend underneath. A CLI flag `--ascii` prints frames live.
  2. **Matplotlib frame renderer**, 3 panels per frame:
     - map with walls, chargers, travelled path (coloured by strategy), discovered clues (marker by type), scan locations, belief heatmap overlay, MAP star, 90% credible contour, and truth marker only in the final frame;
     - battery and time curves with recharge events;
     - entropy / location-confidence curves with strategy-change vertical lines and labels.
  3. `summary.png`: the final frame with the full path and legend.
  4. `run.gif`: a frame every step (or every 2 steps for long runs), 6–8 fps, plus a 2 second hold on the last frame.
- CLI: `python -m walle viz --run outputs/mission_medium_seed7/` creates frames and the GIF from saved files (so visualization does not re-run the mission).

**Acceptance criteria**
- GIF generation completes in under 60 s for a typical run.
- Strategy changes are visible in two places: coloured path segments and labelled vertical lines.
- The truth marker appears **only** in the final frame and the report, never during the run.
- Works headless (`matplotlib.use("Agg")`).

**Antigravity prompt**
```text
Start Phase 7 from PLAN.md (Phase 7). Implement viz.py with the ASCII renderer, the three-panel
matplotlib frame renderer, summary.png and run.gif, and the `viz` CLI command that works from the saved
trace + belief_frames.npz. Use the Agg backend. Reveal the true EVE only on the final frame.
Generate the visuals for outputs/mission_medium_seed7 and show me summary.png. Stop.
```

---

### Phase 8 — Testing hardening and robustness (≈ 1.5 h)

**Goal:** Confidence that nothing silly breaks.

**Tasks**
- Edge-case missions (as YAML in `tests/data/`): tiny battery (forces early recharge), start adjacent to EVE, EVE far away behind walls, no bearing in the initial signal (coordinates only), zero clues, very noisy sensors.
- Fuzz test: 200 random configs, assert no crashes, no negative resources, never stranded, report produced.
- Lint/format pass; remove dead code; make sure every public function has a docstring.
- Run coverage (`pytest --cov`) and aim for ≥ 80% on `belief`, `planner`, `environment`, `agent`.

**Acceptance criteria**
- `pytest -q` is green and takes under 2 minutes.
- Fuzz test passes with 200 seeds.
- Add `scripts/run_all_samples.sh` which regenerates every sample output in one command.

**Antigravity prompt**
```text
Start Phase 8 from PLAN.md. Add the edge-case mission YAMLs and tests, the 200-config fuzz test,
the coverage run, and scripts/run_all_samples.sh. Fix any bug the new tests expose and document each
fix in docs/DECISIONS.md. Show me the final pytest summary and coverage table. Stop.
```

---

### Phase 9 — Bonus A: noisy sensors and decoy / spoofed signals (≈ 1.5 h)

**Goal:** Robustness story that impresses reviewers.

**Tasks**
- Enable `decoys.count`, `spoof_probability`, `false_clue_probability`, `noise_scale` in the environment (forward model already supports them from Phase 2).
- Agent robustness: set `assumed_spoof_rate`, use the mixture likelihood, add **contradiction detection**: if a reading has likelihood below a threshold under the current belief's top hypothesis, flag it as "suspicious", take a confirming scan from a different viewpoint before trusting it (log "suspected decoy").
- `configs/mission_hard_decoys.yaml` with `noise_scale: 1.5`, `spoof_probability: 0.15`, `false_clue_probability: 0.1`, `assumed_spoof_rate: 0.15`.
- Ablation: run the hard mission with `assumed_spoof_rate = 0` vs `0.15` over 50 seeds and compare success rates.

**Acceptance criteria**
- The agent with robust likelihood has a higher success rate than the naive one on the hard mission (report the numbers, even if the gap is small).
- Trace marks suspicious readings and the report lists them in "Evidence" with the status `discounted`.

**Antigravity prompt**
```text
Start Phase 9 (Bonus A) from PLAN.md. Enable decoys, false clues and higher noise end to end.
Add the robust mixture likelihood usage in the agent, suspicious-reading detection with a confirming
scan, the hard-decoys config, and an ablation script scripts/ablation_decoys.py that compares
assumed_spoof_rate 0 vs 0.15 over 50 seeds and prints a table + saves a CSV. Update the report to
list discounted readings. Stop after tests pass.
```

---

### Phase 10 — Bonus B: benchmark and planner comparison (≈ 1.5 h)

**Goal:** Generalization evidence across random missions.

**Tasks**
- `benchmark.py`: generates `N` random missions (default 100) by varying seed, grid size (12–25), wall density (0–0.2), battery (60–120), noise scale (0.8–1.5) and runs `random`, `greedy_bearing` and `bayes_planner` agents on identical missions.
- Output `outputs/benchmark/benchmark_results.csv` with all metrics from 5.13 per run, an aggregated markdown table, and a bar-chart PNG (success rate, mean error, mean battery used, stranded rate).
- CLI: `python -m walle benchmark --n 100 --out outputs/benchmark`.
- **LLM comparison (optional, only if everything else is finished):** implement `LLMAgent` behind the same `Agent` protocol that sends a text summary of the state (position, battery, last observations, belief MAP/entropy) to an API and parses an action. API key via environment variable, never committed. If skipped, write one honest paragraph in the README explaining why a classical Bayesian planner was used (explainability, determinism, no API cost, guaranteed safety constraint) and mention the LLM comparison as future work.

**Acceptance criteria**
- Benchmark runs 100 missions × 3 agents in under 10 minutes.
- Aggregated table shows `bayes_planner` clearly better than the baselines on success rate and with 0% stranded.
- Results are reproducible with `--seed`.

**Antigravity prompt**
```text
Start Phase 10 (Bonus B) from PLAN.md. Implement benchmark.py and the CLI command: random mission
generator with the parameter ranges in the plan, run random / greedy_bearing / bayes_planner on identical
missions, write benchmark_results.csv, an aggregated markdown table and a bar chart. Skip the LLM agent
for now (do not add any API dependency). Run it with n=100 and show me the table. Stop.
```

---

### Phase 11 — README, documentation and packaging (≈ 1.5 h)

**Goal:** A repo a stranger can understand and run in 5 minutes.

**README.md structure (ask Antigravity to follow exactly)**
1. Title, one-paragraph pitch, GIF at the top.
2. Features checklist mapped to the task requirements (use the table in Section 1.2).
3. Quick start: install, run the easy mission, run the medium mission, view outputs, run tests, run the benchmark.
4. **Environment design:** grid, hidden state, actions and costs table, termination rules, sensor model formulas, clue types.
5. **Config format:** annotated YAML plus a link to `CONFIG_REFERENCE.md`.
6. **Agent design:** architecture diagram, belief representation, information-gain planning, safe-return invariant, strategy state machine diagram, why this approach.
7. **Trace and report format** with excerpts.
8. **Sample results:** embed `summary.png`, a short excerpt of the trace and the report, and the benchmark table.
9. **Design decisions and limitations** (fully honest: 2D grid only, static EVE unless random walk enabled, no physics simulator, etc.).
10. Future work (LLM agent comparison, multi-agent coordination, Webots/Gazebo, continuous space with particle filter).
11. Project structure and testing.

Also finalize `docs/DESIGN.md` (math of the update and the utility) and `docs/DECISIONS.md`.

**Acceptance criteria**
- A fresh clone, `pip install -r requirements.txt`, then the three README commands work exactly as written.
- All images in the README exist and render on GitHub.
- No leftover TODOs, no secrets, `outputs/` contains at least the medium and hard sample runs.

**Antigravity prompt**
```text
Start Phase 11. Write README.md following the 11-section structure in PLAN.md Phase 11, finalize
docs/DESIGN.md (belief update math and the utility function with the actual weights) and docs/DECISIONS.md.
Embed the GIF and summary.png. Then do a fresh-clone dry run: create a new venv in a temp directory,
install, and execute every command written in the README, fixing the README or the code if any command fails.
Show me the dry-run log. Stop.
```

---

### Phase 12 — Final QA and submission (≈ 1 h)

**Checklist**
- [ ] `pytest -q` is green.
- [ ] `scripts/run_all_samples.sh` regenerates `outputs/` without errors.
- [ ] Sample outputs committed: easy, medium and hard mission, each with `trace.jsonl`, `trace.txt`, `report.md`, `report.json`, `summary.png`, `run.gif`.
- [ ] README has the GIF, the commands, the config explanation and honest limitations.
- [ ] Repo is on GitHub (public, or access granted as the portal requires), with a clear commit history (at least one commit per phase).
- [ ] No API keys, no `.env`, no giant files (GIF under ~10 MB).
- [ ] Repo link, README link and a 1-minute demo video (if the portal allows) prepared.
- [ ] Submitted at least 5 hours before 11:59 PM on 15 Oct.

---

## 7. Suggested schedule (assumes about 38 hours remaining from the morning of 14 Oct)

| Block | When | Phases | Goal |
|---|---|---|---|
| A | 14 Oct, morning | 0, 1 | Skeleton, config and world working and tested |
| B | 14 Oct, afternoon | 2, 3 | Simulator and belief engine working and tested |
| C | 14 Oct, evening | 4, 5 | First complete autonomous run, even if rough |
| D | 14 Oct, night (stop at a sane hour) | 6 | Trace and report generated |
| E | 15 Oct, morning | 7, 8 | Visuals and hardening |
| F | 15 Oct, afternoon | 11, 12 (+ 9 or 10 if time remains) | README, final QA, **submit by 6 PM** |

**Cut-lines if you fall behind** (cut from the top first):
1. LLM comparison (never needed).
2. `random_walk` EVE mobility.
3. Benchmark chart polish (keep the CSV).
4. GIF (keep `summary.png` and ASCII frames).
5. Decoys (Phase 9) — only if Phase 10 is also impossible; the benchmark is the more valuable bonus.

**Never cut:** the safe-return invariant and its test, the separation test, a sample run with `trace` and `report`, the README.

---

## 8. Debugging playbook (if the agent misbehaves)

| Symptom | Likely cause | Fix |
|---|---|---|
| Belief collapses onto a wrong cell | Wrong bearing convention or sign (y axis points down) | Test `bearing()` on all compass directions; use the single helper everywhere |
| Belief never narrows | Likelihood sigmas too wide, or likelihood not applied at the agent's position at the time of the reading | Log the agent position used in each update; plot the likelihood alone |
| Agent scans in place forever | EIG of the current cell always highest | Add a repeated-scan penalty (diminishing returns: halve EIG for each scan from the same cell) |
| Agent oscillates between two cells | Utility differences smaller than noise | Plan persistence (keep a plan until a >15% better option appears) and the revisit penalty |
| Agent strands | Reserve calculated from the wrong position (before moving instead of after) | The safety check must use the position after the action |
| Agent never recharges | Reserve too low or charger cost mis-specified | Print reserve and battery per step in the text trace |
| MC EIG is noisy | Too few samples | Raise `mc_samples` to 80 or use common random numbers across candidates |
| Run is slow | Likelihoods re-computed in Python loops | Precompute coordinate grids once; vectorize; cache BFS maps |
| Declares too early or too late | Thresholds mis-tuned | Tune `declare_location` and `declare_status` using the benchmark, not by guessing |

---

## 9. Interview and viva preparation (read this before Round 2)

Be ready to explain these in plain words:

1. **What is a belief and why a grid?** A probability for every possible EVE position and status. Every sensor reading multiplies the belief by how likely that reading would be at each cell, then re-normalizes (Bayes' rule).
2. **Why does the agent move to a *different* place before scanning again?** Two bearings from different places cross at EVE (triangulation). Strength gives the distance. The expected-information-gain score captures this automatically.
3. **What is expected information gain?** The average drop in entropy (uncertainty, in bits) we expect from taking a measurement, estimated by simulating possible readings.
4. **How does the agent avoid dying out in the field?** The safe-return invariant: it only acts if after the action it still has enough battery to reach a charger, with a margin.
5. **Why did you not use reinforcement learning or an LLM?** The problem is small and structured, we need guarantees (safety, explainability, determinism), and no training data. A Bayesian planner gives interpretable traces. RL or LLM comparison is future work.
6. **How does the agent infer EVE's status?** Signal amplitude and dropout rates depend on the status, and status clues give labels. The joint belief over location and status handles the ambiguity "weak signal = far or low-power?" by using bearings and multiple viewpoints.
7. **What happens with decoy signals?** Mixture likelihood plus confirmation scans.
8. **What are the limits?** 2D grid, known map, simple noise models, static EVE by default, no physics.
9. **How do you know it works?** Unit tests, safety property test over 100 seeds, benchmark against baselines, and calibration (the truth falls inside the 90% region about 90% of the time).

Practice a 2-minute walkthrough of the GIF: initial uncertainty, the first scans, the strategy change to TRACK, the recharge detour, VERIFY, final declare, and the report.

---

## 10. Definition of done

The project is done when a reviewer can clone the repo, follow the README, run one command, and get: a belief-driven autonomous run that never strands, a complete JSONL trace with reasoning, a final mission report with evidence, inferred location and status, confidence and a recommended next step, plus a GIF showing the path, clue discoveries and strategy changes. All of that is backed by passing tests and an honest list of limitations.
