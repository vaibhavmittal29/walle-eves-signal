"""World generation, map connectivity validation, and ground-truth representation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Sequence, Set, Tuple
import numpy as np

from walle.config import AppConfig, ConfigError
from walle.geometry import bearing, distance
from walle.observations import InitialSignal, PublicMissionInfo, SignalReading


@dataclass(frozen=True)
class TrueClue:
    """Hidden ground truth for a clue object."""
    clue_id: int
    position: Tuple[int, int]
    clue_type: Literal["bearing", "range", "status"]
    ground_truth_value: Any  # exact bearing, exact range, or true status


@dataclass(frozen=True)
class GroundTruth:
    """Complete ground truth state.

    Strict separation: this dataclass is private to the simulation environment
    and runner for metrics/debug only. It must NEVER be passed to the agent.
    """
    eve_location: Tuple[int, int]
    eve_status: Literal["active", "low_power", "damaged"]
    clues: Tuple[TrueClue, ...]
    decoys: Tuple[Tuple[int, int], ...]


def _get_neighbors(x: int, y: int, width: int, height: int) -> List[Tuple[int, int]]:
    """4-connected neighbors within bounds."""
    nbrs = []
    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < width and 0 <= ny < height:
            nbrs.append((nx, ny))
    return nbrs


def check_connectivity(
    start: Tuple[int, int],
    walls: Set[Tuple[int, int]],
    width: int,
    height: int,
) -> Tuple[bool, Set[Tuple[int, int]]]:
    """Perform BFS reachability from start over free cells.

    Returns:
        (is_fully_connected, reachable_cells_set)
    """
    if start in walls:
        return False, set()

    visited: Set[Tuple[int, int]] = {start}
    queue: deque[Tuple[int, int]] = deque([start])

    while queue:
        curr = queue.popleft()
        for nx, ny in _get_neighbors(curr[0], curr[1], width, height):
            nbr = (nx, ny)
            if nbr not in walls and nbr not in visited:
                visited.add(nbr)
                queue.append(nbr)

    total_free = width * height - len(walls)
    is_fully_connected = len(visited) == total_free
    return is_fully_connected, visited


class World:
    """Simulated world holding grid geometry and hidden ground-truth state."""

    def __init__(self, config: AppConfig):
        self._config = config
        self._width = config.mission.grid.width
        self._height = config.mission.grid.height
        self._start = config.mission.start

        # Separate RNG for environment world generation
        self._rng = np.random.default_rng(config.mission.seed)

        # 1. Generate walls and ensure connectivity
        self._walls, self._reachable_cells = self._generate_obstacles()

        # 2. Setup chargers
        self._chargers = self._setup_chargers()

        # 3. Place EVE and determine status
        self._eve_location, self._eve_status = self._place_eve()

        # 4. Place clues
        self._clues = self._place_clues()

        # 5. Place decoys
        self._decoys = self._place_decoys()

        # 6. Initialize initial signal and reading
        self._initial_signal, self._initial_signal_reading = self._create_initial_signal()

    def _create_initial_signal(self) -> Tuple[InitialSignal, Optional[SignalReading]]:
        """Create initial signal specification and sensor reading based on mode."""
        init_cfg = self._config.initial_signal
        if init_cfg.mode == "none":
            return InitialSignal(), None
        elif init_cfg.mode == "configured":
            init_sig = InitialSignal(
                bearing_deg=init_cfg.bearing_deg,
                coordinates=init_cfg.coordinates,
                coordinates_sigma=init_cfg.coordinates_sigma,
                strength=init_cfg.strength,
                timestamp=init_cfg.timestamp,
            )
            if init_cfg.bearing_deg is not None or init_cfg.strength is not None:
                reading = SignalReading(
                    strength=init_cfg.strength,
                    bearing_deg=init_cfg.bearing_deg,
                    dropout=False,
                    missing_bearing_reason=None if init_cfg.bearing_deg is not None else "not_provided",
                )
            else:
                reading = None
            return init_sig, reading
        else:
            # "generated" mode: samples initial observation ONCE at reset from actual target position and status
            from walle.signal_model import sample_signal
            sig = sample_signal(
                agent_pos=self._start,
                eve_pos=self._eve_location,
                eve_status=self._eve_status,
                sensor=self._config.sensor,
                rng=np.random.default_rng(self._config.mission.seed + 555),
                decoys=self._decoys,
            )
            init_sig = InitialSignal(
                bearing_deg=sig.bearing_deg,
                coordinates=None,
                coordinates_sigma=4.0,
                strength=sig.strength,
                timestamp=0,
            )
            return init_sig, sig

    def initial_signal_reading(self) -> Optional[SignalReading]:
        """Return the initial sensor observation generated for mission start."""
        return self._initial_signal_reading

    def _generate_obstacles(self) -> Tuple[frozenset[Tuple[int, int]], Set[Tuple[int, int]]]:
        """Generate obstacle set and verify full connectivity."""
        mode = self._config.mission.obstacles.mode
        w, h = self._width, self._height
        start = self._start

        if mode == "explicit":
            walls = set(self._config.mission.obstacles.explicit)
            connected, reachable = check_connectivity(start, walls, w, h)
            if not connected:
                raise ConfigError(f"Explicit map is not fully connected from start {start}.")
            return frozenset(walls), reachable

        if mode == "ascii":
            walls = set()
            ascii_rows = self._config.mission.obstacles.ascii
            if len(ascii_rows) != h:
                raise ConfigError(f"ASCII map row count ({len(ascii_rows)}) != height ({h}).")
            for y, row in enumerate(ascii_rows):
                if len(row) != w:
                    raise ConfigError(f"ASCII map row {y} length ({len(row)}) != width ({w}).")
                for x, char in enumerate(row):
                    if char == "#":
                        walls.add((x, y))
            connected, reachable = check_connectivity(start, walls, w, h)
            if not connected:
                raise ConfigError(f"ASCII map is not fully connected from start {start}.")
            return frozenset(walls), reachable

        # Random mode: retry with derived seeds up to 50 times
        density = self._config.mission.obstacles.density
        chargers_set = set(self._config.mission.chargers)

        for attempt in range(50):
            attempt_seed = self._config.mission.seed + attempt * 10007
            rng = np.random.default_rng(attempt_seed)
            candidate_walls: Set[Tuple[int, int]] = set()

            for y in range(h):
                for x in range(w):
                    cell = (x, y)
                    if cell == start or cell in chargers_set:
                        continue
                    if rng.random() < density:
                        candidate_walls.add(cell)

            connected, reachable = check_connectivity(start, candidate_walls, w, h)
            if connected:
                return frozenset(candidate_walls), reachable

        raise ConfigError(
            f"Failed to generate fully connected map after 50 attempts with density {density}."
        )

    def _setup_chargers(self) -> Tuple[Tuple[int, int], ...]:
        """Validate and finalize charger locations."""
        chargers = list(self._config.mission.chargers)
        # Ensure start is included if not already present
        if self._start not in chargers:
            chargers.insert(0, self._start)

        for c in chargers:
            if c in self._walls:
                raise ConfigError(f"Charger at {c} cannot be placed inside a wall.")
            if c not in self._reachable_cells:
                raise ConfigError(f"Charger at {c} is unreachable from start.")

        return tuple(chargers)

    def _place_eve(self) -> Tuple[Tuple[int, int], Literal["active", "low_power", "damaged"]]:
        """Place EVE on a free reachable cell and assign her status."""
        eve_cfg = self._config.mission.eve

        # Location
        if eve_cfg.location != "random":
            loc = (int(eve_cfg.location[0]), int(eve_cfg.location[1]))
            if loc in self._walls:
                raise ConfigError(f"EVE location {loc} cannot be in a wall.")
            if loc not in self._reachable_cells:
                raise ConfigError(f"EVE location {loc} is not reachable from start.")
            eve_loc = loc
        else:
            # Filter reachable cells by minimum distance from start
            min_dist = eve_cfg.min_distance_from_start
            candidates = [
                cell for cell in self._reachable_cells
                if cell != self._start and cell not in self._chargers
                and distance(self._start, cell) >= min_dist
            ]
            if not candidates:
                # Fallback: furthest reachable cells
                sorted_by_dist = sorted(
                    [c for c in self._reachable_cells if c != self._start],
                    key=lambda c: distance(self._start, c),
                    reverse=True,
                )
                candidates = sorted_by_dist[: max(1, len(sorted_by_dist) // 4)]

            idx = self._rng.integers(0, len(candidates))
            eve_loc = candidates[idx]

        # Status
        if eve_cfg.status in ("active", "low_power", "damaged"):
            eve_status = eve_cfg.status
        else:
            statuses: List[Literal["active", "low_power", "damaged"]] = ["active", "low_power", "damaged"]
            eve_status = statuses[self._rng.integers(0, len(statuses))]

        return eve_loc, eve_status

    def _place_clues(self) -> Tuple[TrueClue, ...]:
        """Place clues on free reachable cells and precalculate ground truth."""
        clue_cfg = self._config.mission.clues
        count = clue_cfg.count
        if count == 0:
            return ()

        # Clue type mix
        type_keys = ["bearing", "range", "status"]
        type_probs = [clue_cfg.type_mix[k] for k in type_keys]

        # Select candidate positions
        forbidden = {self._start, self._eve_location, *self._chargers}
        candidate_cells = [c for c in self._reachable_cells if c not in forbidden]

        if clue_cfg.placement == "explicit":
            clues = []
            for idx, c_dict in enumerate(clue_cfg.explicit):
                pos = tuple(c_dict["pos"])
                c_type = c_dict["type"]
                gt_val = self._compute_clue_gt(pos, c_type)
                clues.append(TrueClue(clue_id=idx, position=pos, clue_type=c_type, ground_truth_value=gt_val))
            return tuple(clues)

        # Random placement
        self._rng.shuffle(candidate_cells)
        placed_cells = candidate_cells[: min(count, len(candidate_cells))]

        clues = []
        for idx, pos in enumerate(placed_cells):
            c_type = self._rng.choice(type_keys, p=type_probs)
            gt_val = self._compute_clue_gt(pos, c_type)
            clues.append(
                TrueClue(
                    clue_id=idx,
                    position=pos,
                    clue_type=c_type,
                    ground_truth_value=gt_val,
                )
            )

        return tuple(clues)

    def _compute_clue_gt(self, pos: Tuple[int, int], c_type: str) -> Any:
        """Compute exact ground-truth value for a clue at a given location."""
        if c_type == "bearing":
            return bearing(pos, self._eve_location)
        if c_type == "range":
            return distance(pos, self._eve_location)
        if c_type == "status":
            return self._eve_status
        raise ValueError(f"Unknown clue type '{c_type}'.")

    def _place_decoys(self) -> Tuple[Tuple[int, int], ...]:
        """Place decoy transmitters for spoofing simulations."""
        decoy_count = self._config.sensor.decoys.count
        if decoy_count == 0:
            return ()

        forbidden = {self._start, self._eve_location, *self._chargers}
        candidates = [c for c in self._reachable_cells if c not in forbidden]
        self._rng.shuffle(candidates)
        return tuple(candidates[: min(decoy_count, len(candidates))])

    def public_info(self) -> PublicMissionInfo:
        """Return public mission information visible to the agent.

        Strict separation guarantee: NO private fields (EVE position/status,
        clues, decoys) are leaked here.
        """
        sensor_prior = self._config.sensor.to_sensor_prior(
            assumed_spoof_rate=self._config.agent.assumed_spoof_rate
        )

        return PublicMissionInfo(
            width=self._width,
            height=self._height,
            walls=self._walls,
            chargers=self._chargers,
            start=self._start,
            battery_capacity=self._config.resources.battery_capacity,
            battery_initial=self._config.resources.battery_initial,
            time_budget=self._config.resources.time_budget,
            costs=self._config.resources.costs.to_cost_table(),
            initial_signal=self._initial_signal,
            sensor_prior=sensor_prior,
        )

    def ground_truth(self) -> GroundTruth:
        """Return ground truth state for simulation/testing/reporting only.

        WARNING: NEVER pass this or its return value to the agent.
        """
        return GroundTruth(
            eve_location=self._eve_location,
            eve_status=self._eve_status,
            clues=self._clues,
            decoys=self._decoys,
        )

    def render_ascii_debug(self) -> str:
        """Render debug ASCII map showing walls, chargers, start, EVE, and clues."""
        lines = []
        clue_positions = {c.position: c.clue_type[0].upper() for c in self._clues}
        charger_set = set(self._chargers)

        border = "+" + "-" * self._width + "+"
        lines.append(border)

        for y in range(self._height):
            row_chars = []
            for x in range(self._width):
                pos = (x, y)
                if pos in self._walls:
                    row_chars.append("#")
                elif pos == self._eve_location:
                    row_chars.append("E")
                elif pos == self._start:
                    row_chars.append("S")
                elif pos in charger_set:
                    row_chars.append("C")
                elif pos in clue_positions:
                    row_chars.append("!")
                elif pos in self._decoys:
                    row_chars.append("D")
                else:
                    row_chars.append(".")
            lines.append("|" + "".join(row_chars) + "|")

        lines.append(border)
        legend = "Legend: S=Start, E=EVE, C=Charger, !=Clue, D=Decoy, #=Wall, .=Free"
        lines.append(legend)
        lines.append(
            f"EVE Ground Truth: position={self._eve_location}, status={self._eve_status}, clues={len(self._clues)}"
        )
        return "\n".join(lines)
