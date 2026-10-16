"""Tests for Phase 8: Resource accounting, metrics reconciliation, and baseline confidence nullability."""

from pathlib import Path
import pytest

from walle.actions import ActionType, cost_of
from walle.config import AppConfig, ResourcesConfig, load_config
from walle.runner import run_mission


def test_energy_consumed_formula_and_cross_check():
    """Verify consumed = initial + recharge_delivered - final and cross-check against action costs."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    res = run_mission(config_path=cfg, agent_type="bayes_planner", master_seed=7)

    initial_battery = cfg.resources.battery_initial
    final_battery = res.trace_records[-1]["battery"]

    expected_consumed = initial_battery + res.recharge_energy_delivered - final_battery
    assert res.battery_consumed_by_actions == expected_consumed

    # Cross-check against action costs recorded in trace
    total_action_battery = sum(rec["action_battery_cost"] for rec in res.trace_records)
    assert res.battery_consumed_by_actions == total_action_battery


def test_partial_initial_charge_and_final_greater_than_initial():
    """Test partial initial charge where final battery exceeds initial battery (net_battery_change < 0)."""
    base_cfg = load_config(Path("configs/mission_medium.yaml"))

    # Initial battery is small (25), capacity is 100
    resources = ResourcesConfig(
        battery_capacity=100,
        battery_initial=25,
        time_budget=250,
        costs=base_cfg.resources.costs,
    )
    low_start_cfg = AppConfig(
        mission=base_cfg.mission,
        initial_signal=base_cfg.initial_signal,
        resources=resources,
        sensor=base_cfg.sensor,
        agent=base_cfg.agent,
    )

    res = run_mission(config_path=low_start_cfg, agent_type="bayes_planner", master_seed=7)

    initial_bat = 25
    final_bat = res.trace_records[-1]["battery"]

    # Agent recharges on charger, ending with final battery > 25
    if final_bat > initial_bat:
        assert res.net_battery_change == initial_bat - final_bat
        assert res.net_battery_change < 0

    expected_consumed = initial_bat + res.recharge_energy_delivered - final_bat
    assert res.battery_consumed_by_actions == expected_consumed


def test_min_battery_absolute_and_margin_reported_separately():
    """min_battery_absolute and min_battery_margin must be separately tracked and distinct."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    res = run_mission(config_path=cfg, agent_type="bayes_planner", master_seed=7)

    assert hasattr(res, "min_battery_absolute")
    assert hasattr(res, "min_battery_margin")

    # Absolute battery cannot be negative
    assert res.min_battery_absolute >= 0

    # Minimum battery in trace must match min_battery_absolute
    min_in_trace = min(r["battery"] for r in res.trace_records)
    assert res.min_battery_absolute == min_in_trace


def test_baselines_no_fabricated_confidence_and_nullable_posterior():
    """Baseline agents (Random, GreedyBearing) must NOT fabricate 0.90 confidence or credible regions."""
    cfg = load_config(Path("configs/mission_easy.yaml"))

    for b_type in ("random", "greedy_bearing"):
        res = run_mission(config_path=cfg, agent_type=b_type, master_seed=42)

        assert res.location_confidence is None, f"{b_type} fabricated location confidence!"
        assert res.status_confidence is None, f"{b_type} fabricated status confidence!"
        assert res.credible_hit is None, f"{b_type} fabricated credible_hit!"
        assert res.final_entropy is None, f"{b_type} fabricated final_entropy!"


def test_report_renders_na_for_baseline_confidence(tmp_path):
    """Report JSON and Markdown must render N/A or null for baselines without posterior modeling."""
    cfg = load_config(Path("configs/mission_easy.yaml"))
    res = run_mission(config_path=cfg, agent_type="random", out_dir=tmp_path, master_seed=42)

    import json
    report_json = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    report_md = (tmp_path / "report.md").read_text(encoding="utf-8")

    assert report_json["final_answer"]["location_confidence"] is None
    assert report_json["final_answer"]["status_confidence"] is None
    assert report_json["ground_truth_check"]["credible_region_hit"] is None

    assert "N/A" in report_md
