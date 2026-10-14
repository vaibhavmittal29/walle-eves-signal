"""Statistical and behavior tests for the forward signal and clue model."""

import numpy as np
import pytest

from walle.config import SensorConfig
from walle.signal_model import expected_strength, sample_clue_value, sample_signal


def test_expected_strength_formula():
    """Verify mu(d, k) = A_k / (1 + (d / d0)^2)."""
    amp = {"active": 1.0, "low_power": 0.6, "damaged": 0.35}
    d0 = 6.0

    # At distance 0, mu should equal A_k
    assert expected_strength(0.0, "active", amp, d0) == 1.0
    assert expected_strength(0.0, "low_power", amp, d0) == 0.6

    # At distance d0, mu should equal A_k / 2
    assert expected_strength(6.0, "active", amp, d0) == pytest.approx(0.5)
    assert expected_strength(6.0, "low_power", amp, d0) == pytest.approx(0.3)


def test_signal_strength_statistics_2000_samples():
    """Verify mean of 2000 sampled strengths matches mu(d, k) within 3 standard errors."""
    sensor = SensorConfig(
        noise_scale=1.0,
        strength_sigma=0.05,
        d0=6.0,
        amplitude={"active": 1.0, "low_power": 0.6, "damaged": 0.35},
        dropout={"active": 0.0, "low_power": 0.0, "damaged": 0.0},  # Disable dropouts for pure strength test
    )
    rng = np.random.default_rng(42)

    agent_pos = (2, 2)
    eve_pos = (6, 5)  # distance = 5.0
    d = 5.0
    mu_true = expected_strength(d, "active", sensor.amplitude, sensor.d0)

    samples = []
    for _ in range(2000):
        obs = sample_signal(agent_pos, eve_pos, "active", sensor, rng)
        assert obs.strength is not None
        samples.append(obs.strength)

    sample_mean = float(np.mean(samples))
    sample_std = float(np.std(samples, ddof=1))
    std_error = sample_std / np.sqrt(len(samples))

    # Must match mu_true within 3 standard errors
    assert abs(sample_mean - mu_true) < 3.0 * std_error


def test_signal_dropout_rates():
    """Verify status-dependent dropout rates."""
    sensor = SensorConfig(
        dropout={"active": 0.05, "low_power": 0.25, "damaged": 0.50},
    )
    rng = np.random.default_rng(123)
    agent_pos = (0, 0)
    eve_pos = (10, 10)

    for status, expected_p in (("active", 0.05), ("low_power", 0.25), ("damaged", 0.50)):
        dropouts = 0
        trials = 1500
        for _ in range(trials):
            obs = sample_signal(agent_pos, eve_pos, status, sensor, rng)
            if obs.dropout:
                dropouts += 1

        empirical_p = dropouts / trials
        # 3-sigma tolerance for Bernoulli
        se = np.sqrt(expected_p * (1.0 - expected_p) / trials)
        assert abs(empirical_p - expected_p) < 3.5 * se


def test_clue_sampling():
    """Verify noisy clue sampling respects types and bounds."""
    sensor = SensorConfig()
    rng = np.random.default_rng(777)
    clue_pos = (5, 5)
    eve_pos = (8, 9)  # dx=3, dy=4 => dist=5.0, bearing=143.13 deg

    # Bearing clue
    b_val = sample_clue_value(clue_pos, eve_pos, "active", "bearing", sensor, rng)
    assert isinstance(b_val, float)
    assert 0.0 <= b_val < 360.0

    # Range clue
    r_val = sample_clue_value(clue_pos, eve_pos, "active", "range", sensor, rng)
    assert isinstance(r_val, float)
    assert r_val >= 0.0

    # Status clue
    s_val = sample_clue_value(clue_pos, eve_pos, "active", "status", sensor, rng)
    assert s_val in ("active", "low_power", "damaged")
