"""Unit tests for world generation, connectivity, and determinism."""

from pathlib import Path
import pytest

from walle.config import load_config
from walle.geometry import distance
from walle.world import World, check_connectivity


def test_seed_determinism():
    """Identical seeds must yield identical world geometry, EVE position, status, and clues."""
    cfg1 = load_config(Path("configs/mission_medium.yaml"))
    cfg2 = load_config(Path("configs/mission_medium.yaml"))

    w1 = World(cfg1)
    w2 = World(cfg2)

    gt1 = w1.ground_truth()
    gt2 = w2.ground_truth()

    assert gt1.eve_location == gt2.eve_location
    assert gt1.eve_status == gt2.eve_status
    assert len(gt1.clues) == len(gt2.clues)
    for c1, c2 in zip(gt1.clues, gt2.clues):
        assert c1.position == c2.position
        assert c1.clue_type == c2.clue_type
        assert c1.ground_truth_value == c2.ground_truth_value

    assert w1.public_info().walls == w2.public_info().walls


def test_seed_divergence():
    """Different seeds must yield different worlds."""
    cfg1 = load_config(Path("configs/mission_medium.yaml"))
    cfg2 = load_config(Path("configs/mission_hard_decoys.yaml"))

    w1 = World(cfg1)
    w2 = World(cfg2)

    # Different maps or eve locations
    assert (
        w1.ground_truth().eve_location != w2.ground_truth().eve_location
        or w1.public_info().walls != w2.public_info().walls
    )


def test_full_connectivity():
    """All free cells must be reachable from the start cell via 4-connected BFS."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    world = World(cfg)
    pub = world.public_info()

    connected, reachable = check_connectivity(pub.start, pub.walls, pub.width, pub.height)
    assert connected is True
    assert len(reachable) == pub.width * pub.height - len(pub.walls)


def test_eve_and_clues_never_in_walls():
    """EVE, chargers, and clues must never be placed inside walls."""
    for cfg_name in ("mission_easy.yaml", "mission_medium.yaml", "mission_hard_decoys.yaml"):
        cfg = load_config(Path("configs") / cfg_name)
        world = World(cfg)
        pub = world.public_info()
        gt = world.ground_truth()

        assert gt.eve_location not in pub.walls
        assert pub.start not in pub.walls
        for c in pub.chargers:
            assert c not in pub.walls
        for clue in gt.clues:
            assert clue.position not in pub.walls
        for decoy in gt.decoys:
            assert decoy not in pub.walls


def test_ascii_debug_render():
    """Verify ASCII map rendering produces expected characters."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    world = World(cfg)
    ascii_map = world.render_ascii_debug()

    assert "Legend:" in ascii_map
    assert "EVE Ground Truth:" in ascii_map
    assert "S" in ascii_map  # Start
    assert "E" in ascii_map  # EVE
