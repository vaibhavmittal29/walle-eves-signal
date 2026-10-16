"""Robustness, edge-case scenarios, and fuzz testing for the autonomous agent."""

from pathlib import Path
import pytest

from walle.config import (
    AgentConfig,
    AgentSafety,
    AgentThresholds,
    AppConfig,
    CluesConfig,
    CostsConfig,
    DecoyConfig,
    EveConfig,
    GridConfig,
    InitialSignalConfig,
    MissionSectionConfig,
    ObstaclesConfig,
    ResourcesConfig,
    SensorConfig,
    load_config,
)
from walle.runner import run_mission


def test_edge_cases_execution(tmp_path: Path):
    """Verify that all 6 edge case missions execute safely to completion without crashing."""
    edge_files = [
        "edge_tiny_battery.yaml",
        "edge_start_adjacent_to_eve.yaml",
        "edge_eve_behind_walls.yaml",
        "edge_no_bearing.yaml",
        "edge_zero_clues.yaml",
        "edge_very_noisy.yaml",
    ]

    for fname in edge_files:
        p = Path("tests/data") / fname
        out = tmp_path / fname.replace(".yaml", "")
        res = run_mission(p, out_dir=out)

        assert res.outcome != "stranded", f"Agent stranded on edge case {fname}!"
        assert res.battery_used >= 0
        assert res.ticks_used > 0
        assert (out / "report.md").exists()
        assert (out / "trace.jsonl").exists()


def test_fuzz_200_random_configs_never_stranded(tmp_path: Path):
    """Fuzz test: 200 randomized mission configurations, asserting no crashes and 0% stranded rate."""
    for fuzz_seed in range(200):
        grid_w = 12 + (fuzz_seed % 7)   # 12 to 18
        grid_h = 12 + (fuzz_seed % 5)   # 12 to 16
        battery = 50 + (fuzz_seed % 50) # 50 to 99
        density = 0.05 + 0.01 * (fuzz_seed % 8) # 0.05 to 0.12

        m_cfg = MissionSectionConfig(
            name=f"fuzz_{fuzz_seed}",
            seed=fuzz_seed,
            grid=GridConfig(width=grid_w, height=grid_h),
            start=(1, 1),
            obstacles=ObstaclesConfig(mode="random", density=density),
            chargers=[(1, 1), (grid_w - 2, grid_h - 2)],
            eve=EveConfig(location="random", status="random", mobility="static", min_distance_from_start=5),
            clues=CluesConfig(count=3, placement="random"),
        )
        res_cfg = ResourcesConfig(
            battery_capacity=battery,
            battery_initial=battery,
            time_budget=150,
        )
        ag_cfg = AgentConfig(
            type="bayes_planner",
            seed=fuzz_seed + 1000,
            mc_samples=15,       # Fast sampling for 200-fuzz run
            max_candidates=10,
            thresholds=AgentThresholds(track=0.45, verify=0.65, declare_location=0.80, declare_status=0.65),
            safety=AgentSafety(margin_fraction=0.10, margin_flat=3),
        )

        cfg = AppConfig(
            mission=m_cfg,
            initial_signal=InitialSignalConfig(mode="none", bearing_deg=None, coordinates=None, strength=None),
            resources=res_cfg,
            sensor=SensorConfig(noise_scale=1.0),
            agent=ag_cfg,
        )

        # Run mission
        res = run_mission(cfg, master_seed=fuzz_seed)

        # Safety & integrity assertions
        assert res.outcome != "stranded", f"Agent stranded on fuzz configuration {fuzz_seed}!"
        assert res.min_battery_margin >= 0, f"Negative battery margin on fuzz seed {fuzz_seed}!"
        assert res.battery_used >= 0, f"Negative battery used on fuzz seed {fuzz_seed}!"
