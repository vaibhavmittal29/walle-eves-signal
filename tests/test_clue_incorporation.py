"""Tests verifying clue incorporation into agent belief (Group A1)."""

import pytest
from walle.agent import BayesPlannerAgent
from walle.config import load_config
from walle.environment import Environment
from walle.observations import ClueReading, Observation


def test_agent_incorporates_clue_changes_belief():
    """Verify that an observation with a clue changes the agent's belief."""
    cfg = load_config("configs/mission_easy.yaml")
    env = Environment(cfg)
    info, _ = env.reset()

    agent = BayesPlannerAgent(seed=42)
    agent.reset(info)

    e0 = agent._belief.entropy()
    # Clue with bearing pointing toward (10, 10)
    clue = ClueReading(clue_id=1, position=(2, 2), type="bearing", value=45.0)
    obs_with_clue = Observation(
        step=1,
        time_left=100,
        battery=100,
        position=(0, 0),
        on_charger=True,
        signal=None,
        clues=[clue],
        bumped=False,
        action_succeeded=True,
        done=False,
        done_reason=None,
    )

    agent.act(obs_with_clue)
    e1 = agent._belief.entropy()

    # The belief MUST change (entropy must decrease or shift)
    assert abs(e0 - e1) > 0.01, f"Belief was not updated by clue! e0={e0}, e1={e1}"


def test_bearing_clue_shifts_map_toward_truth():
    """Verify that a bearing clue shifts the spatial marginal / MAP toward the clue vector."""
    cfg = load_config("configs/mission_easy.yaml")
    env = Environment(cfg)
    info, _ = env.reset()

    agent = BayesPlannerAgent(seed=42)
    agent.reset(info)

    # Place clue at (5, 5) with bearing 90 degrees (East -> +x)
    clue = ClueReading(clue_id=101, position=(5, 5), type="bearing", value=90.0)
    obs = Observation(
        step=1,
        time_left=100,
        battery=100,
        position=(5, 5),
        on_charger=False,
        signal=None,
        clues=[clue],
        bumped=False,
        action_succeeded=True,
        done=False,
        done_reason=None,
    )

    agent.act(obs)
    map_x, map_y = agent._belief.map_estimate()
    # Bearing 90 deg is East, so x should be > 5
    assert map_x >= 5, f"Expected MAP to shift East (x >= 5), got ({map_x}, {map_y})"


def test_status_clue_shifts_status_marginal():
    """Verify that a status clue shifts the status marginal toward the clue status."""
    cfg = load_config("configs/mission_easy.yaml")
    env = Environment(cfg)
    info, _ = env.reset()

    agent = BayesPlannerAgent(seed=42)
    agent.reset(info)

    clue = ClueReading(clue_id=202, position=(5, 5), type="status", value="damaged")
    obs = Observation(
        step=1,
        time_left=100,
        battery=100,
        position=(5, 5),
        on_charger=False,
        signal=None,
        clues=[clue],
        bumped=False,
        action_succeeded=True,
        done=False,
        done_reason=None,
    )

    agent.act(obs)
    st_marg = agent._belief.status_marginal()
    assert st_marg["damaged"] > 0.5, f"Expected damaged status > 0.5, got {st_marg}"


def test_repeated_clue_updates_only_once():
    """Verify that observing the same clue twice updates the belief only once."""
    cfg = load_config("configs/mission_easy.yaml")
    env = Environment(cfg)
    info, _ = env.reset()

    agent = BayesPlannerAgent(seed=42)
    agent.reset(info)

    clue = ClueReading(clue_id=303, position=(5, 5), type="range", value=3.0)
    obs = Observation(
        step=1,
        time_left=100,
        battery=100,
        position=(5, 5),
        on_charger=False,
        signal=None,
        clues=[clue],
        bumped=False,
        action_succeeded=True,
        done=False,
        done_reason=None,
    )

    agent.act(obs)
    e1 = agent._belief.entropy()

    # Feed the exact same clue in step 2
    obs2 = Observation(
        step=2,
        time_left=99,
        battery=99,
        position=(5, 5),
        on_charger=False,
        signal=None,
        clues=[clue],
        bumped=False,
        action_succeeded=True,
        done=False,
        done_reason=None,
    )
    agent.act(obs2)
    e2 = agent._belief.entropy()

    assert abs(e1 - e2) < 1e-9, f"Same clue double counted! e1={e1}, e2={e2}"
