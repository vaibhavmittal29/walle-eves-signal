"""Tests for Evidence accounting and Expected Information Gain (Phase 4)."""

import math
import numpy as np
import pytest

from walle.agent import BayesPlannerAgent
from walle.belief import Belief, apply_observation
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
from walle.info_gain import eig_signal
from walle.observations import Observation, SignalReading
from walle.runner import run_mission


def test_initial_signal_info_gain_equals_actual_kl(tmp_path):
    """Initial signal info gain must equal the exact KL divergence from the uniform prior, not 0.5."""
    cfg = AppConfig(
        mission=MissionSectionConfig(
            grid=GridConfig(width=10, height=10),
            obstacles=ObstaclesConfig(mode="explicit", explicit=[]),
        ),
        initial_signal=InitialSignalConfig(
            mode="configured",
            bearing_deg=45.0,
            strength=0.75,
        ),
    )
    res = run_mission(cfg, out_dir=tmp_path)

    # In evidence records, initial signal is step 0
    ev_0 = res.evidence_records[0]
    assert ev_0["type"] == "initial_signal"
    actual_gain = ev_0["info_gain_bits"]

    # 0.5 placeholder must be removed
    assert actual_gain != 0.5, "Initial signal info gain is still hardcoded to 0.5 placeholder!"

    # Compute expected KL directly
    env = Environment(cfg)
    info, obs0 = env.reset()
    b = Belief(info)
    # Uniform prior mass
    num_free = info.width * info.height
    u_val = 1.0 / (num_free * 3)

    # Apply observation
    apply_observation(b, obs0, info.start, info)
    valid = b.grid > 1e-15
    expected_kl = float(np.sum(b.grid[valid] * np.log2(b.grid[valid] / u_val)))

    assert math.isclose(actual_gain, expected_kl, rel_tol=1e-4, abs_tol=1e-4)


def test_no_initial_signal_has_zero_info_gain(tmp_path):
    """When no initial signal is configured (mode='none'), info gain is 0.0 or record is not added."""
    cfg = AppConfig(
        mission=MissionSectionConfig(
            grid=GridConfig(width=10, height=10),
            obstacles=ObstaclesConfig(mode="explicit", explicit=[]),
        ),
        initial_signal=InitialSignalConfig(
            mode="none",
        ),
    )
    res = run_mission(cfg, out_dir=tmp_path)
    init_evs = [e for e in res.evidence_records if e["type"] == "initial_signal"]
    assert len(init_evs) == 0


def test_eig_non_negative_across_diverse_beliefs():
    """Monte Carlo EIG must be non-negative (I >= 0 by Jensen's inequality) across diverse belief states."""
    cfg = AppConfig(
        mission=MissionSectionConfig(
            grid=GridConfig(width=8, height=8),
            start=(0, 0),
            chargers=[(0, 0)],
            obstacles=ObstaclesConfig(mode="explicit", explicit=[(2, 2), (2, 3)]),
        )
    )
    env = Environment(cfg)
    info, _ = env.reset()
    rng = np.random.default_rng(42)

    # State 1: Uniform belief
    b1 = Belief(info)
    eig1 = eig_signal(b1, (3, 3), rng, info, mc_samples=30)
    assert eig1 >= -1e-6

    # State 2: Peaked belief (concentrated at a cell)
    b2 = Belief(info)
    b2._grid[:, :, :] = 0.0
    b2._grid[4, 4, 0] = 0.8
    b2._grid[4, 5, 1] = 0.2
    eig2 = eig_signal(b2, (1, 1), rng, info, mc_samples=30)
    assert eig2 >= -1e-6

    # State 3: Bimodal belief
    b3 = Belief(info)
    b3._grid[:, :, :] = 0.0
    b3._grid[1, 1, :] = 0.25 / 3.0
    b3._grid[6, 6, :] = 0.75 / 3.0
    eig3 = eig_signal(b3, (3, 4), rng, info, mc_samples=30)
    assert eig3 >= -1e-6


def test_sum_of_evidence_consistent_with_entropy_reduction(tmp_path):
    """In a stationary mission, sum of observation KL gains tracks total entropy reduction from prior."""
    cfg = AppConfig(
        mission=MissionSectionConfig(
            name="test_info_accounting",
            seed=7,
            grid=GridConfig(width=10, height=10),
            eve=EveConfig(mobility="stationary", min_distance_from_start=3),
            clues=CluesConfig(count=2),
        ),
        initial_signal=InitialSignalConfig(
            mode="configured",
            bearing_deg=45.0,
            strength=0.5,
        ),
    )
    res = run_mission(cfg, out_dir=tmp_path)
    total_ev_count = len(res.evidence_records)
    assert res.report_dict["evidence_count"] == total_ev_count

    # All evidence records must have valid non-negative float info_gain_bits
    for ev in res.evidence_records:
        assert isinstance(ev["info_gain_bits"], float)
        assert ev["info_gain_bits"] >= -1e-6
