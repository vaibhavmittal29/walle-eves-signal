"""Baseline agents for benchmark comparison: RandomAgent and GreedyBearingAgent."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple
import numpy as np

from walle.actions import Action, ActionType, MOVE_DELTAS, cost_of
from walle.agent import CandidateScore, Decision
from walle.geometry import distance, wrap_angle
from walle.observations import Observation, PublicMissionInfo
from walle.planner import (
    bfs_distances,
    is_action_safe,
    nearest_charger,
    path_to_move_action,
    return_reserve,
    shortest_path,
)


class RandomAgent:
    """Baseline agent performing random exploration while adhering to safe-return battery limits."""

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._rng = np.random.default_rng(seed)
        self._info: Optional[PublicMissionInfo] = None
        self._step = 0
        self._last_bearing: Optional[float] = None
        self._charger_dist_maps: Dict[Tuple[int, int], Dict[Tuple[int, int], int]] = {}

    def reset(self, info: PublicMissionInfo) -> None:
        self._info = info
        self._rng = np.random.default_rng(self._seed)
        self._step = 0
        self._last_bearing = info.initial_signal.bearing_deg
        self._charger_dist_maps = {
            c: bfs_distances(c, info.walls, info.width, info.height)
            for c in info.chargers
        }

    def act(self, obs: Observation) -> Tuple[Action, Decision]:
        if self._info is None:
            raise RuntimeError("Agent not reset.")
        self._step += 1
        pos = obs.position

        if obs.signal and obs.signal.bearing_deg is not None:
            self._last_bearing = obs.signal.bearing_deg

        # Calculate return reserve
        res = return_reserve(
            pos, self._info.chargers, self._info.costs.move.battery,
            0.10, 3, self._info.walls, self._info.width, self._info.height,
            self._charger_dist_maps,
        )

        # 1. Recharge if on charger and low battery
        if obs.on_charger and obs.battery < 80:
            act = Action(type=ActionType.RECHARGE)
            return act, Decision(act, ["RECHARGE"], [], "Recharging on charger.")

        # 2. Return if battery near reserve
        if obs.battery <= res + 2:
            best_c, _ = nearest_charger(pos, self._info.chargers, self._info.walls, self._info.width, self._info.height, self._charger_dist_maps)
            path = shortest_path(pos, best_c, self._info.walls, self._info.width, self._info.height)
            if len(path) > 1:
                act = path_to_move_action(pos, path[1])
                return act, Decision(act, ["RETURN"], [], "Returning to charger.")
            elif obs.on_charger:
                act = Action(type=ActionType.RECHARGE)
                return act, Decision(act, ["RECHARGE"], [], "At charger, recharging.")

        # 3. Declare when time is running low or randomly after step 80
        if obs.time_left <= 10 or self._step >= 80:
            dec_x = max(0, min(self._info.width - 1, pos[0] + 3))
            dec_y = max(0, min(self._info.height - 1, pos[1] + 3))
            act = Action(type=ActionType.DECLARE, declare_x=dec_x, declare_y=dec_y, declare_status="active")
            return act, Decision(act, ["DECLARE"], [], "Random baseline declaration.")

        # 4. Scan periodically every 5 steps
        if self._step % 5 == 0:
            act = Action(type=ActionType.SCAN_SIGNAL)
            if is_action_safe(obs.battery, pos, 2, self._info.chargers, self._info.costs.move.battery, 0.10, 3, self._info.walls, self._info.width, self._info.height, self._charger_dist_maps):
                return act, Decision(act, ["SCAN_SIGNAL"], [], "Periodic random scan.")

        # 5. Move in random safe direction
        safe_moves = []
        for m_type, (dx, dy) in MOVE_DELTAS.items():
            target = (pos[0] + dx, pos[1] + dy)
            if 0 <= target[0] < self._info.width and 0 <= target[1] < self._info.height and target not in self._info.walls:
                if is_action_safe(obs.battery, target, 1, self._info.chargers, self._info.costs.move.battery, 0.10, 3, self._info.walls, self._info.width, self._info.height, self._charger_dist_maps):
                    safe_moves.append(Action(type=m_type))

        if safe_moves:
            chosen = self._rng.choice(safe_moves)
            return chosen, Decision(chosen, [chosen.type.value], [], "Random safe move.")

        # Fallback to nearest charger
        best_c, _ = nearest_charger(pos, self._info.chargers, self._info.walls, self._info.width, self._info.height, self._charger_dist_maps)
        path = shortest_path(pos, best_c, self._info.walls, self._info.width, self._info.height)
        if len(path) > 1:
            act = path_to_move_action(pos, path[1])
            return act, Decision(act, ["RETURN"], [], "Fallback return.")

        act = Action(type=ActionType.SCAN_SIGNAL)
        return act, Decision(act, ["WAIT"], [], "Wait in place.")


class GreedyBearingAgent:
    """Baseline agent following measured bearings greedily towards the target."""

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._rng = np.random.default_rng(seed)
        self._info: Optional[PublicMissionInfo] = None
        self._step = 0
        self._last_bearing: Optional[float] = None
        self._last_strength: Optional[float] = None
        self._charger_dist_maps: Dict[Tuple[int, int], Dict[Tuple[int, int], int]] = {}

    def reset(self, info: PublicMissionInfo) -> None:
        self._info = info
        self._rng = np.random.default_rng(self._seed)
        self._step = 0
        self._last_bearing = info.initial_signal.bearing_deg
        self._last_strength = info.initial_signal.strength
        self._charger_dist_maps = {
            c: bfs_distances(c, info.walls, info.width, info.height)
            for c in info.chargers
        }

    def act(self, obs: Observation) -> Tuple[Action, Decision]:
        if self._info is None:
            raise RuntimeError("Agent not reset.")
        self._step += 1
        pos = obs.position

        if obs.signal:
            if obs.signal.bearing_deg is not None:
                self._last_bearing = obs.signal.bearing_deg
            if obs.signal.strength is not None:
                self._last_strength = obs.signal.strength

        # Safety reserve check
        res = return_reserve(
            pos, self._info.chargers, self._info.costs.move.battery,
            0.10, 3, self._info.walls, self._info.width, self._info.height,
            self._charger_dist_maps,
        )

        if obs.on_charger and obs.battery < 80:
            act = Action(type=ActionType.RECHARGE)
            return act, Decision(act, ["RECHARGE"], [], "Greedy recharging on charger.")

        if obs.battery <= res + 2:
            best_c, _ = nearest_charger(pos, self._info.chargers, self._info.walls, self._info.width, self._info.height, self._charger_dist_maps)
            path = shortest_path(pos, best_c, self._info.walls, self._info.width, self._info.height)
            if len(path) > 1:
                act = path_to_move_action(pos, path[1])
                return act, Decision(act, ["RETURN"], [], "Greedy safe return.")
            elif obs.on_charger:
                act = Action(type=ActionType.RECHARGE)
                return act, Decision(act, ["RECHARGE"], [], "At charger, recharging.")

        # Declare condition: strong signal (>0.80) or timeout imminent
        if (self._last_strength and self._last_strength > 0.80) or obs.time_left <= 8:
            act = Action(type=ActionType.DECLARE, declare_x=pos[0], declare_y=pos[1], declare_status="active")
            return act, Decision(act, ["DECLARE"], [], f"Greedy declare at {pos}.")

        # Scan every 3 steps to update bearing
        if self._step % 3 == 0:
            act = Action(type=ActionType.SCAN_SIGNAL)
            if is_action_safe(obs.battery, pos, 2, self._info.chargers, self._info.costs.move.battery, 0.10, 3, self._info.walls, self._info.width, self._info.height, self._charger_dist_maps):
                return act, Decision(act, ["SCAN_SIGNAL"], [], "Greedy signal sweep.")

        # Choose move action best aligned with last measured compass bearing
        if self._last_bearing is not None:
            best_action = None
            min_ang_diff = 999.0
            for m_type, (dx, dy) in MOVE_DELTAS.items():
                target = (pos[0] + dx, pos[1] + dy)
                if 0 <= target[0] < self._info.width and 0 <= target[1] < self._info.height and target not in self._info.walls:
                    if is_action_safe(obs.battery, target, 1, self._info.chargers, self._info.costs.move.battery, 0.10, 3, self._info.walls, self._info.width, self._info.height, self._charger_dist_maps):
                        # Angle of this move: 0 North, 90 East, 180 South, 270 West
                        # atan2(dx, -dy) mod 360
                        move_bearing = math.degrees(math.atan2(dx, -dy)) % 360.0
                        diff = abs(wrap_angle(move_bearing - self._last_bearing))
                        if diff < min_ang_diff:
                            min_ang_diff = diff
                            best_action = Action(type=m_type)

            if best_action is not None:
                return best_action, Decision(best_action, [best_action.type.value], [], f"Greedy move aligned with bearing {self._last_bearing:.1f} deg.")

        # Fallback
        act = Action(type=ActionType.SCAN_SIGNAL)
        return act, Decision(act, ["SCAN_SIGNAL"], [], "Greedy default scan.")
