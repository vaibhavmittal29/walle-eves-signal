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
...
