"""Tests for initial-signal semantics and missing-bearing likelihood handling."""

import math
import numpy as np
import pytest

from walle.config import AppConfig, InitialSignalConfig, MissionSectionConfig, SensorConfig
from walle.environment import Environment
from walle.geometry import bearing
from walle.observations import SensorPrior, SignalReading
from walle.signal_model import STATUS_TO_IDX, build_signal_likelihood, sample_signal
from walle.world import World


@pytest.fixture
def default_prior() -> SensorPrior:
    return SensorPrior(
        noise_scale=1.0,
        strength_sigma=0.05,
        bearing_sigma_base_deg=8.0,
        bearing_sigma_per_cell_deg=2.0,
        d0=6.0,
        amplitude={"active": 1.0, "low_power": 0.6, "damaged": 0.35},
        dropout={"active": 0.05, "low_power": 0.25, "damaged": 0.50},
        clue_bearing_sigma_deg=15.0,
        clue_range_sigma=2.0,
        clue_status_accuracy=0.8,
        clue_detect_probability=0.9,
        assumed_spoof_rate=0.0,
    )


def test_strength_only_does_not_collapse_onto_agent_cell(default_prior):
    """Strength-only reading must compute strength likelihood across grid, not collapse onto agent."""
    reading = SignalReading(
        strength=0.5,
        bearing_deg=None,
        dropout=False,
        missing_bearing_reason="not_provided",
    )
    agent_pos = (5, 5)
    L = build_signal_likelihood(
        reading=reading,
        agent_pos=agent_pos,
        prior=default_prior,
        width=11,
        height=11,
        walls=set(),
    )

    # Must NOT be collapsed only on (5, 5)
    # Surrounding cells at distance > 0 must have positive likelihood
    assert L[5, 6, 0] > 0.0, "Cell (6, 5) should have non-zero likelihood for strength-only reading"
    assert L[5, 7, 0] > 0.0, "Cell (7, 5) should have non-zero likelihood for strength-only reading"
    assert np.count_nonzero(L[:, :, 0] > 0) > 1, "Likelihood should not be concentrated solely on agent pos"


def test_bearing_only_applies_angular_likelihood_without_strength_distortion(default_prior):
    """Bearing-only reading evaluates angular likelihood and sets d=0 to zero likelihood."""
    reading = SignalReading(
        strength=None,
        bearing_deg=90.0,  # Due East (+x)
        dropout=False,
        missing_bearing_reason=None,
    )
    agent_pos = (5, 5)
    L = build_signal_likelihood(
        reading=reading,
        agent_pos=agent_pos,
        prior=default_prior,
        width=11,
        height=11,
        walls=set(),
    )

    # At agent position d=0, bearing is physically undefined -> zero likelihood
    assert L[5, 5, 0] == 0.0
    assert L[5, 5, 1] == 0.0
    assert L[5, 5, 2] == 0.0

    # East direction (x > 5, y = 5) should have high likelihood
    # West direction (x < 5, y = 5) should have near zero likelihood
    east_val = L[5, 8, 0]
    west_val = L[5, 2, 0]
    assert east_val > 10.0 * west_val

    # Status variation should strictly reflect (1 - P_drop[k]) since strength is None
    for idx, st in enumerate(("active", "low_power", "damaged")):
        expected_ratio = (1.0 - default_prior.dropout[st]) / (1.0 - default_prior.dropout["active"])
        actual_ratio = L[5, 8, idx] / L[5, 8, 0]
        assert math.isclose(actual_ratio, expected_ratio, rel_tol=1e-5)


def test_dropout_shifts_status_marginals_without_spatial_distortion(default_prior):
    """Dropout carries status evidence (P_drop[k]) with zero spatial bias."""
    reading = SignalReading(
        strength=None,
        bearing_deg=None,
        dropout=True,
        missing_bearing_reason="dropout",
    )
    agent_pos = (5, 5)
    L = build_signal_likelihood(
        reading=reading,
        agent_pos=agent_pos,
        prior=default_prior,
        width=10,
        height=10,
        walls=set(),
    )

    # For any status, spatial distribution must be flat across all cells
    for idx, st in enumerate(("active", "low_power", "damaged")):
        p_drop = default_prior.dropout[st]
        assert np.allclose(L[:, :, idx], p_drop)

    # Status likelihood ratio must match P_drop[damaged] / P_drop[active] = 0.50 / 0.05 = 10.0
    ratio = L[0, 0, STATUS_TO_IDX["damaged"]] / L[0, 0, STATUS_TO_IDX["active"]]
    assert math.isclose(ratio, 10.0, rel_tol=1e-5)


def test_co_located_reading_evaluates_strength_through_forward_model(default_prior):
    """Co-located reading evaluates observed strength at d=0 rather than assigning binary 1.0."""
    # When active target is co-located, expected strength at d=0 is A_active = 1.0.
    # When damaged target is co-located, expected strength at d=0 is A_damaged = 0.35.
    agent_pos = (5, 5)

    reading_active_like = SignalReading(
        strength=1.0,
        bearing_deg=None,
        dropout=False,
        missing_bearing_reason="co_located",
    )
    L_act = build_signal_likelihood(
        reading=reading_active_like,
        agent_pos=agent_pos,
        prior=default_prior,
        width=10,
        height=10,
        walls=set(),
    )

    # Non-agent cells are 0
    assert L_act[4, 5, 0] == 0.0
    assert L_act[5, 6, 0] == 0.0

    # At agent cell, active should have higher likelihood than damaged for strength=1.0
    act_idx = STATUS_TO_IDX["active"]
    dam_idx = STATUS_TO_IDX["damaged"]
    assert L_act[5, 5, act_idx] > L_act[5, 5, dam_idx]

    # For strength=0.35, damaged should have higher likelihood than active
    reading_damaged_like = SignalReading(
        strength=0.35,
        bearing_deg=None,
        dropout=False,
        missing_bearing_reason="co_located",
    )
    L_dam = build_signal_likelihood(
        reading=reading_damaged_like,
        agent_pos=agent_pos,
        prior=default_prior,
        width=10,
        height=10,
        walls=set(),
    )
    assert L_dam[5, 5, dam_idx] > L_dam[5, 5, act_idx]


def test_configured_vs_generated_initial_signal():
    """Environment correctly implements configured vs generated initial signals."""
    # 1. Configured mode
    cfg_conf = AppConfig(
        initial_signal=InitialSignalConfig(
            mode="configured",
            bearing_deg=42.0,
            strength=0.77,
        )
    )
    env_conf = Environment(cfg_conf)
    pub_info, obs = env_conf.reset()

    assert pub_info.initial_signal.bearing_deg == 42.0
    assert pub_info.initial_signal.strength == 0.77
    assert obs.signal is not None
    assert obs.signal.bearing_deg == 42.0
    assert obs.signal.strength == 0.77

    # 2. Generated mode: samples from true EVE state deterministically
    cfg_gen = AppConfig(
        mission=MissionSectionConfig(seed=12345),
        initial_signal=InitialSignalConfig(mode="generated"),
    )
    env_gen = Environment(cfg_gen)
    pub_info_gen, obs_gen = env_gen.reset()

    assert obs_gen.signal is not None
    # Generated signal is non-trivial and matches sample_signal
    gt = env_gen._world.ground_truth()
    sig_expected = sample_signal(
        agent_pos=pub_info_gen.start,
        eve_pos=gt.eve_location,
        eve_status=gt.eve_status,
        sensor=cfg_gen.sensor,
        rng=np.random.default_rng(12345 + 555),
        decoys=gt.decoys,
    )
    assert obs_gen.signal.dropout == sig_expected.dropout
    assert obs_gen.signal.missing_bearing_reason == sig_expected.missing_bearing_reason
    if not sig_expected.dropout:
        assert math.isclose(obs_gen.signal.strength, sig_expected.strength, abs_tol=1e-5)
        if sig_expected.bearing_deg is not None:
            assert math.isclose(obs_gen.signal.bearing_deg, sig_expected.bearing_deg, abs_tol=1e-5)
