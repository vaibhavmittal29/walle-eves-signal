"""Unit and statistical tests for the Bayesian belief engine."""

from pathlib import Path
import numpy as np
import pytest

from walle.belief import Belief, apply_observation
from walle.config import AppConfig, MissionSectionConfig, SensorConfig, load_config
from walle.geometry import bearing, distance
from walle.observations import ClueReading, Observation, SignalReading
from walle.signal_model import (
    build_clue_likelihood,
    build_signal_likelihood,
    expected_strength,
    sample_signal,
)
from walle.world import World


def test_belief_normalization_and_wall_zeros():
    """Belief must sum to 1.0 within 1e-9, and probability on all walls must be exactly 0."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    world = World(cfg)
    info = world.public_info()
    belief = Belief(info)

    # Prior check
    assert abs(np.sum(belief.grid) - 1.0) < 1e-9
    loc_marg = belief.location_marginal()
    for wx, wy in info.walls:
        assert loc_marg[wy, wx] == 0.0

    # Random likelihood update check
    dummy_L = np.random.uniform(0.1, 1.0, size=(info.height, info.width, 3))
    belief.update(dummy_L)

    assert abs(np.sum(belief.grid) - 1.0) < 1e-9
    loc_marg = belief.location_marginal()
    for wx, wy in info.walls:
        assert loc_marg[wy, wx] == 0.0


def test_noise_free_triangulation_converges_to_true_cell():
    """With noise-free synthetic readings from 3 positions, MAP must equal true cell."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    world = World(cfg)
    info = world.public_info()
    gt = world.ground_truth()
    true_loc = gt.eve_location
    true_status = gt.eve_status

    belief = Belief(info)

    # 3 distinct scan positions
    scan_points = [(1, 1), (18, 2), (10, 18)]

    for pos in scan_points:
        d = distance(pos, true_loc)
        str_val = expected_strength(d, true_status, info.sensor_prior.amplitude, info.sensor_prior.d0)
        brg_val = bearing(pos, true_loc)
        reading = SignalReading(strength=str_val, bearing_deg=brg_val, dropout=False)

        L = build_signal_likelihood(
            reading=reading,
            agent_pos=pos,
            prior=info.sensor_prior,
            width=info.width,
            height=info.height,
            walls=info.walls,
        )
        belief.update(L)

    map_pos = belief.map_estimate()
    assert map_pos == true_loc


def test_median_error_with_noise_over_50_seeds():
    """With realistic noise, after 6 spread-out scans, median error over 50 seeds is <= 2 cells."""
    base_cfg = load_config(Path("configs/mission_medium.yaml"))
    errors = []

    for seed in range(50):
        # We vary master seed to randomize true EVE placement and environments
        m = MissionSectionConfig(
            name=f"test_{seed}",
            seed=seed,
            grid=base_cfg.mission.grid,
            start=base_cfg.mission.start,
            obstacles=base_cfg.mission.obstacles,
            chargers=base_cfg.mission.chargers,
            eve=base_cfg.mission.eve,
            clues=base_cfg.mission.clues,
        )
        cfg_seed = AppConfig(
            mission=m,
            initial_signal=base_cfg.initial_signal,
            resources=base_cfg.resources,
            sensor=base_cfg.sensor,
            agent=base_cfg.agent,
        )
        world = World(cfg_seed)
        info = world.public_info()
        gt = world.ground_truth()
        rng = np.random.default_rng(1000 + seed)

        belief = Belief(info)
        scan_points = [(2, 2), (15, 9), (4, 15), (16, 16), (5, 5), (10, 10)]

        for pos in scan_points:
            sig = sample_signal(
                agent_pos=pos,
                eve_pos=gt.eve_location,
                eve_status=gt.eve_status,
                sensor=cfg_seed.sensor,
                rng=rng,
            )
            L = build_signal_likelihood(
                reading=sig,
                agent_pos=pos,
                prior=info.sensor_prior,
                width=info.width,
                height=info.height,
                walls=info.walls,
            )
            belief.update(L)

        map_pos = belief.map_estimate()
        err = distance(map_pos, gt.eve_location)
        errors.append(err)

    median_err = float(np.median(errors))
    assert median_err <= 2.0, f"Median error {median_err:.2f} exceeds 2.0 cells threshold!"


def test_entropy_decreases_on_average():
    """Information gain reduces Shannon entropy on average across trials."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    world = World(cfg)
    info = world.public_info()
    gt = world.ground_truth()

    entropy_drops = []
    for seed in range(30):
        rng = np.random.default_rng(5000 + seed)
        belief = Belief(info)
        h_before = belief.entropy()

        pos = (info.start[0] + (seed % 5), info.start[1] + (seed % 5))
        sig = sample_signal(pos, gt.eve_location, gt.eve_status, cfg.sensor, rng)
        L = build_signal_likelihood(sig, pos, info.sensor_prior, info.width, info.height, info.walls)
        belief.update(L)
        h_after = belief.entropy()
        entropy_drops.append(h_before - h_after)

    mean_drop = float(np.mean(entropy_drops))
    assert mean_drop > 0.0, f"Average entropy drop was non-positive: {mean_drop:.3f} bits"


def test_repeated_dropouts_shift_status_towards_damaged_or_low_power():
    """Repeated dropouts should significantly shift the status marginal towards damaged/low_power."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    world = World(cfg)
    info = world.public_info()
    belief = Belief(info)

    # Initial uniform status marginal: ~0.33 each
    init_marg = belief.status_marginal()
    assert abs(init_marg["active"] - 1.0 / 3.0) < 0.01

    # Simulate 5 dropout observations
    dropout_reading = SignalReading(strength=None, bearing_deg=None, dropout=True)
    for _ in range(5):
        L = build_signal_likelihood(
            reading=dropout_reading,
            agent_pos=info.start,
            prior=info.sensor_prior,
            width=info.width,
            height=info.height,
            walls=info.walls,
        )
        belief.update(L)

    after_marg = belief.status_marginal()
    # Damaged has dropout 0.50, low_power 0.25, active 0.05
    # Probability of active must drop substantially, damaged must dominate
    assert after_marg["active"] < 0.05
    assert after_marg["damaged"] > after_marg["low_power"] > after_marg["active"]


def test_status_clue_shifts_marginal():
    """A status clue reporting 'damaged' with 0.8 accuracy must increase damaged probability."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    world = World(cfg)
    info = world.public_info()
    belief = Belief(info)

    L = build_clue_likelihood(
        clue_pos=(5, 5),
        clue_type="status",
        clue_value="damaged",
        prior=info.sensor_prior,
        width=info.width,
        height=info.height,
        walls=info.walls,
    )
    belief.update(L)

    marg = belief.status_marginal()
    assert marg["damaged"] > 0.70
    assert marg["active"] < 0.20


def test_robust_mixture_prevents_zero_mass_on_truth():
    """With assumed_spoof_rate=0.15, a spoofed reading does not collapse true location to 0."""
    cfg = load_config(Path("configs/mission_hard_decoys.yaml"))
    world = World(cfg)
    info = world.public_info()
    gt = world.ground_truth()
    true_x, true_y = gt.eve_location

    belief = Belief(info)
    prior_mass_at_truth = float(belief.location_marginal()[true_y, true_x])

    # Inject completely misleading reading (e.g. bearing 180 degrees away from truth)
    true_b = bearing(info.start, (true_x, true_y))
    wrong_b = (true_b + 180.0) % 360.0
    spoof_reading = SignalReading(strength=0.9, bearing_deg=wrong_b, dropout=False)

    L = build_signal_likelihood(
        reading=spoof_reading,
        agent_pos=info.start,
        prior=info.sensor_prior,
        width=info.width,
        height=info.height,
        walls=info.walls,
    )
    belief.update(L)

    post_mass_at_truth = float(belief.location_marginal()[true_y, true_x])
    assert post_mass_at_truth > 0.0, "Mass on truth collapsed to zero!"
    assert belief.contradiction_count == 0
