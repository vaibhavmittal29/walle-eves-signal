"""Tests verifying random walk mobility and pure NumPy belief diffusion (Group A5)."""

import pytest
import numpy as np
from walle.config import load_config
from walle.environment import Environment
from walle.belief import Belief
from walle.runner import run_mission


def test_belief_predict_diffuses_without_scipy():
    """Verify that Belief.predict() diffuses probability mass over time using NumPy only."""
    cfg = load_config("configs/mission_easy.yaml")
    env = Environment(cfg)
    info, _ = env.reset()

    belief = Belief(info)
    # Concentrate belief on a single cell (5, 5)
    belief._grid[:, :, :] = 0.0
    belief._grid[5, 5, 0] = 1.0

    p_center_before = float(belief.location_marginal()[5, 5])
    assert p_center_before == 1.0

    # Diffuse with drift_sigma = 0.8
    belief.predict(drift_sigma=0.8)

    loc_after = belief.location_marginal()
    p_center_after = float(loc_after[5, 5])
    p_neighbor = float(loc_after[5, 6])

    # Center mass should drop and neighbors should gain mass
    assert p_center_after < p_center_before
    assert p_neighbor > 0.0
    # Total mass must still sum to exactly 1.0
    assert abs(float(np.sum(belief.grid)) - 1.0) < 1e-9

    # Wall cells must have zero probability
    for wx, wy in info.walls:
        assert belief.grid[wy, wx, :].sum() == 0.0


def test_end_to_end_mission_with_random_walk_mobility(tmp_path):
    """Verify that an end-to-end mission runs without error when eve.mobility is random_walk."""
    yaml_content = """
mission:
  name: mission_random_walk_test
  seed: 42
  grid:
    width: 15
    height: 15
  start: [2, 2]
  obstacles:
    mode: random
    density: 0.05
  chargers:
    - [2, 2]
  eve:
    location: random
    status: active
    mobility: random_walk
    min_distance_from_start: 5
  clues:
    count: 3
    placement: random

initial_signal:
  bearing_deg: 45.0
  strength: 0.3

resources:
  battery_capacity: 100
  battery_initial: 100
  time_budget: 150
"""
    test_yaml = tmp_path / "mission_random_walk.yaml"
    test_yaml.write_text(yaml_content.strip(), encoding="utf-8")

    res = run_mission(
        config_path=str(test_yaml),
        agent_type="bayes_planner",
        out_dir=str(tmp_path / "out"),
        master_seed=42,
    )

    assert res.outcome in ("declared", "timeout", "stranded")
    assert res.steps > 0
