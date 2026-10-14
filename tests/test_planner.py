"""Unit and property tests for BFS planner, safe return reserve, and information gain."""

import math
from pathlib import Path
import numpy as np
import pytest

from walle.belief import Belief
from walle.config import load_config
from walle.geometry import distance
from walle.info_gain import eig_area, eig_signal, generate_candidates
from walle.observations import SignalReading
from walle.planner import (
    bfs_distances,
    is_action_safe,
    nearest_charger,
    return_reserve,
    shortest_path,
)
from walle.signal_model import build_signal_likelihood
from walle.world import World


def test_bfs_and_shortest_path_consistency():
    """Verify shortest path length exactly matches BFS distance on random maps."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    world = World(cfg)
    info = world.public_info()

    bfs_map = bfs_distances(info.start, info.walls, info.width, info.height)
    assert len(bfs_map) > 0

    rng = np.random.default_rng(999)
    sample_targets = rng.choice(list(bfs_map.keys()), size=20, replace=False)

    for target in sample_targets:
        target_tuple = (int(target[0]), int(target[1]))
        expected_len = bfs_map[target_tuple]
        path = shortest_path(info.start, target_tuple, info.walls, info.width, info.height)

        assert len(path) == expected_len + 1
        assert path[0] == info.start
        assert path[-1] == target_tuple

        # Check consecutive steps are 4-connected neighbors
        for i in range(len(path) - 1):
            assert distance(path[i], path[i + 1]) == 1.0
            assert path[i] not in info.walls


def test_return_reserve_monotonicity():
    """Return reserve must increase monotonically as distance to nearest charger increases."""
    chargers = [(0, 0)]
    walls = frozenset()
    w, h = 20, 20
    move_cost = 1
    margin_frac = 0.10
    margin_flat = 3

    last_reserve = -1
    for step in range(0, 15):
        pos = (step, 0)
        res = return_reserve(
            pos=pos,
            chargers=chargers,
            move_battery_cost=move_cost,
            margin_fraction=margin_frac,
            margin_flat=margin_flat,
            walls=walls,
            width=w,
            height=h,
        )
        assert res >= last_reserve
        last_reserve = res

    # At distance 0, reserve is flat margin
    res_at_charger = return_reserve((0, 0), chargers, move_cost, margin_frac, margin_flat, walls, w, h)
    assert res_at_charger == margin_flat


def test_safety_invariant_enforcement():
    """is_action_safe must strictly reject actions that would violate the return reserve."""
    chargers = [(0, 0)]
    walls = frozenset()
    w, h = 20, 20
    move_cost = 1
    margin_frac = 0.10
    margin_flat = 3

    # At cell (10, 0), dist to charger is 10.
    # Reserve needed = ceil(10 * 1.1 + 3) = 14 battery.
    target_pos = (10, 0)
    needed_reserve = return_reserve(target_pos, chargers, move_cost, margin_frac, margin_flat, walls, w, h)
    assert needed_reserve == 14

    # If action costs 2 battery:
    # 1. Starting battery 16 -> 16 - 2 = 14 >= 14 => SAFE
    assert is_action_safe(16, target_pos, 2, chargers, move_cost, margin_frac, margin_flat, walls, w, h) is True

    # 2. Starting battery 15 -> 15 - 2 = 13 < 14 => UNSAFE
    assert is_action_safe(15, target_pos, 2, chargers, move_cost, margin_frac, margin_flat, walls, w, h) is False


def test_eig_signal_triangulation_superior_to_collinear():
    """EIG should be higher at a baseline orthogonal to a prior bearing than collinear."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    world = World(cfg)
    info = world.public_info()

    belief = Belief(info)
    center_eve = (10, 10)

    # Hand-crafted prior observation: scan from (2, 10) pointing East (90 deg) towards (10, 10)
    sig_reading = SignalReading(strength=0.4, bearing_deg=90.0, dropout=False)
    L = build_signal_likelihood(sig_reading, (2, 10), info.sensor_prior, info.width, info.height, info.walls)
    belief.update(L)

    rng1 = np.random.default_rng(42)
    rng2 = np.random.default_rng(42)

    # Position A: Collinear (4, 10) - 6 cells West of target along the exact same bearing line
    collinear_pos = (4, 10)
    # Position B: Orthogonal triangulation baseline (10, 4) - 6 cells North of target (90 deg baseline)
    triangulation_pos = (10, 4)

    eig_collinear = eig_signal(belief, collinear_pos, rng1, info, mc_samples=80)
    eig_triangulation = eig_signal(belief, triangulation_pos, rng2, info, mc_samples=80)

    # Orthogonal baseline gives superior triangulation information gain
    assert eig_triangulation > eig_collinear
    assert eig_collinear >= 0.0


def test_candidate_generator_invariants():
    """Candidate generator must never return walls, unreachable cells, or exceed max_candidates."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    world = World(cfg)
    info = world.public_info()
    belief = Belief(info)
    rng = np.random.default_rng(123)

    reach_set = set(bfs_distances(info.start, info.walls, info.width, info.height).keys())

    candidates = generate_candidates(
        current_pos=info.start,
        belief=belief,
        scan_history=[info.start],
        info=info,
        rng=rng,
        max_candidates=25,
    )

    assert len(candidates) <= 25
    assert len(candidates) == len(set(candidates))  # Deduplicated
    assert info.start in candidates

    for c in candidates:
        assert c not in info.walls
        assert c in reach_set
        assert 0 <= c[0] < info.width
        assert 0 <= c[1] < info.height
