"""Observation dataclasses and public mission information for the agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class MoveCost:
    """Resource costs for a single movement step."""
    battery: int = 1
    time: int = 1


@dataclass(frozen=True)
class ScanSignalCost:
    """Resource costs for a directional signal scan."""
    battery: int = 2
    time: int = 1


@dataclass(frozen=True)
class ScanAreaCost:
    """Resource costs for an area scan covering radius r in 1..max_radius."""
    battery_base: int = 2
    battery_per_radius: int = 2
    time_base: int = 1
    time_per_radius: int = 1
    max_radius: int = 3

    def battery_cost(self, radius: int) -> int:
        return self.battery_base + self.battery_per_radius * radius

    def time_cost(self, radius: int) -> int:
        return self.time_base + self.time_per_radius * radius


@dataclass(frozen=True)
class RechargeCost:
    """Resource effects for recharging at a charging station."""
    battery_gain: int = 20
    time: int = 2


@dataclass(frozen=True)
class CostTable:
    """Complete table of resource costs for all actions."""
    move: MoveCost
    scan_signal: ScanSignalCost
    scan_area: ScanAreaCost
    recharge: RechargeCost


@dataclass(frozen=True)
class InitialSignal:
    """Prior signal observation provided at mission initialization."""
    bearing_deg: float | None
    coordinates: tuple[int, int] | None
    coordinates_sigma: float
    strength: float | None
    timestamp: int = 0


@dataclass(frozen=True)
class SensorPrior:
    """Sensor parameters assumed by the agent for inference and planning."""
    noise_scale: float
    strength_sigma: float
    bearing_sigma_base_deg: float
    bearing_sigma_per_cell_deg: float
    d0: float
    amplitude: Mapping[str, float]
    dropout: Mapping[str, float]
    clue_bearing_sigma_deg: float
    clue_range_sigma: float
    clue_status_accuracy: float
    clue_detect_probability: float
    assumed_spoof_rate: float = 0.0


@dataclass(frozen=True)
class PublicMissionInfo:
    """Mission specification visible to the autonomous agent.

    Strict separation invariant: PublicMissionInfo must NEVER contain
    hidden state such as EVE's true position/status, decoy locations,
    or undiscovered clue positions.
    """
    width: int
    height: int
    walls: frozenset[tuple[int, int]]
    chargers: tuple[tuple[int, int], ...]
    start: tuple[int, int]
    battery_capacity: int
    battery_initial: int
    time_budget: int
    costs: CostTable
    initial_signal: InitialSignal
    sensor_prior: SensorPrior


@dataclass(frozen=True)
class SignalReading:
    """Directional signal reading received from a SCAN_SIGNAL action."""
    strength: float | None
    bearing_deg: float | None
    dropout: bool
    missing_bearing_reason: str | None = None


@dataclass(frozen=True)
class ClueReading:
    """Clue measurement revealed by a SCAN_AREA action."""
    clue_id: int
    position: tuple[int, int]
    type: str  # 'bearing', 'range', 'status'
    value: float | str  # degrees (float), distance (float), or status label (str)


@dataclass(frozen=True)
class Observation:
    """Observation packet returned to the agent after each environment step."""
    step: int
    position: tuple[int, int]
    battery: int
    time_left: int
    action_succeeded: bool
    bumped: bool
    on_charger: bool
    signal: SignalReading | None
    clues: tuple[ClueReading, ...]
    done: bool
    done_reason: str | None  # 'declared' | 'stranded' | 'timeout'
