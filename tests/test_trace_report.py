"""Unit tests verifying trace logging format, replayability, report generation, and determinism."""

import json
from pathlib import Path
import pytest

from walle.actions import Action, ActionType
from walle.config import load_config
from walle.environment import Environment
from walle.report import generate_report
from walle.runner import run_mission


def test_trace_jsonl_schema(tmp_path: Path):
    """Every step must produce exactly one valid JSON line containing all mandatory schema keys."""
    out_dir = tmp_path / "test_run"
    res = run_mission("configs/mission_easy.yaml", out_dir=out_dir)

    jsonl_path = out_dir / "trace.jsonl"
    assert jsonl_path.exists()

    required_top_keys = {
        "step",
        "tick",
        "strategy",
        "strategy_change",
        "state_before",
        "decision",
        "observation",
        "belief_after",
    }
    required_state_keys = {"pos", "battery", "time_left", "reserve"}
    required_decision_keys = {"action", "plan", "top_candidates", "reasoning"}
    required_obs_keys = {"pos", "battery", "signal", "clues", "bumped"}
    required_belief_keys = {
        "map",
        "map_prob",
        "entropy_bits",
        "info_gain_bits",
        "location_confidence",
        "status_probs",
    }

    lines = [line.strip() for line in open(jsonl_path, "r", encoding="utf-8") if line.strip()]
    assert len(lines) == res.steps

    for line_idx, line in enumerate(lines, start=1):
        record = json.loads(line)
        assert required_top_keys.issubset(record.keys()), f"Line {line_idx} missing top keys"
        assert required_state_keys.issubset(record["state_before"].keys())
        assert required_decision_keys.issubset(record["decision"].keys())
        assert required_obs_keys.issubset(record["observation"].keys())
        assert required_belief_keys.issubset(record["belief_after"].keys())


def test_trace_replay_reproduces_identical_observations(tmp_path: Path):
    """Replaying logged actions on a fresh environment with same seed reproduces identical observations."""
    out_dir = tmp_path / "replay_run"
    res = run_mission("configs/mission_easy.yaml", out_dir=out_dir)

    jsonl_path = out_dir / "trace.jsonl"
    lines = [json.loads(line) for line in open(jsonl_path, "r", encoding="utf-8") if line.strip()]

    # Fresh environment with same config
    cfg = load_config("configs/mission_easy.yaml")
    env = Environment(cfg)
    _, obs = env.reset()

    for idx, rec in enumerate(lines):
        act_name = rec["decision"]["action"]
        act_type = ActionType(act_name)
        if act_type == ActionType.DECLARE:
            dec_pos = rec["decision"]["plan"]  # e.g. DECLARE
            map_x, map_y = rec["belief_after"]["map"]
            action = Action(type=act_type, declare_x=map_x, declare_y=map_y, declare_status="active")
        elif act_type == ActionType.SCAN_AREA:
            action = Action(type=act_type, radius=2)
        else:
            action = Action(type=act_type)

        obs = env.step(action)
        expected_pos = tuple(rec["observation"]["pos"])
        expected_battery = rec["observation"]["battery"]
        assert obs.position == expected_pos
        assert obs.battery == expected_battery


def test_report_contains_all_eight_sections(tmp_path: Path):
    """Generated report.md must contain all 8 required sections with matching metrics."""
    out_dir = tmp_path / "report_run"
    res = run_mission("configs/mission_easy.yaml", out_dir=out_dir)

    md_path = out_dir / "report.md"
    json_path = out_dir / "report.json"
    assert md_path.exists()
    assert json_path.exists()

    md_text = md_path.read_text(encoding="utf-8")

    # Verify all 8 headers exist
    expected_sections = [
        "## 1. Mission Summary",
        "## 2. Final Inferred Answer",
        "## 3. Evidence Table",
        "## 4. Resource Utilization",
        "## 5. Strategy Timeline",
        "## 6. Recommended Next Step",
        "## 7. Ground Truth Validation (Simulation Only)",
        "## 8. Limitations and Assumptions",
    ]
    for sec in expected_sections:
        assert sec in md_text, f"Report missing section '{sec}'"

    # Verify JSON content matches RunResult
    rep_json = json.loads(json_path.read_text(encoding="utf-8"))
    assert rep_json["mission_summary"]["config_name"] == res.config_name
    assert rep_json["mission_summary"]["total_steps"] == res.steps
    assert rep_json["resource_utilization"]["battery_used"] == res.battery_used
    assert rep_json["ground_truth_check"]["success"] == res.success


def test_recommended_next_step_rules(tmp_path: Path):
    """Recommended next step text differs correctly between confident and unconfident cases."""
    from walle.config import load_config
    from walle.world import World
    from walle.belief import Belief

    cfg = load_config("configs/mission_easy.yaml")
    world = World(cfg)
    info = world.public_info()
    belief = Belief(info)

    # 1. Low confidence belief (uniform)
    out_dir_unconf = tmp_path / "unconf"
    res = run_mission("configs/mission_easy.yaml", out_dir=out_dir_unconf)
    _, md_unconf = generate_report(res, [], [], out_dir_unconf, belief=belief)
    txt_unconf = md_unconf.read_text(encoding="utf-8")
    assert "Target localization confidence is moderate" in txt_unconf

    # 2. High confidence belief (concentrated at declared location)
    out_dir_conf = tmp_path / "conf"
    res_conf = run_mission("configs/mission_easy.yaml", out_dir=out_dir_conf)
    belief._grid.fill(0.0)
    dec_x, dec_y = res_conf.declared_location
    belief._grid[dec_y, dec_x, 0] = 1.0
    _, md_conf = generate_report(res_conf, [], [], out_dir_conf, belief=belief)
    txt_conf = md_conf.read_text(encoding="utf-8")
    assert "Dispatch WALL-E directly to target coordinates" in txt_conf


def test_determinism_byte_identical_trace(tmp_path: Path):
    """Running identical seed twice produces byte-identical trace.jsonl."""
    dir1 = tmp_path / "run_1"
    dir2 = tmp_path / "run_2"

    run_mission("configs/mission_medium.yaml", out_dir=dir1)
    run_mission("configs/mission_medium.yaml", out_dir=dir2)

    bytes1 = (dir1 / "trace.jsonl").read_bytes()
    bytes2 = (dir2 / "trace.jsonl").read_bytes()
    assert bytes1 == bytes2, "Traces for identical seed diverged!"
