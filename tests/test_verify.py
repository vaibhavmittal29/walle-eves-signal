"""Tests for Phase 9: Production trace replay verifier."""

import json
from pathlib import Path
import pytest

from walle.config import load_config
from walle.runner import run_mission
from walle.verify import VerificationResult, verify_run
from walle.cli import main as cli_main


def test_verify_clean_run(tmp_path):
    """A real successful mission run must verify cleanly with exit code 0 and no errors."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    run_mission(config_path=cfg, agent_type="bayes_planner", out_dir=tmp_path, master_seed=7)

    result = verify_run(tmp_path)
    assert result.is_valid is True
    assert len(result.errors) == 0
    assert result.steps_verified > 0

    # Test CLI entrypoint on clean run
    exit_code = cli_main(["verify", str(tmp_path)])
    assert exit_code == 0


def test_verify_catches_tampered_battery(tmp_path):
    """Mutating a battery value in trace.jsonl must fail verification with specific energy error."""
    cfg = load_config(Path("configs/mission_easy.yaml"))
    run_mission(config_path=cfg, agent_type="bayes_planner", out_dir=tmp_path, master_seed=42)

    # Tamper with trace.jsonl
    trace_file = tmp_path / "trace.jsonl"
    lines = trace_file.read_text(encoding="utf-8").strip().split("\n")
    rec = json.loads(lines[1])
    # Add unearned battery
    if "battery" in rec:
        rec["battery"] += 50
    if "observation" in rec and "battery" in rec["observation"]:
        rec["observation"]["battery"] += 50
    lines[1] = json.dumps(rec)
    trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = verify_run(tmp_path)
    assert result.is_valid is False
    assert any("battery" in err.lower() or "energy" in err.lower() for err in result.errors)

    exit_code = cli_main(["verify", str(tmp_path)])
    assert exit_code != 0


def test_verify_catches_wall_clipping_or_teleport(tmp_path):
    """Mutating a position in trace.jsonl to teleport or clip a wall must fail verification."""
    cfg = load_config(Path("configs/mission_easy.yaml"))
    run_mission(config_path=cfg, agent_type="bayes_planner", out_dir=tmp_path, master_seed=42)

    trace_file = tmp_path / "trace.jsonl"
    lines = trace_file.read_text(encoding="utf-8").strip().split("\n")
    rec = json.loads(lines[1])
    # Teleport to arbitrary distant cell
    if "position" in rec:
        rec["position"] = [rec["position"][0] + 5, rec["position"][1] + 5]
    if "observation" in rec and "pos" in rec["observation"]:
        rec["observation"]["pos"] = [rec["observation"]["pos"][0] + 5, rec["observation"]["pos"][1] + 5]
    lines[1] = json.dumps(rec)
    trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = verify_run(tmp_path)
    assert result.is_valid is False
    assert any("transition" in err.lower() or "position" in err.lower() or "wall" in err.lower() or "teleport" in err.lower() for err in result.errors)


def test_verify_catches_illegal_recharge(tmp_path):
    """Executing a recharge off a charging station must fail verification."""
    cfg = load_config(Path("configs/mission_medium.yaml"))
    run_mission(config_path=cfg, agent_type="bayes_planner", out_dir=tmp_path, master_seed=7)

    trace_file = tmp_path / "trace.jsonl"
    lines = trace_file.read_text(encoding="utf-8").strip().split("\n")
    
    # Force step 1 to be an illegal recharge off-charger
    rec = json.loads(lines[1])
    if "action" in rec:
        rec["action"] = "RECHARGE"
    if "decision" in rec:
        rec["decision"]["action"] = "RECHARGE"
        if "action_params" in rec["decision"]:
            rec["decision"]["action_params"]["type"] = "RECHARGE"
    if "observation" in rec:
        rec["observation"]["pos"] = [0, 0]  # off-charger cell
        rec["observation"]["action_succeeded"] = True
    lines[1] = json.dumps(rec)
    trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = verify_run(tmp_path)
    assert result.is_valid is False
    assert any("recharge" in err.lower() or "charger" in err.lower() for err in result.errors)


def test_verify_catches_tampered_declaration(tmp_path):
    """Inconsistency between final declaration and report.json must fail verification."""
    cfg = load_config(Path("configs/mission_easy.yaml"))
    run_mission(config_path=cfg, agent_type="bayes_planner", out_dir=tmp_path, master_seed=42)

    # Tamper with report.json final inferred location
    report_file = tmp_path / "report.json"
    rep = json.loads(report_file.read_text(encoding="utf-8"))
    rep["final_answer"]["inferred_location"] = [999, 999]
    report_file.write_text(json.dumps(rep, indent=2), encoding="utf-8")

    result = verify_run(tmp_path)
    assert result.is_valid is False
    assert any("declared" in err.lower() or "location" in err.lower() or "final" in err.lower() for err in result.errors)
