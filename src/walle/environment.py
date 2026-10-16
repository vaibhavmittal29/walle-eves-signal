"""Simulated grid-world environment and step execution."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple
import numpy as np

from walle.actions import Action, ActionType, MOVE_DELTAS, cost_of
from walle.config import AppConfig
from walle.geometry import distance
from walle.observations import (
    ClueReading,
    Observation,
    PublicMissionInfo,
    SignalReading,
)
from walle.signal_model import sample_clue_value, sample_signal
from walle.world import GroundTruth, TrueClue, World


class Environment:
    """Simulated search environment managing physics, sensors, and resources."""

    def __init__(self, config: AppConfig):
        self._config = config
        self._world = World(config)
        self._costs = config.resources.costs.to_cost_table()

        # Determinism: separate RNG for observation sampling
        self._rng = np.random.default_rng(config.mission.seed + 1000)

        # Environment dynamics state
        self._position: Tuple[int, int] = self._world._start
        self._battery: int = self._config.resources.battery_initial
        self._time_left: int = self._config.resources.time_budget
        self._step_count: int = 0
        self._done: bool = False
        self._done_reason: Optional[str] = None

        # Revealed clues memory: clue_id -> ClueReading
        self._revealed_clues: Dict[int, ClueReading] = {}

    def reset(self) -> Tuple[PublicMissionInfo, Observation]:
        """Reset environment to initial mission state and return initial observation."""
        self._world = World(self._config)
        self._rng = np.random.default_rng(self._config.mission.seed + 1000)

        self._position = self._world._start
        self._battery = self._config.resources.battery_initial
        self._time_left = self._config.resources.time_budget
        self._step_count = 0
        self._done = False
        self._done_reason = None
        self._revealed_clues.clear()

        # Public mission info and initial signal reading at step 0
        pub_info = self._world.public_info()
        initial_signal_reading = self._world.initial_signal_reading()

        initial_obs = Observation(
            step=0,
            position=self._position,
            battery=self._battery,
            time_left=self._time_left,
            action_succeeded=True,
            bumped=False,
            on_charger=(self._position in self._world._chargers),
            signal=initial_signal_reading,
            clues=(),
            done=False,
            done_reason=None,
        )

        return pub_info, initial_obs

    def step(self, action: Action) -> Observation:
        """Execute one action, update resources and environment state, and return observation."""
        if self._done:
            return Observation(
                step=self._step_count,
                position=self._position,
                battery=self._battery,
                time_left=self._time_left,
                action_succeeded=False,
                bumped=False,
                on_charger=(self._position in self._world._chargers),
                signal=None,
                clues=(),
                done=True,
                done_reason=self._done_reason,
            )

        self._step_count += 1
        b_cost, t_cost = cost_of(action, self._costs)

        # Deduct time
        self._time_left = max(0, self._time_left - t_cost)

        action_succeeded = True
        bumped = False
        signal_obs: Optional[SignalReading] = None
        clues_obs: List[ClueReading] = []

        # 1. MOVE Actions
        if action.type in MOVE_DELTAS:
            self._battery = max(0, self._battery - b_cost)
            dx, dy = MOVE_DELTAS[action.type]
            target = (self._position[0] + dx, self._position[1] + dy)

            # Check bounds and walls
            in_bounds = (0 <= target[0] < self._world._width and 0 <= target[1] < self._world._height)
            if in_bounds and target not in self._world._walls:
                self._position = target
                bumped = False
                action_succeeded = True
            else:
                bumped = True
                action_succeeded = False

        # 2. SCAN_SIGNAL Action
        elif action.type == ActionType.SCAN_SIGNAL:
            self._battery = max(0, self._battery - b_cost)
            signal_obs = sample_signal(
                agent_pos=self._position,
                eve_pos=self._world._eve_location,
                eve_status=self._world._eve_status,
                sensor=self._config.sensor,
                rng=self._rng,
                decoys=self._world._decoys,
            )

        # 3. SCAN_AREA Action
        elif action.type == ActionType.SCAN_AREA:
            self._battery = max(0, self._battery - b_cost)
            radius = max(1, min(action.radius, self._costs.scan_area.max_radius))
            p_detect = self._config.sensor.clue_noise.detect_probability

            for clue in self._world._clues:
                d = distance(self._position, clue.position)
                if d <= float(radius):
                    # If previously revealed, return remembered clue
                    if clue.clue_id in self._revealed_clues:
                        clues_obs.append(self._revealed_clues[clue.clue_id])
                    else:
                        # Detection roll
                        if self._rng.random() < p_detect:
                            val = sample_clue_value(
                                clue_pos=clue.position,
                                eve_pos=self._world._eve_location,
                                eve_status=self._world._eve_status,
                                clue_type=clue.clue_type,
                                sensor=self._config.sensor,
                                rng=self._rng,
                            )
                            reading = ClueReading(
                                clue_id=clue.clue_id,
                                position=clue.position,
                                type=clue.clue_type,
                                value=val,
                            )
                            self._revealed_clues[clue.clue_id] = reading
                            clues_obs.append(reading)

        # 4. RECHARGE Action
        elif action.type == ActionType.RECHARGE:
            if self._position in self._world._chargers:
                gain = self._costs.recharge.battery_gain
                self._battery = min(self._config.resources.battery_capacity, self._battery + gain)
                action_succeeded = True
            else:
                action_succeeded = False

        # 5. DECLARE Action
        elif action.type == ActionType.DECLARE:
            self._done = True
            self._done_reason = "declared"

        # Check termination conditions
        if not self._done:
            # Target mobility movement
            if self._config.mission.eve.mobility == "random_walk":
                ex, ey = self._world._eve_location
                nbrs = [(ex + dx, ey + dy) for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))]
                valid_nbrs = [
                    n for n in nbrs
                    if 0 <= n[0] < self._world._width and 0 <= n[1] < self._world._height
                    and n not in self._world._walls
                ]
                if valid_nbrs and self._rng.random() < 0.5:
                    idx = int(self._rng.integers(0, len(valid_nbrs)))
                    self._world._eve_location = valid_nbrs[idx]
            elif self._config.mission.eve.mobility == "diffusion":
                ex, ey = self._world._eve_location
                sig = self._config.mission.eve.diffusion_sigma
                R = max(1, int(math.ceil(3.0 * sig)))
                candidates = []
                weights = []
                for dy in range(-R, R + 1):
                    for dx in range(-R, R + 1):
                        nx, ny = ex + dx, ey + dy
                        if (
                            0 <= nx < self._world._width
                            and 0 <= ny < self._world._height
                            and (nx, ny) not in self._world._walls
                        ):
                            w = math.exp(-0.5 * (dx * dx + dy * dy) / (sig * sig))
                            candidates.append((nx, ny))
                            weights.append(w)
                if candidates:
                    probs = np.array(weights, dtype=np.float64)
                    probs /= np.sum(probs)
                    chosen_idx = int(self._rng.choice(len(candidates), p=probs))
                    self._world._eve_location = candidates[chosen_idx]

            # Stranded: 0 battery away from any charger
            if self._battery <= 0 and self._position not in self._world._chargers:
                self._done = True
                self._done_reason = "stranded"
            # Timeout: time budget exhausted
            elif self._time_left <= 0:
                self._done = True
                self._done_reason = "timeout"
            # Max steps ceiling
            elif self._step_count >= 2 * self._config.resources.time_budget:
                self._done = True
                self._done_reason = "timeout"

        return Observation(
            step=self._step_count,
            position=self._position,
            battery=self._battery,
            time_left=self._time_left,
            action_succeeded=action_succeeded,
            bumped=bumped,
            on_charger=(self._position in self._world._chargers),
            signal=signal_obs,
            clues=tuple(clues_obs),
            done=self._done,
            done_reason=self._done_reason,
        )

    def ground_truth(self) -> GroundTruth:
        """Expose ground truth for runner/scoring only. Never pass to agent."""
        return self._world.ground_truth()
