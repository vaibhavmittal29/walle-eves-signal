"""Action definitions and resource cost calculations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from walle.observations import CostTable


class ActionType(str, Enum):
    """Enumeration of possible agent actions."""
    MOVE_N = "MOVE_N"
    MOVE_E = "MOVE_E"
    MOVE_S = "MOVE_S"
    MOVE_W = "MOVE_W"
    SCAN_SIGNAL = "SCAN_SIGNAL"
    SCAN_AREA = "SCAN_AREA"
    RECHARGE = "RECHARGE"
    DECLARE = "DECLARE"


# Delta mappings for 4-connected grid movement: (dx, dy) where y increases downward
MOVE_DELTAS: dict[ActionType, Tuple[int, int]] = {
    ActionType.MOVE_N: (0, -1),
    ActionType.MOVE_E: (1, 0),
    ActionType.MOVE_S: (0, 1),
    ActionType.MOVE_W: (-1, 0),
}


@dataclass(frozen=True)
class Action:
    """Action requested by the agent."""
    type: ActionType
    radius: int = 1  # Used by SCAN_AREA (1, 2, or 3)
    declare_x: Optional[int] = None
    declare_y: Optional[int] = None
    declare_status: Optional[str] = None  # 'active', 'low_power', or 'damaged'

    def __post_init__(self) -> None:
        if self.type == ActionType.SCAN_AREA and not (1 <= self.radius <= 3):
            raise ValueError(f"SCAN_AREA radius must be in 1..3, got {self.radius}")
        if self.type == ActionType.DECLARE:
            if self.declare_x is None or self.declare_y is None or self.declare_status is None:
                raise ValueError("DECLARE action requires declare_x, declare_y, and declare_status")


def cost_of(action: Action, costs: CostTable) -> Tuple[int, int]:
    """Calculate resource costs (battery_cost, time_cost) for an action.

    Args:
        action: The action to evaluate.
        costs: The mission's cost table.

    Returns:
        Tuple of (battery_cost, time_cost).
    """
    if action.type in MOVE_DELTAS:
        return (costs.move.battery, costs.move.time)

    if action.type == ActionType.SCAN_SIGNAL:
        return (costs.scan_signal.battery, costs.scan_signal.time)

    if action.type == ActionType.SCAN_AREA:
        r = max(1, min(action.radius, costs.scan_area.max_radius))
        return (costs.scan_area.battery_cost(r), costs.scan_area.time_cost(r))

    if action.type == ActionType.RECHARGE:
        # Recharging consumes 0 battery (it replenishes), but consumes time
        return (0, costs.recharge.time)

    if action.type == ActionType.DECLARE:
        return (0, 1)

    return (0, 0)
