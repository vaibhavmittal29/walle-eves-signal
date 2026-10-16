"""Path planning, BFS reachability, and safe-return battery budgeting."""

from __future__ import annotations

from collections import deque
import math
from typing import Dict, List, Optional, Sequence, Set, Tuple

from walle.actions import Action, ActionType, MOVE_DELTAS, cost_of
from walle.observations import CostTable


def bfs_distances(
    source: Tuple[int, int],
    walls: Set[Tuple[int, int]] | frozenset[Tuple[int, int]],
    width: int,
    height: int,
) -> Dict[Tuple[int, int], int]:
    """Compute shortest path distance from source to all reachable cells via BFS.

    Args:
        source: Starting grid cell (x, y).
        walls: Set of wall/obstacle coordinates.
        width: Grid width.
        height: Grid height.

    Returns:
        Mapping of cell (x, y) to integer path distance.
    """
    if source in walls or not (0 <= source[0] < width and 0 <= source[1] < height):
        return {}

    distances: Dict[Tuple[int, int], int] = {source: 0}
    queue: deque[Tuple[int, int]] = deque([source])

    while queue:
        curr = queue.popleft()
        d = distances[curr]
        cx, cy = curr

        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            nx, ny = cx + dx, cy + dy
            nbr = (nx, ny)
            if 0 <= nx < width and 0 <= ny < height and nbr not in walls and nbr not in distances:
                distances[nbr] = d + 1
                queue.append(nbr)

    return distances


def shortest_path(
    source: Tuple[int, int],
    target: Tuple[int, int],
    walls: Set[Tuple[int, int]] | frozenset[Tuple[int, int]],
    width: int,
    height: int,
) -> List[Tuple[int, int]]:
    """Compute shortest 4-connected grid path from source to target.

    Args:
        source: Starting cell.
        target: Target cell.
        walls: Obstacles.
        width: Grid width.
        height: Grid height.

    Returns:
        List of coordinates [source, p1, ..., target], or empty list if unreachable.
    """
    if source == target:
        return [source]
    if source in walls or target in walls:
        return []

    parent: Dict[Tuple[int, int], Tuple[int, int]] = {}
    visited: Set[Tuple[int, int]] = {source}
    queue: deque[Tuple[int, int]] = deque([source])
    found = False

    while queue:
        curr = queue.popleft()
        if curr == target:
            found = True
            break

        cx, cy = curr
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            nx, ny = cx + dx, cy + dy
            nbr = (nx, ny)
            if 0 <= nx < width and 0 <= ny < height and nbr not in walls and nbr not in visited:
                visited.add(nbr)
                parent[nbr] = curr
                queue.append(nbr)

    if not found:
        return []

    # Reconstruct path backwards
    path = []
    curr = target
    while curr != source:
        path.append(curr)
        curr = parent[curr]
    path.append(source)
    path.reverse()
    return path


def path_to_move_action(current: Tuple[int, int], next_cell: Tuple[int, int]) -> Action:
    """Convert a single-step move between adjacent cells into an Action."""
    dx = next_cell[0] - current[0]
    dy = next_cell[1] - current[1]

    if dx == 0 and dy == -1:
        return Action(type=ActionType.MOVE_N)
    if dx == 1 and dy == 0:
        return Action(type=ActionType.MOVE_E)
    if dx == 0 and dy == 1:
        return Action(type=ActionType.MOVE_S)
    if dx == -1 and dy == 0:
        return Action(type=ActionType.MOVE_W)

    raise ValueError(f"Cells {current} and {next_cell} are not adjacent 4-connected neighbors.")


def nearest_charger(
    pos: Tuple[int, int],
    chargers: Sequence[Tuple[int, int]],
    walls: Set[Tuple[int, int]] | frozenset[Tuple[int, int]],
    width: int,
    height: int,
    charger_dist_maps: Optional[Dict[Tuple[int, int], Dict[Tuple[int, int], int]]] = None,
) -> Tuple[Tuple[int, int], int]:
    """Find the closest charging station and the shortest path distance to it.

    Args:
        pos: Current position.
        chargers: Sequence of charger locations.
        walls: Grid obstacles.
        width: Grid width.
        height: Grid height.
        charger_dist_maps: Optional precomputed BFS distance maps from each charger.

    Returns:
        Tuple of (nearest_charger_pos, distance_in_steps).
    """
    best_charger = chargers[0]
    best_dist = 999999

    for c in chargers:
        if charger_dist_maps and c in charger_dist_maps:
            dist = charger_dist_maps[c].get(pos, 999999)
        else:
            dist_map = bfs_distances(c, walls, width, height)
            dist = dist_map.get(pos, 999999)

        if dist < best_dist:
            best_dist = dist
            best_charger = c

    return best_charger, best_dist


def return_reserve(
    pos: Tuple[int, int],
    chargers: Sequence[Tuple[int, int]],
    move_battery_cost: int,
    margin_fraction: float,
    margin_flat: int,
    walls: Set[Tuple[int, int]] | frozenset[Tuple[int, int]],
    width: int,
    height: int,
    charger_dist_maps: Optional[Dict[Tuple[int, int], Dict[Tuple[int, int], int]]] = None,
) -> int:
    """Calculate the mandatory safe-return battery reserve needed at position pos.

    Formula:
        reserve = ceil(dist_to_nearest_charger * move_battery_cost * (1 + margin_fraction) + margin_flat)
    """
    _, dist = nearest_charger(pos, chargers, walls, width, height, charger_dist_maps)
    base_battery = dist * move_battery_cost
    reserve = math.ceil(base_battery * (1.0 + margin_fraction) + margin_flat)
    return reserve


def is_action_safe(
    current_battery: int,
    pos_after: Tuple[int, int],
    action_battery_cost: int,
    chargers: Sequence[Tuple[int, int]],
    move_battery_cost: int,
    margin_fraction: float,
    margin_flat: int,
    walls: Set[Tuple[int, int]] | frozenset[Tuple[int, int]],
    width: int,
    height: int,
    charger_dist_maps: Optional[Dict[Tuple[int, int], Dict[Tuple[int, int], int]]] = None,
) -> bool:
    """Evaluate the core safe-return invariant.

    Invariant:
        An action is SAFE if and only if, after paying its battery cost and arriving
        at the resulting position, the remaining battery is at least equal to the
        return reserve required at that new position:
            battery_after >= return_reserve(pos_after)
    """
    battery_after = current_battery - action_battery_cost
    if battery_after < 0:
        return False

    reserve_needed = return_reserve(
        pos=pos_after,
        chargers=chargers,
        move_battery_cost=move_battery_cost,
        margin_fraction=margin_fraction,
        margin_flat=margin_flat,
        walls=walls,
        width=width,
        height=height,
        charger_dist_maps=charger_dist_maps,
    )

    return battery_after >= reserve_needed


def check_action_safety(
    action: Action,
    current_pos: Tuple[int, int],
    current_battery: int,
    costs: CostTable,
    chargers: Sequence[Tuple[int, int]],
    walls: Set[Tuple[int, int]] | frozenset[Tuple[int, int]],
    width: int,
    height: int,
    margin_fraction: float,
    margin_flat: int,
    charger_dist_maps: Optional[Dict[Tuple[int, int], Dict[Tuple[int, int], int]]] = None,
) -> Tuple[bool, Tuple[int, int], int, int]:
    """Verify safe-return invariant for an action before execution.

    Args:
        action: The candidate action to execute.
        current_pos: Current agent grid coordinates (x, y).
        current_battery: Current agent battery level.
        costs: Mission cost table.
        chargers: Sequence of charger coordinates.
        walls: Set or frozenset of obstacle coordinates.
        width: Grid width.
        height: Grid height.
        margin_fraction: Fractional safety margin on movement.
        margin_flat: Flat battery reserve buffer.
        charger_dist_maps: Optional precomputed distance maps from chargers.

    Returns:
        Tuple of (is_safe, pos_after, battery_after, reserve_needed_at_pos_after).
    """
    if action.type == ActionType.DECLARE:
        res = return_reserve(
            pos=current_pos,
            chargers=chargers,
            move_battery_cost=costs.move.battery,
            margin_fraction=margin_fraction,
            margin_flat=margin_flat,
            walls=walls,
            width=width,
            height=height,
            charger_dist_maps=charger_dist_maps,
        )
        return True, current_pos, current_battery, res

    if action.type == ActionType.RECHARGE:
        res = return_reserve(
            pos=current_pos,
            chargers=chargers,
            move_battery_cost=costs.move.battery,
            margin_fraction=margin_fraction,
            margin_flat=margin_flat,
            walls=walls,
            width=width,
            height=height,
            charger_dist_maps=charger_dist_maps,
        )
        if current_pos in chargers:
            return True, current_pos, current_battery, res
        return current_battery >= res, current_pos, current_battery, res

    b_cost = cost_of(action, costs)[0]
    pos_after = current_pos
    if action.type in MOVE_DELTAS:
        dx, dy = MOVE_DELTAS[action.type]
        cand_pos = (current_pos[0] + dx, current_pos[1] + dy)
        if 0 <= cand_pos[0] < width and 0 <= cand_pos[1] < height and cand_pos not in walls:
            pos_after = cand_pos

    battery_after = current_battery - b_cost
    res_after = return_reserve(
        pos=pos_after,
        chargers=chargers,
        move_battery_cost=costs.move.battery,
        margin_fraction=margin_fraction,
        margin_flat=margin_flat,
        walls=walls,
        width=width,
        height=height,
        charger_dist_maps=charger_dist_maps,
    )

    if battery_after < 0:
        return False, pos_after, battery_after, res_after

    is_safe = (battery_after >= res_after)
    return is_safe, pos_after, battery_after, res_after
