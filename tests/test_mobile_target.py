"""Tests for mobile-target timing and prediction models (Phase 3)."""

import math
import numpy as np
import pytest

from walle.agent import BayesPlannerAgent
from walle.belief import Belief
from walle.config import (
    AppConfig,
    CluesConfig,
    EveConfig,
    GridConfig,
    InitialSignalConfig,
    MissionSectionConfig,
    ObstaclesConfig,
)
from walle.environment import Environment
from walle.observations import Observation, PublicMissionInfo, SignalReading
from walle.runner import run_mission


def test_observation_timing_not_pre_diffused():
    """Verify that observation at step t is applied to belief BEFORE forward prediction."""
    # Create an agent with mobility enabled
    agent = BayesPlannerAgent(seed=42, mobility="random_walk", drift_sigma=0.5)
    cfg = AppConfig(
        mission=MissionSectionConfig(
            grid=GridConfig(width=10, height=10),
            eve=EveConfig(mobility="random_walk"),
            obstacles=ObstaclesConfig(mode="explicit", explicit=[]),
        ),
        initial_signal=InitialSignalConfig(mode="configured", bearing_deg=None, strength=None),
    )
    env = Environment(cfg)
    info, obs0 = env.reset()
    agent.reset(info)

    # Initial step 0
    agent.observe(obs0)

    # Concentrate belief artificially on a single point to track diffusion timing
    agent._belief._grid[:, :, :] = 0.0
    agent._belief._grid[5, 5, 0] = 1.0

    # Mock an observation at step 1 with bearing pointing exactly to (5, 5) from (5, 4)
    # Target is South (bearing 180.0)
    obs1 = Observation(
        step=1,
        position=(5, 4),
        battery=90,
        time_left=240,
        action_succeeded=True,
        bumped=False,
        on_charger=False,
        signal=SignalReading(
            strength=0.9,
            bearing_deg=180.0,
            dropout=False,
        ),
        clues=(),
        done=False,
        done_reason=None,
    )

    # Check that in apply_observation, the prior used to evaluate the likelihood is the un-diffused state
    # We monkey-patch belief.update to record whether the grid was already diffused at the moment update() was called
    update_called_with_pre_diffused_grid = []
    original_update = agent._belief.update

    def tracking_update(L):
        # If pre-diffused before update, the mass at (5, 5) would already be < 1.0 before multiplying L
        # In an un-diffused state, grid[5, 5, 0] is still 1.0
        update_called_with_pre_diffused_grid.append(agent._belief._grid[5, 5, 0] < 0.99)
        return original_update(L)

    agent._belief.update = tracking_update
    agent.observe(obs1)

    assert len(update_called_with_pre_diffused_grid) >= 1
    assert bool(update_called_with_pre_diffused_grid[0]) is False, (
        "Belief was pre-diffused BEFORE observation update was applied!"
    )


def test_random_walk_probability_conservation_with_walls():
    """Verify that random-walk prediction conserves mass within 1e-12 after 50 steps on a map with walls."""
    # 10x10 map with walls, start at (0, 0)
    walls = frozenset({(2, 3), (2, 4), (5, 5), (5, 6), (7, 1), (7, 2)})
    cfg = AppConfig(
        mission=MissionSectionConfig(
            grid=GridConfig(width=10, height=10),
            start=(0, 0),
            chargers=[(0, 0)],
            obstacles=ObstaclesConfig(mode="explicit", explicit=list(walls)),
        )
    )
    env = Environment(cfg)
    info, _ = env.reset()

    belief = Belief(info)
    assert abs(float(np.sum(belief.grid)) - 1.0) < 1e-12

    for step in range(50):
        belief.predict(mobility_type="random_walk")
        total_mass = float(np.sum(belief.grid))
        assert abs(total_mass - 1.0) < 1e-12, f"Mass deviated at step {step}: {total_mass}"
        # All wall cells must have strictly zero mass
        for wx, wy in walls:
            assert belief.grid[wy, wx, :].sum() == 0.0, f"Wall cell ({wx}, {wy}) received mass!"


def test_diffusion_kernel_respects_walls_and_conserves_mass():
    """Verify discrete Gaussian diffusion kernel respects walls and does not leak mass into obstacles."""
    walls = frozenset({(4, 4), (4, 5), (5, 4), (5, 5)})
    cfg = AppConfig(
        mission=MissionSectionConfig(
            grid=GridConfig(width=10, height=10),
            obstacles=ObstaclesConfig(mode="explicit", explicit=list(walls)),
        )
    )
    env = Environment(cfg)
    info, _ = env.reset()

    belief = Belief(info)
    # Start with localized mass adjacent to the wall block at (3, 4)
    belief._grid[:, :, :] = 0.0
    belief._grid[4, 3, 0] = 1.0

    for step in range(20):
        belief.predict(mobility_type="diffusion", diffusion_sigma=1.2)
        total_mass = float(np.sum(belief.grid))
        assert abs(total_mass - 1.0) < 1e-12, f"Diffusion mass deviated at step {step}: {total_mass}"
        # Wall cells must remain exactly 0.0
        for wx, wy in walls:
            assert belief.grid[wy, wx, :].sum() == 0.0, f"Diffusion leaked mass into wall ({wx}, {wy})!"


@pytest.mark.parametrize("mode", ["stationary", "random_walk", "diffusion"])
def test_mission_runs_with_all_mobility_modes(tmp_path, mode):
    """Verify that an end-to-end mission executes without error under stationary, random_walk, and diffusion."""
    cfg = AppConfig(
        mission=MissionSectionConfig(
            name=f"test_mobility_{mode}",
            seed=101,
            grid=GridConfig(width=12, height=12),
            eve=EveConfig(
                mobility=mode,
                min_distance_from_start=4,
            ),
            clues=CluesConfig(count=3),
        ),
        resources=AppConfig().resources,
    )
    out_dir = tmp_path / f"out_{mode}"
    res = run_mission(
        config_path=cfg,
        agent_type="bayes_planner",
        out_dir=out_dir,
        master_seed=101,
    )
    assert res.outcome in ("declared", "timeout", "stranded")
    assert res.steps > 0
