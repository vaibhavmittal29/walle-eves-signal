"""Unit tests for ASCII rendering, Matplotlib summary charts, and animated GIF generation."""

from pathlib import Path
from PIL import Image
import pytest

from walle.belief import Belief
from walle.config import load_config
from walle.runner import run_mission
from walle.viz import generate_visuals_from_run, render_ascii
from walle.world import World


def test_ascii_render_contains_landmarks():
    """ASCII renderer must display walls, chargers, agent, and belief ramp characters."""
    cfg = load_config("configs/mission_medium.yaml")
    world = World(cfg)
    info = world.public_info()
    gt = world.ground_truth()
    belief = Belief(info)

    ascii_out = render_ascii(
        position=info.start,
        belief=belief,
        info=info,
        show_truth=False,
    )

    assert "W" in ascii_out  # WALL-E
    assert "C" in ascii_out  # Charger
    assert "#" in ascii_out  # Wall
    assert "Legend:" in ascii_out
    assert "Belief ramp:" in ascii_out

    # When show_truth is True, EVE is visible
    ascii_with_truth = render_ascii(
        position=info.start,
        belief=belief,
        info=info,
        show_truth=True,
        ground_truth=gt,
    )
    assert "E" in ascii_with_truth
    assert f"{gt.eve_location}" in ascii_with_truth


def test_visuals_generation_creates_valid_png_and_gif(tmp_path: Path):
    """generate_visuals_from_run must generate non-empty, openable summary.png and run.gif."""
    out_dir = tmp_path / "viz_test"
    run_mission("configs/mission_easy.yaml", out_dir=out_dir)

    summary_path, gif_path = generate_visuals_from_run(out_dir)

    assert summary_path.exists()
    assert gif_path.exists()
    assert (out_dir / "path_map.png").exists()
    assert (out_dir / "path_3d.png").exists()
    assert (out_dir / "belief_evolution.png").exists()
    assert (out_dir / "metrics_dashboard.png").exists()
    assert (out_dir / "predictions.json").exists()
    assert (out_dir / "run.log").exists()

    # Open with Pillow to verify image validity
    with Image.open(summary_path) as s_img:
        assert s_img.size[0] > 500
        assert s_img.size[1] > 200
        assert s_img.format == "PNG"

    with Image.open(out_dir / "path_map.png") as pm_img:
        assert pm_img.size[0] > 500
        assert pm_img.format == "PNG"

    with Image.open(out_dir / "path_3d.png") as p3_img:
        assert p3_img.size[0] > 500
        assert p3_img.format == "PNG"

    with Image.open(out_dir / "belief_evolution.png") as be_img:
        assert be_img.size[0] > 500
        assert be_img.format == "PNG"

    with Image.open(out_dir / "metrics_dashboard.png") as md_img:
        assert md_img.size[0] > 500
        assert md_img.format == "PNG"

    with Image.open(gif_path) as g_img:
        assert g_img.is_animated is True
        assert g_img.n_frames >= 2
        assert g_img.format == "GIF"
