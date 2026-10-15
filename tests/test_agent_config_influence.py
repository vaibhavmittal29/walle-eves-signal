"""Tests verifying that agent configuration in YAML influences behavior (Group A2)."""

import pytest
from walle.actions import ActionType
from walle.agent import BayesPlannerAgent
from walle.config import AgentSafety, AgentThresholds, load_config
from walle.environment import Environment
from walle.observations import Observation
from walle.runner import run_mission
from walle.strategies import Strategy


def test_changing_safety_margin_changes_behavior():
    """Verify that changing agent.safety.margin_fraction in config changes reserve / steps."""
    cfg_path = "configs/mission_easy.yaml"
    cfg = load_config(cfg_path)
    env = Environment(cfg)
    info, obs = env.reset()

    # Agent with strict safety margin
    agent_strict = BayesPlannerAgent(
        seed=42,
        safety=AgentSafety(margin_fraction=0.60, margin_flat=10),
    )
    agent_strict.reset(info)
    agent_strict.observe(obs)
    _, dec_strict = agent_strict.plan(obs)

    # Agent with default safety margin
    agent_default = BayesPlannerAgent(
        seed=42,
        safety=AgentSafety(margin_fraction=0.05, margin_flat=1),
    )
    agent_default.reset(info)
    agent_default.observe(obs)
    _, dec_default = agent_default.plan(obs)

    # Reserves in reasoning or candidate utilities should reflect different reserve requirements
    assert "reserve" in dec_strict.reasoning
    assert "reserve" in dec_default.reasoning
    # Strict reserve must be greater than default reserve
    import re
    res_strict_val = int(re.search(r"reserve (\d+)", dec_strict.reasoning).group(1))
    res_default_val = int(re.search(r"reserve (\d+)", dec_default.reasoning).group(1))
    assert res_strict_val > res_default_val, f"Strict {res_strict_val} <= default {res_default_val}"


def test_changing_declare_threshold_delays_declaration():
    """Verify that a higher declare_location threshold prevents premature declaration."""
    cfg = load_config("configs/mission_easy.yaml")
    env = Environment(cfg)
    info, _ = env.reset()

    # Agent with standard threshold 0.85
    agent_std = BayesPlannerAgent(
        seed=42,
        thresholds=AgentThresholds(track=0.5, verify=0.75, declare_location=0.85, declare_status=0.70),
    )
    agent_std.reset(info)

    # Agent with ultra-high threshold 0.9999
    agent_strict = BayesPlannerAgent(
        seed=42,
        thresholds=AgentThresholds(track=0.5, verify=0.75, declare_location=0.9999, declare_status=0.70),
    )
    agent_strict.reset(info)

    # Place both in VERIFY strategy with 90% location confidence and 90% status confidence
    for ag in (agent_std, agent_strict):
        ag._strategy = Strategy.VERIFY
        ag._belief._grid[:, :, :] = 0.0001
        ag._belief._grid[11, 6, 0] = 0.90  # 90% confidence at (6, 11) for 'active'
        ag._belief._grid /= ag._belief._grid.sum()

    obs = Observation(
        step=5,
        time_left=100,
        battery=80,
        position=(6, 10),
        on_charger=False,
        signal=None,
        clues=[],
        bumped=False,
        action_succeeded=True,
        done=False,
        done_reason=None,
    )

    act_std, _ = agent_std.act(obs)
    act_strict, _ = agent_strict.act(obs)

    assert act_std.type == ActionType.DECLARE, f"Expected DECLARE for std agent, got {act_std.type}"
    assert act_strict.type != ActionType.DECLARE, f"Expected NOT DECLARE for strict agent, got {act_strict.type}"
