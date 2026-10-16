"""Production trace replay verifier.

Independently loads a mission's trace.jsonl, report.json, and configuration to rigorously verify:
1. Action-by-action energy and time cost accounting against the config's cost table.
2. The agent's stated reserve at each step matches return_reserve(pos).
3. Every move transition was to a valid adjacent cell (no wall-clipping, no teleports).
4. Every recharge occurred on a cell that is actually a charger.
5. The safe-return invariant held: battery >= return_reserve at every field step.
6. Final declared location/status match report.json.
7. Any corrupt or inconsistent step produces a specific diagnostic error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from walle.actions import ActionType
from walle.config import AppConfig, load_config
from walle.planner import return_reserve


@dataclass
class VerificationResult:
    """Result of an independent trace verification audit."""

    is_valid: bool
    errors: List[str]
    steps_verified: int
    warnings: List[str] = field(default_factory=list)


def verify_run(run_dir: Union[str, Path]) -> VerificationResult:
    """Rigorously verify an execution trace and mission report.

    Args:
        run_dir: Directory containing trace.jsonl, report.json, and optionally config.yaml.

    Returns:
        VerificationResult with validity flag, step count, and diagnostic errors.
    """
    run_path = Path(run_dir)
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Check required artifact presence
    trace_path = run_path / "trace.jsonl"
    report_path = run_path / "report.json"

    if not trace_path.exists():
        return VerificationResult(
            is_valid=False,
            errors=[f"Missing required artifact: {trace_path}"],
            steps_verified=0,
        )

    if not report_path.exists():
        return VerificationResult(
            is_valid=False,
            errors=[f"Missing required artifact: {report_path}"],
            steps_verified=0,
        )

    # 2. Load report.json
    try:
        report_data = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return VerificationResult(
            is_valid=False,
            errors=[f"Corrupt or unreadable report.json: {exc}"],
            steps_verified=0,
        )

    # 3. Locate and load configuration
    cfg: Optional[AppConfig] = None
    config_local = run_path / "config.yaml"

    if config_local.exists():
        try:
            cfg = load_config(config_local)
        except Exception as exc:
            warnings.append(f"Could not load local config.yaml: {exc}")

    if cfg is None:
        cfg_name = report_data.get("mission_summary", {}).get("config_name", "")
        candidate_paths = [
            Path(f"configs/{cfg_name}.yaml"),
            Path(f"configs/{cfg_name}"),
            Path(f"configs/mission_{cfg_name}.yaml"),
        ]
        for cp in candidate_paths:
            if cp.exists():
                try:
                    cfg = load_config(cp)
                    break
                except Exception:
                    pass

    env_meta = report_data.get("environment", {})
    grid_w, grid_h = env_meta.get("grid_size", [20, 20])
    chargers = [tuple(c) for c in env_meta.get("chargers", [(2, 2)])]
    walls = [tuple(w) for w in env_meta.get("walls", [])]

    if cfg is not None:
        grid_w, grid_h = cfg.mission.grid.width, cfg.mission.grid.height
        if not chargers:
            chargers = [tuple(c) for c in cfg.mission.chargers]
        if not walls and cfg.mission.obstacles.walls:
            walls = [tuple(w) for w in cfg.mission.obstacles.walls]

    # Costs and margins
    if cfg is not None:
        cost_table = cfg.resources.costs.to_cost_table()
        margin_fraction = cfg.agent.safety.margin_fraction
        margin_flat = cfg.agent.safety.margin_flat
        max_bat_capacity = cfg.resources.battery_capacity
    else:
        from walle.config import CostsConfig
        cost_table = CostsConfig().to_cost_table()
        margin_fraction = 0.15
        margin_flat = 3
        max_bat_capacity = 100

    move_bat_cost = cost_table.move.battery
    move_time_cost = cost_table.move.time
    scan_sig_bat_cost = cost_table.scan_signal.battery
    scan_sig_time_cost = cost_table.scan_signal.time
    declare_bat_cost = 0
    declare_time_cost = 1
    recharge_time_cost = cost_table.recharge.time

    # 4. Parse trace.jsonl lines
    lines = [l.strip() for l in trace_path.read_text(encoding="utf-8").strip().split("\n") if l.strip()]
    if not lines:
        return VerificationResult(
            is_valid=False,
            errors=["Empty trace.jsonl: no simulation steps recorded."],
            steps_verified=0,
        )

    records: List[Dict[str, Any]] = []
    for idx, line in enumerate(lines, start=1):
        try:
            records.append(json.loads(line))
        except Exception as exc:
            errors.append(f"Line {idx} in trace.jsonl is not valid JSON: {exc}")

    if errors:
        return VerificationResult(is_valid=False, errors=errors, steps_verified=0)

    # 5. Step-by-step trace replay and invariant verification
    step_count = len(records)
    current_pos: Optional[Tuple[int, int]] = None
    current_battery: Optional[int] = None
    current_time_left: Optional[int] = None

    move_deltas = {
        "MOVE_N": (0, -1),
        "MOVE_S": (0, 1),
        "MOVE_E": (1, 0),
        "MOVE_W": (-1, 0),
    }

    for step_idx, rec in enumerate(records, start=1):
        # Extract state_before
        sb = rec.get("state_before", {})
        pos_before = tuple(sb.get("pos", [0, 0])) if "pos" in sb else current_pos
        bat_before = sb.get("battery", current_battery)
        time_before = sb.get("time_left", current_time_left)

        if current_pos is None:
            current_pos = pos_before
            current_battery = bat_before
            current_time_left = time_before

        # Check state continuity
        if current_pos is not None and pos_before != current_pos:
            errors.append(
                f"Step {step_idx}: Discontinuous agent position: expected {current_pos}, got {pos_before} in state_before."
            )
        if current_battery is not None and bat_before != current_battery:
            errors.append(
                f"Step {step_idx}: Discontinuous battery: expected {current_battery}, got {bat_before} in state_before."
            )
        if current_time_left is not None and time_before != current_time_left:
            errors.append(
                f"Step {step_idx}: Discontinuous time left: expected {current_time_left}, got {time_before} in state_before."
            )

        # Extract decision and action
        dec = rec.get("decision", {})
        action_name = dec.get("action") or rec.get("action", "")
        action_params = dec.get("action_params", {})
        radius = action_params.get("radius", 1)

        # Extract observation
        obs = rec.get("observation", {})
        pos_after = tuple(obs.get("pos", obs.get("position", current_pos)))
        bat_after = obs.get("battery", current_battery)
        time_after = obs.get("time_left", current_time_left)
        bumped = obs.get("bumped", False)
        succeeded = obs.get("action_succeeded", True)

        # Verify action-by-action energy and transition mechanics
        if action_name in move_deltas:
            dx, dy = move_deltas[action_name]
            intended_x = current_pos[0] + dx
            intended_y = current_pos[1] + dy
            is_wall_or_oob = (
                intended_x < 0
                or intended_x >= grid_w
                or intended_y < 0
                or intended_y >= grid_h
                or (intended_x, intended_y) in walls
            )

            if is_wall_or_oob:
                # Must be bumped and remain at current position
                if not bumped:
                    errors.append(
                        f"Step {step_idx}: Move {action_name} towards obstacle/boundary ({intended_x}, {intended_y}) did not report bumped=True."
                    )
                if pos_after != current_pos:
                    errors.append(
                        f"Step {step_idx}: Wall-clipping or OOB transition on {action_name}: agent moved to illegal position {pos_after}."
                    )
            else:
                if not bumped:
                    if pos_after != (intended_x, intended_y):
                        errors.append(
                            f"Step {step_idx}: Invalid move transition: {current_pos} -> {pos_after} on {action_name} (expected ({intended_x}, {intended_y}))."
                        )
                else:
                    if pos_after != current_pos:
                        errors.append(
                            f"Step {step_idx}: Agent reported bumped=True but changed position from {current_pos} to {pos_after}."
                        )

            # Battery and time accounting
            expected_bat = max(0, current_battery - move_bat_cost)
            expected_time = current_time_left - move_time_cost
            if bat_after != expected_bat:
                errors.append(
                    f"Step {step_idx}: Battery accounting error on {action_name}: expected {expected_bat}, observed {bat_after}."
                )
            if time_after != expected_time:
                errors.append(
                    f"Step {step_idx}: Time accounting error on {action_name}: expected {expected_time}, observed {time_after}."
                )

        elif action_name == "SCAN_SIGNAL":
            if pos_after != current_pos:
                errors.append(
                    f"Step {step_idx}: Position changed on SCAN_SIGNAL: {current_pos} -> {pos_after}."
                )
            expected_bat = max(0, current_battery - scan_sig_bat_cost)
            expected_time = current_time_left - scan_sig_time_cost
            if bat_after != expected_bat:
                errors.append(
                    f"Step {step_idx}: Battery accounting error on SCAN_SIGNAL: expected {expected_bat}, observed {bat_after}."
                )
            if time_after != expected_time:
                errors.append(
                    f"Step {step_idx}: Time accounting error on SCAN_SIGNAL: expected {expected_time}, observed {time_after}."
                )

        elif action_name == "SCAN_AREA":
            if pos_after != current_pos:
                errors.append(
                    f"Step {step_idx}: Position changed on SCAN_AREA: {current_pos} -> {pos_after}."
                )
            area_bat_cost = 2 + 2 * radius
            area_time_cost = 1 + radius
            expected_bat = max(0, current_battery - area_bat_cost)
            expected_time = current_time_left - area_time_cost
            if bat_after != expected_bat:
                errors.append(
                    f"Step {step_idx}: Battery accounting error on SCAN_AREA(r={radius}): expected {expected_bat}, observed {bat_after}."
                )
            if time_after != expected_time:
                errors.append(
                    f"Step {step_idx}: Time accounting error on SCAN_AREA(r={radius}): expected {expected_time}, observed {time_after}."
                )

        elif action_name == "RECHARGE":
            if pos_after != current_pos:
                errors.append(
                    f"Step {step_idx}: Position changed on RECHARGE: {current_pos} -> {pos_after}."
                )
            # Must be strictly on a charger cell
            if current_pos not in chargers:
                errors.append(
                    f"Step {step_idx}: Illegal RECHARGE attempted off-charger at {current_pos}."
                )
            else:
                if bat_after < current_battery:
                    errors.append(
                        f"Step {step_idx}: Recharge docking decreased battery from {current_battery} to {bat_after}."
                    )
                if bat_after > max_bat_capacity:
                    errors.append(
                        f"Step {step_idx}: Recharge exceeded maximum battery capacity: {bat_after} > {max_bat_capacity}."
                    )

            expected_time = current_time_left - recharge_time_cost
            if time_after != expected_time:
                errors.append(
                    f"Step {step_idx}: Time accounting error on RECHARGE: expected {expected_time}, observed {time_after}."
                )

        elif action_name == "DECLARE":
            if pos_after != current_pos:
                errors.append(
                    f"Step {step_idx}: Position changed on DECLARE: {current_pos} -> {pos_after}."
                )
            expected_bat = max(0, current_battery - declare_bat_cost)
            expected_time = current_time_left - declare_time_cost
            if bat_after != expected_bat:
                errors.append(
                    f"Step {step_idx}: Battery accounting error on DECLARE: expected {expected_bat}, observed {bat_after}."
                )
            if time_after != expected_time:
                errors.append(
                    f"Step {step_idx}: Time accounting error on DECLARE: expected {expected_time}, observed {time_after}."
                )

        # Check return reserve consistency
        true_reserve = return_reserve(
            pos=current_pos,
            chargers=chargers,
            move_battery_cost=move_bat_cost,
            margin_fraction=margin_fraction,
            margin_flat=margin_flat,
            walls=walls,
            width=grid_w,
            height=grid_h,
        )

        stated_reserve = sb.get("reserve")
        if stated_reserve is not None and abs(stated_reserve - true_reserve) > 1:
            errors.append(
                f"Step {step_idx}: Stated reserve {stated_reserve} does not match computed reserve {true_reserve} at {current_pos}."
            )

        # Check safe-return invariant: battery >= return_reserve while in the field
        if current_pos not in chargers and current_battery < true_reserve:
            errors.append(
                f"Step {step_idx}: Safe-return invariant violated at {current_pos}: battery {current_battery} < return_reserve {true_reserve}."
            )

        # Advance state
        current_pos = pos_after
        current_battery = bat_after
        current_time_left = time_after

    # 6. Check report.json final declaration consistency
    final_rec = records[-1]
    final_dec = final_rec.get("decision", {})
    final_action = final_dec.get("action") or final_rec.get("action")

    if final_action == "DECLARE":
        f_params = final_dec.get("action_params", {})
        dec_x = f_params.get("declare_x", current_pos[0] if current_pos else 0)
        dec_y = f_params.get("declare_y", current_pos[1] if current_pos else 0)
        dec_status = f_params.get("declare_status", "active")

        rep_ans = report_data.get("final_answer", {})
        rep_loc = rep_ans.get("inferred_location")
        rep_st = rep_ans.get("inferred_status")

        if rep_loc is not None and list(rep_loc) != [dec_x, dec_y]:
            errors.append(
                f"Declared location mismatch: trace declared {[dec_x, dec_y]} but report.json recorded {rep_loc}."
            )
        if rep_st is not None and rep_st != dec_status:
            errors.append(
                f"Declared status mismatch: trace declared '{dec_status}' but report.json recorded '{rep_st}'."
            )

    is_valid = (len(errors) == 0)
    return VerificationResult(
        is_valid=is_valid,
        errors=errors,
        steps_verified=step_count,
        warnings=warnings,
    )


def verify_main(run_dir: Union[str, Path]) -> int:
    """CLI runner for trace verification. Prints diagnostics and returns exit code."""
    res = verify_run(run_dir)
    print(f"\n==================================================")
    print(f"WALL-E TRACE REPLAY VERIFICATION: {Path(run_dir).name}")
    print(f"==================================================")
    print(f"Status:         {'[PASSED]' if res.is_valid else '[FAILED]'}")
    print(f"Steps Verified: {res.steps_verified}")

    if res.warnings:
        print(f"\nWarnings ({len(res.warnings)}):")
        for w in res.warnings:
            print(f"  [WARN] {w}")

    if not res.is_valid:
        print(f"\nDiagnostic Errors ({len(res.errors)}):")
        for err in res.errors:
            print(f"  [FAIL] {err}")
        print("==================================================\n")
        return 1

    print(f"All state transitions, energy budgets, and safety invariants verified cleanly.")
    print("==================================================\n")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m walle.verify <run_dir>")
        sys.exit(1)
    sys.exit(verify_main(sys.argv[1]))
