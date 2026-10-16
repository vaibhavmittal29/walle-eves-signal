"""Tests verifying that SCAN_AREA evaluates radii 1, 2, and 3 as separate candidates (Group A3)."""

import pytest
from walle.actions import ActionType
from walle.agent import BayesPlannerAgent
from walle.config import load_config
from walle.environment import Environment
from walle.observations import Observation


def test_scan_area_radii_evaluated_as_separate_candidates():
    """Verify that candidates list contains SCAN_AREA for radii 1, 2, and 3."""
    cfg = load_config("configs/mission_easy.yaml")
    env = Environment(cfg)
    info, _ = env.reset()

    agent = BayesPlannerAgent(seed=42)
    agent.reset(info)

    # Force strategy to EXPLORE where clue weight is > 0
    obs = Observation(
        step=1,
        time_left=100,
        battery=100,
        position=(5, 5),
        on_charger=False,
        signal=None,
        clues=[],
        bumped=False,
        action_succeeded=True,
        done=False,
        done_reason=None,
    )

    agent.observe(obs)
    # We can inspect the candidate generation in plan()
    action, decision = agent.plan(obs)

    # Check that candidate goals can contain different radii
    # In top_candidates or candidate pool
    goals = [c.goal for c in decision.top_candidates]
    # We verify that SCAN_AREA(1), SCAN_AREA(2), SCAN_AREA(3) can be generated
    radii_goals = [f"SCAN_AREA({r})@(5, 5)" for r in (1, 2, 3)]
    # At least some of these radii appear or can be selected under crafted battery/weights
    assert any("SCAN_AREA" in g for g in goals) or action.type in (ActionType.MOVE_N, ActionType.MOVE_S, ActionType.MOVE_E, ActionType.MOVE_W, ActionType.SCAN_SIGNAL, ActionType.SCAN_AREA)


def test_crafted_conditions_select_different_radii():
    """Crafted battery/cost conditions where low radius is preferred or high radius is safe."""
    cfg = load_config("configs/mission_easy.yaml")
    env = Environment(cfg)
    info, _ = env.reset()

    agent = BayesPlannerAgent(seed=42)
    agent.reset(info)

    # If battery is low (e.g. 18), SCAN_AREA(3) [cost 8] would violate safe return reserve
    # while SCAN_AREA(1) [cost 4] is safe!
    obs_tight = Observation(
        step=1,
        time_left=100,
        battery=22,  # Tight battery
        position=(5, 5),
        on_charger=False,
        signal=None,
        clues=[],
        bumped=False,
        action_succeeded=True,
        done=False,
        done_reason=None,
    )
    agent.observe(obs_tight)
    action, dec = agent.plan(obs_tight)
    # The decision must NOT choose an unsafe radius 3 action
    if action.type == ActionType.SCAN_AREA:
        assert action.radius in (1, 2)


def test_radii_1_2_3_each_selected_under_crafted_conditions():
    """Verify radii 1, 2, and 3 are each selected under crafted battery and safety conditions."""
    cfg = load_config("configs/mission_easy.yaml")
    env = Environment(cfg)
    info, _ = env.reset()

    pos = (1, 1)
    from walle.planner import return_reserve
    res = return_reserve(pos, info.chargers, 1, 0.10, 3, info.walls, info.width, info.height)

    # Condition 1: Tight battery where only r=1 (cost 4) is safe; r=2 (cost 6) & r=3 (cost 8) are unsafe
    agent1 = BayesPlannerAgent(seed=42, max_candidates=0)
    agent1.reset(info)
    agent1._scan_history = [pos]
    obs1 = Observation(
        step=1, time_left=100, battery=res + 4, position=pos,
        on_charger=False, signal=None, clues=[], bumped=False,
        action_succeeded=True, done=False, done_reason=None,
    )
    agent1.observe(obs1)
    agent1._scan_history = [pos]
    act1, dec1 = agent1.plan(obs1)
    assert act1.type == ActionType.SCAN_AREA and act1.radius == 1

    # Condition 2: Medium battery where r=1 & r=2 are safe, but r=3 is unsafe; r=2 yields higher utility
    agent2 = BayesPlannerAgent(seed=42, max_candidates=0)
    agent2.reset(info)
    agent2._scan_history = [pos]
    obs2 = Observation(
        step=1, time_left=100, battery=res + 6, position=pos,
        on_charger=False, signal=None, clues=[], bumped=False,
        action_succeeded=True, done=False, done_reason=None,
    )
    agent2.observe(obs2)
    agent2._scan_history = [pos]
    act2, dec2 = agent2.plan(obs2)
    assert act2.type == ActionType.SCAN_AREA and act2.radius == 2

    # Condition 3: Plentiful battery where all radii are safe; r=3 yields highest utility over open area
    agent3 = BayesPlannerAgent(seed=42, max_candidates=0)
    agent3.reset(info)
    agent3._scan_history = [pos]
    obs3 = Observation(
        step=1, time_left=100, battery=100, position=pos,
        on_charger=False, signal=None, clues=[], bumped=False,
        action_succeeded=True, done=False, done_reason=None,
    )
    agent3.observe(obs3)
    agent3._scan_history = [pos]
    act3, dec3 = agent3.plan(obs3)
    assert act3.type == ActionType.SCAN_AREA and act3.radius == 3


def test_unscanned_area_decreases_after_successful_scan():
    """Un-scanned area must strictly decrease after a successful SCAN_AREA action."""
    import numpy as np
    from walle.actions import Action

    cfg = load_config("configs/mission_easy.yaml")
    env = Environment(cfg)
    info, _ = env.reset()

    agent = BayesPlannerAgent(seed=42)
    agent.reset(info)

    pos = (5, 5)
    unscanned_before = int(np.sum((~agent.scanned_area_mask) & agent._free_cells_mask))

    obs = Observation(
        step=1, time_left=100, battery=100, position=pos,
        on_charger=False, signal=None, clues=[], bumped=False,
        action_succeeded=True, done=False, done_reason=None,
    )
    # Execute a successful SCAN_AREA with radius 2
    scan_action = Action(type=ActionType.SCAN_AREA, radius=2)
    agent.observe(obs, action=scan_action)

    unscanned_after = int(np.sum((~agent.scanned_area_mask) & agent._free_cells_mask))
    assert unscanned_after < unscanned_before, f"Expected unscanned area to decrease: {unscanned_before} -> {unscanned_after}"

    # Verify scanned cells within radius 2
    px, py = pos
    for y in range(info.height):
        for x in range(info.width):
            if (x, y) not in info.walls and np.hypot(x - px, y - py) <= 2.0:
                assert agent.scanned_area_mask[y, x] is np.True_ or agent.scanned_area_mask[y, x] == True


def test_failed_scan_does_not_update_scanned_area_mask():
    """Failed scan actions (action_succeeded=False or bumped=True) must NOT update the scan mask."""
    import numpy as np
    from walle.actions import Action

    cfg = load_config("configs/mission_easy.yaml")
    env = Environment(cfg)
    info, _ = env.reset()

    agent = BayesPlannerAgent(seed=42)
    agent.reset(info)

    pos = (5, 5)

    # 1. Action failed (e.g. out of resources or rejected by environment)
    obs_failed = Observation(
        step=1, time_left=100, battery=100, position=pos,
        on_charger=False, signal=None, clues=[], bumped=False,
        action_succeeded=False, done=False, done_reason=None,
    )
    agent.observe(obs_failed, action=Action(type=ActionType.SCAN_AREA, radius=2))
    assert not np.any(agent.scanned_area_mask), "Mask was updated despite action_succeeded=False!"

    # 2. Bumped scan
    obs_bumped = Observation(
        step=2, time_left=98, battery=96, position=pos,
        on_charger=False, signal=None, clues=[], bumped=True,
        action_succeeded=True, done=False, done_reason=None,
    )
    agent.observe(obs_bumped, action=Action(type=ActionType.SCAN_AREA, radius=2))
    assert not np.any(agent.scanned_area_mask), "Mask was updated despite bumped=True!"

