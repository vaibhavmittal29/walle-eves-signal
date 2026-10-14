"""Unit tests for simulated environment dynamics, resource costs, and edge cases."""

from pathlib import Path
import pytest

from walle.actions import Action, ActionType
from walle.config import load_config
from walle.environment import Environment


def test_wall_bump_costs_resources_and_prevents_move():
    """Moving into an obstacle/boundary costs battery & time, sets bumped=True, keeps position."""
    cfg = load_config(Path("configs/mission_easy.yaml"))
    env = Environment(cfg)
    _, obs = env.reset()

    # Move north from (1, 1) to (1, 0), then north into boundary (1, -1)
    obs = env.step(Action(type=ActionType.MOVE_N))
    assert obs.position == (1, 0)
    battery_before = obs.battery
    time_before = obs.time_left

    # Now step north into boundary
    bump_obs = env.step(Action(type=ActionType.MOVE_N))
    assert bump_obs.bumped is True
    assert bump_obs.action_succeeded is False
    assert bump_obs.position == (1, 0)  # Unchanged
    assert bump_obs.battery == battery_before - 1
    assert bump_obs.time_left == time_before - 1


def test_recharge_rules():
    """Recharge only works on charger stations."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    env = Environment(cfg)
    _, obs = env.reset()

    # Start cell (2, 2) is a charger station
    assert obs.on_charger is True

    # Waste some battery with a scan
    obs = env.step(Action(type=ActionType.SCAN_SIGNAL))
    assert obs.battery < 100

    # Recharge on charger
    bat_before = obs.battery
    obs = env.step(Action(type=ActionType.RECHARGE))
    assert obs.action_succeeded is True
    assert obs.battery == min(100, bat_before + 20)

    # Move off charger
    obs = env.step(Action(type=ActionType.MOVE_E))
    assert obs.on_charger is False
    bat_off = obs.battery
    time_off = obs.time_left

    # Recharge off charger fails
    obs = env.step(Action(type=ActionType.RECHARGE))
    assert obs.action_succeeded is False
    assert obs.battery == bat_off  # No battery gained
    assert obs.time_left == time_off - 2  # Time still spent


def test_clue_scan_radius_and_caching():
    """Clue beyond scan radius is never revealed; inside is revealed and cached."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    env = Environment(cfg)
    _, obs = env.reset()
    gt = env.ground_truth()

    # Locate a clue and place agent far from it
    assert len(gt.clues) > 0
    clue = gt.clues[0]

    # Teleport agent to 5 cells away from clue 0, and check that clue 0 is NOT revealed
    env._position = (clue.position[0] + 5, clue.position[1])

    # Scan with radius 2 -> clue 0 is 5 cells away, should never be revealed
    obs = env.step(Action(type=ActionType.SCAN_AREA, radius=2))
    assert not any(c.clue_id == clue.clue_id for c in obs.clues)

    # Move agent to 1 cell away from clue
    env._position = (clue.position[0] + 1, clue.position[1])

    # Scan with radius 1 multiple times until detected
    revealed = False
    for _ in range(10):
        obs = env.step(Action(type=ActionType.SCAN_AREA, radius=1))
        if any(c.clue_id == clue.clue_id for c in obs.clues):
            revealed = True
            break
    assert revealed is True

    # Subsequent scans must always return this revealed clue without re-rolling
    obs = env.step(Action(type=ActionType.SCAN_AREA, radius=1))
    assert any(c.clue_id == clue.clue_id for c in obs.clues)


def test_stranded_termination():
    """Battery reaching 0 away from a charger causes immediate stranded termination."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    env = Environment(cfg)
    _, obs = env.reset()

    # Move off charger
    env.step(Action(type=ActionType.MOVE_E))
    assert env._position not in env._world._chargers

    # Drain battery to 1
    env._battery = 1

    # Take MOVE action costing 1 battery
    obs = env.step(Action(type=ActionType.MOVE_E))
    assert obs.battery == 0
    assert obs.done is True
    assert obs.done_reason == "stranded"


def test_timeout_termination():
    """Exhausting time budget causes timeout termination."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    env = Environment(cfg)
    _, obs = env.reset()

    # Set time left to 1
    env._time_left = 1
    obs = env.step(Action(type=ActionType.MOVE_E))
    assert obs.done is True
    assert obs.done_reason == "timeout"


def test_determinism_identical_actions():
    """Same seed and identical action sequence produce identical observations."""
    cfg = load_config(Path("configs/mission_medium.yaml"))

    actions = [
        Action(type=ActionType.MOVE_E),
        Action(type=ActionType.SCAN_SIGNAL),
        Action(type=ActionType.MOVE_S),
        Action(type=ActionType.SCAN_AREA, radius=2),
    ]

    env1 = Environment(cfg)
    _, obs1 = env1.reset()
    trace1 = [obs1]
    for a in actions:
        trace1.append(env1.step(a))

    env2 = Environment(cfg)
    _, obs2 = env2.reset()
    trace2 = [obs2]
    for a in actions:
        trace2.append(env2.step(a))

    assert len(trace1) == len(trace2)
    for o1, o2 in zip(trace1, trace2):
        assert o1.step == o2.step
        assert o1.position == o2.position
        assert o1.battery == o2.battery
        assert o1.time_left == o2.time_left
        if o1.signal is not None:
            assert o2.signal is not None
            assert o1.signal.strength == o2.signal.strength
            assert o1.signal.bearing_deg == o2.signal.bearing_deg
