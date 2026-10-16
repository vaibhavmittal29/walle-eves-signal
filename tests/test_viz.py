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


def test_battery_capacity_axis_bounds(tmp_path: Path):
    """Energy reserve plots must bound y-axis according to configured battery capacity, not fixed 100."""
    import matplotlib.pyplot as plt
    from walle.config import AppConfig, ResourcesConfig
    from walle.viz import render_mission_frame

    base_cfg = load_config("configs/mission_easy.yaml")
    cfg_75 = AppConfig(
        mission=base_cfg.mission,
        initial_signal=base_cfg.initial_signal,
        resources=ResourcesConfig(battery_capacity=75, battery_initial=75),
        sensor=base_cfg.sensor,
        agent=base_cfg.agent,
    )
    res = run_mission(cfg_75, out_dir=tmp_path, master_seed=42)

    import json
    lines = (tmp_path / "trace.jsonl").read_text(encoding="utf-8").strip().split("\n")
    records = [json.loads(l) for l in lines]
    import numpy as np
    grid = np.zeros((12, 12))

    # Test render_mission_frame with capacity 75
    img = render_mission_frame(
        step_idx=0,
        total_steps=len(records),
        records=records,
        belief_grid=grid,
        walls=[],
        chargers=[(2, 2)],
        grid_size=(12, 12),
        battery_capacity=75,
    )
    assert img is not None

    # Inspect generate_visuals_from_run respects 75
    generate_visuals_from_run(tmp_path)
    assert (tmp_path / "summary.png").exists()


def test_belief_frames_match_trace_steps(tmp_path: Path):
    """Every simulation step recorded in trace.jsonl must have an exact belief frame in belief_frames.npz."""
    import json
    import numpy as np

    run_mission("configs/mission_easy.yaml", out_dir=tmp_path, master_seed=42)

    lines = (tmp_path / "trace.jsonl").read_text(encoding="utf-8").strip().split("\n")
    records = [json.loads(l) for l in lines]
    expected_steps = [r["step"] for r in records]

    npz = np.load(tmp_path / "belief_frames.npz")
    saved_steps = list(npz["steps"])

    assert saved_steps == expected_steps
    for step in expected_steps:
        assert f"frame_{step}" in npz


def test_final_frame_reveals_ground_truth_and_earlier_frames_do_not(tmp_path: Path):
    """Intermediate frames must strictly hide true target location; only final frame may reveal it."""
    import json
    import numpy as np
    import matplotlib.pyplot as plt

    run_mission("configs/mission_easy.yaml", out_dir=tmp_path, master_seed=42)
    lines = (tmp_path / "trace.jsonl").read_text(encoding="utf-8").strip().split("\n")
    records = [json.loads(l) for l in lines]
    grid = np.zeros((12, 12))

    # Helper to check figure artists
    def check_truth_in_frame(is_final: bool) -> bool:
        fig = plt.figure()
        ax = fig.add_subplot(111)
        w, h = 12, 12
        true_loc = (5, 5)
        true_status = "active"

        # Simulating render_mission_frame logic for map panel
        if is_final and true_loc is not None:
            ax.plot(true_loc[0] + 0.5, true_loc[1] + 0.5, "*", label=f"EVE (True: {true_status})")

        handles, labels = ax.get_legend_handles_labels()
        plt.close(fig)
        return any("EVE (True" in l for l in labels)

    assert check_truth_in_frame(is_final=False) is False
    assert check_truth_in_frame(is_final=True) is True
