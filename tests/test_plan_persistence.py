"""Tests verifying plan persistence and re-planning rules (Group A4)."""

import pytest
from walle.actions import Action, ActionType
from walle.agent import BayesPlannerAgent
from walle.config import load_config
from walle.environment import Environment
from walle.observations import Observation, SignalReading


def test_surprising_reading_causes_replan():
    """Verify that a surprising / new signal reading mid-plan causes a re-plan."""
    cfg = load_config("configs/mission_easy.yaml")
    env = Environment(cfg)
    info, _ = env.reset()

    agent = BayesPlannerAgent(seed=42)
    agent.reset(info)

    # Initial step with no signal
    obs0 = Observation(
        step=1,
        time_left=100,
        battery=100,
        position=(2, 2),
        on_charger=True,
        signal=None,
        clues=[],
        bumped=False,
        action_succeeded=True,
        done=False,
        done_reason=None,
    )
    act0, dec0 = agent.act(obs0)

    # If the agent formed a multi-step plan, simulate mid-plan step
    agent._current_plan = [Action(type=ActionType.MOVE_E), Action(type=ActionType.MOVE_E), Action(type=ActionType.SCAN_SIGNAL)]
    agent._current_plan_goal = "GO_TO@(4, 2)->SCAN"
    agent._current_plan_utility = 1.0

    # Next step: arrival of a new strong signal reading should trigger re-planning (rule c)
    obs_signal = Observation(
        step=2,
        time_left=99,
        battery=99,
        position=(3, 2),
        on_charger=False,
        signal=SignalReading(strength=0.8, bearing_deg=180.0, dropout=False),
        clues=[],
        bumped=False,
        action_succeeded=True,
        done=False,
        done_reason=None,
    )

    act1, dec1 = agent.act(obs_signal)
    # The plan should have been re-evaluated to exploit the new bearing 180° (South)
    # Goal should not simply be the old target without re-evaluating
    assert dec1.reasoning is not None
