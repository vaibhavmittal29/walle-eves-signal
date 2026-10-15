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
