"""Mission runner tying Environment, Agent, TraceLogger, and ReportGenerator."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import json
import numpy as np

from walle.actions import Action, ActionType, cost_of
from walle.agent import BayesPlannerAgent, Decision
from walle.baselines import GreedyBearingAgent, RandomAgent
from walle.belief import Belief
from walle.config import AppConfig, MissionSectionConfig, load_config, validate_config
from walle.environment import Environment
from walle.geometry import distance
from walle.observations import Observation, PublicMissionInfo
from walle.planner import return_reserve
from walle.report import generate_report
from walle.trace import TraceLogger
from walle.world import GroundTruth


@dataclass(frozen=True)
class RunResult:
    """Consolidated performance metrics and outcomes from a mission run."""
    config_name: str
    seed: int
    agent_type: str
    outcome: str  # 'declared', 'forced_declare', 'stranded', 'timeout'
    steps: int
    ticks_used: int
    battery_used: int
    recharges_count: int
    distance_travelled: float
    min_battery_margin: int
    declared_location: Tuple[int, int]
    declared_status: str
    true_location: Tuple[int, int]
    true_status: str
    location_error: float
    status_correct: bool
    success: bool  # error <= 2.0 and status_correct
    credible_hit: bool  # true location inside 90% credible region
    final_entropy: float
    location_confidence: float
    status_confidence: float
    clues_found: int
    trace_records: List[Dict[str, Any]]
    evidence_records: List[Dict[str, Any]] = field(default_factory=list)
    report_dict: Dict[str, Any] = field(default_factory=dict)
    net_battery_change: int = 0
    battery_consumed_by_actions: int = 0
    recharge_energy_delivered: int = 0


def run_mission(
    config_path: Union[str, Path, AppConfig],
    agent_type: Optional[str] = None,
    out_dir: Optional[Union[str, Path]] = None,
    master_seed: Optional[int] = None,
    agent_seed: Optional[int] = None,
    print_ascii: bool = False,
) -> RunResult:
    """Execute a complete simulated mission from start to final declaration.

    Strict separation: agent only receives PublicMissionInfo and Observation.
    Ground truth is only inspected after termination for evaluation metrics.
    """
    if isinstance(config_path, AppConfig):
        cfg = config_path
        validate_config(cfg)
    else:
        cfg = load_config(config_path)

    if master_seed is not None:
        m = MissionSectionConfig(
            name=cfg.mission.name,
            seed=master_seed,
            grid=cfg.mission.grid,
            start=cfg.mission.start,
            obstacles=cfg.mission.obstacles,
            chargers=cfg.mission.chargers,
            eve=cfg.mission.eve,
            clues=cfg.mission.clues,
        )
        cfg = AppConfig(
            mission=m,
            initial_signal=cfg.initial_signal,
            resources=cfg.resources,
            sensor=cfg.sensor,
            agent=cfg.agent,
        )

    # Instantiate Environment
    env = Environment(cfg)
    info, obs = env.reset()

    # Determine Agent Type
    selected_agent_type = agent_type or cfg.agent.type
    a_seed = agent_seed if agent_seed is not None else cfg.agent.seed

    if selected_agent_type == "bayes_planner":
        agent = BayesPlannerAgent(
            seed=a_seed,
            mc_samples=cfg.agent.mc_samples,
            max_candidates=cfg.agent.max_candidates,
            thresholds=cfg.agent.thresholds,
            safety=cfg.agent.safety,
            assumed_spoof_rate=cfg.agent.assumed_spoof_rate,
            expected_clues=cfg.mission.clues.count,
            mobility=cfg.mission.eve.mobility,
            diffusion_sigma=cfg.mission.eve.diffusion_sigma,
            drift_sigma=0.5 if cfg.mission.eve.mobility == "random_walk" else (cfg.mission.eve.diffusion_sigma if cfg.mission.eve.mobility == "diffusion" else 0.0),
        )
    elif selected_agent_type == "greedy_bearing":
        agent = GreedyBearingAgent(seed=a_seed)
    elif selected_agent_type == "random":
        agent = RandomAgent(seed=a_seed)
    else:
        raise ValueError(f"Unknown agent type '{selected_agent_type}'.")

    # Reset agent with public info only
    agent.reset(info)
    if isinstance(agent, BayesPlannerAgent):
        agent.observe(obs)

    # Setup logger if out_dir requested
    logger = (
        TraceLogger(
            out_dir=out_dir,
            walls=info.walls,
            chargers=info.chargers,
            grid_size=(info.width, info.height),
        )
        if out_dir is not None
        else None
    )

    # Tracking variables
    trace_records: List[Dict[str, Any]] = []
    evidence_records: List[Dict[str, Any]] = []
    initial_battery = obs.battery
    prev_pos = obs.position
    distance_travelled = 0.0
    recharges_count = 0
    recharge_energy_delivered = 0
    min_battery_margin = 999999
    declared_x, declared_y = obs.position
    declared_st = "active"

    # Log initial signal as evidence item #0 if present
    if obs.signal is not None and (obs.signal.strength is not None or obs.signal.bearing_deg is not None):
        init_gain = 0.0
        if isinstance(agent, BayesPlannerAgent) and agent._belief is not None:
            # Actual KL divergence against uniform prior
            b_curr = agent._belief.grid
            num_free = (info.width * info.height) - len(info.walls)
            u_val = 1.0 / max(1, num_free * 3)
            valid = b_curr > 1e-15
            init_gain = float(np.sum(b_curr[valid] * np.log2(b_curr[valid] / u_val)))
            init_gain = max(0.0, init_gain)

        evidence_records.append({
            "step": 0,
            "type": "initial_signal",
            "raw_value": f"str={obs.signal.strength}, brg={obs.signal.bearing_deg}°",
            "info_gain_bits": init_gain,
            "status": "trusted",
            "effect": f"Initial prior pointing along bearing {obs.signal.bearing_deg}°",
        })

    while not obs.done:
        # Pre-step state capture
        curr_step = obs.step + 1
        curr_tick = cfg.resources.time_budget - obs.time_left
        strat_name = agent._strategy.value if isinstance(agent, BayesPlannerAgent) else "SEARCH"
        strat_changes_before = len(agent.strategy_change_log) if isinstance(agent, BayesPlannerAgent) else 0

        # Calculate reserve with configured safety margins
        curr_res = return_reserve(
            pos=obs.position,
            chargers=info.chargers,
            move_battery_cost=info.costs.move.battery,
            margin_fraction=cfg.agent.safety.margin_fraction,
            margin_flat=cfg.agent.safety.margin_flat,
            walls=info.walls,
            width=info.width,
            height=info.height,
        )
        state_before = {
            "pos": [obs.position[0], obs.position[1]],
            "battery": obs.battery,
            "time_left": obs.time_left,
            "reserve": curr_res,
        }

        # Agent decision
        if isinstance(agent, BayesPlannerAgent):
            action, decision = agent.plan(obs)
        else:
            action, decision = agent.act(obs)

        # Detect if strategy changed during this act() call
        strat_change = None

        if action.type == ActionType.DECLARE:
            declared_x = action.declare_x if action.declare_x is not None else obs.position[0]
            declared_y = action.declare_y if action.declare_y is not None else obs.position[1]
            declared_st = action.declare_status if action.declare_status is not None else "active"

        # Step simulation
        obs = env.step(action)

        # Ingest observation immediately into agent so belief and metrics reflect obs
        if isinstance(agent, BayesPlannerAgent):
            agent.observe(obs)
            if len(agent.strategy_change_log) > strat_changes_before:
                strat_change = agent.strategy_change_log[-1]

        # Metric updates
        if action.type == ActionType.RECHARGE and obs.action_succeeded:
            recharges_count += 1
            energy_gained = max(0, obs.battery - state_before["battery"])
            recharge_energy_delivered += energy_gained

        dist_step = distance(prev_pos, obs.position)
        distance_travelled += dist_step
        prev_pos = obs.position

        if obs.battery < min_battery_margin:
            min_battery_margin = obs.battery

        # Evidence tracking
        is_susp = getattr(agent, "last_observation_suspicious", False)
        status_tag = "discounted" if is_susp else "trusted"

        if obs.signal is not None:
            if isinstance(agent, BayesPlannerAgent) and agent._belief is not None:
                gain = agent._belief.last_signal_gain
                map_est = agent._belief.map_estimate()
            else:
                gain = 0.0
                map_est = (0, 0)
            sig_val = (
                f"str={obs.signal.strength:.3f}, brg={obs.signal.bearing_deg:.1f}°"
                if obs.signal.strength is not None and obs.signal.bearing_deg is not None
                else "DROPOUT"
            )
            evidence_records.append({
                "step": obs.step,
                "type": "scan_signal",
                "raw_value": sig_val,
                "info_gain_bits": gain,
                "status": status_tag,
                "effect": (
                    "Discounted suspected decoy (bearing mismatch > 3σ); scheduled confirmation scan"
                    if is_susp
                    else f"Updated MAP to {map_est}, entropy={agent._belief.entropy():.2f}b"
                ) if isinstance(agent, BayesPlannerAgent) else "-",
            })

        if obs.clues:
            for cl in obs.clues:
                if isinstance(agent, BayesPlannerAgent) and agent._belief is not None:
                    gain = agent._belief.last_clue_gains.get(cl.clue_id, 0.0)
                else:
                    gain = 0.0
                evidence_records.append({
                    "step": obs.step,
                    "type": f"clue_{cl.type}",
                    "raw_value": str(cl.value),
                    "info_gain_bits": gain,
                    "status": "trusted",
                    "effect": f"Direct {cl.type} evidence at {cl.position}",
                })

        is_pending_conf = getattr(agent, "_pending_confirmation", False)
        conf_step = getattr(agent, "_confirmation_step", 0)

        # Compact step record
        step_rec = {
            "step": obs.step,
            "action": action.type.value,
            "position": obs.position,
            "battery": obs.battery,
            "time_left": obs.time_left,
            "bumped": obs.bumped,
            "reasoning": decision.reasoning,
            "pending_confirmation": is_pending_conf,
            "confirmation_step": conf_step,
        }
        trace_records.append(step_rec)

        # Log step via TraceLogger
        if logger is not None:
            belief_ref = agent._belief if isinstance(agent, BayesPlannerAgent) else Belief(info)
            logger.log_step(
                step=curr_step,
                tick=curr_tick,
                strategy=strat_name,
                strategy_change=strat_change,
                state_before=state_before,
                decision=decision,
                observation=obs,
                belief=belief_ref,
                is_suspicious=is_susp,
                pending_confirmation=is_pending_conf,
                confirmation_step=conf_step,
            )

        # Optional Live ASCII rendering
        if print_ascii:
            from walle.viz import render_ascii
            b_ref = agent._belief if isinstance(agent, BayesPlannerAgent) else Belief(info)
            clue_positions = [c.position for c in obs.clues] if obs.clues else []
            frame = render_ascii(
                position=obs.position,
                belief=b_ref,
                info=info,
                show_truth=obs.done,
                ground_truth=env.ground_truth() if obs.done else None,
                discovered_clues=clue_positions,
            )
            print(f"\n[STEP {curr_step:03d} | TICK {curr_tick:03d} | {strat_name}] Action: {action.type.value} | Battery: {obs.battery} | Time: {obs.time_left}")
            print(frame)

    if logger is not None:
        logger.close()

    # Post-mission ground truth evaluation
    gt = env.ground_truth()
    eve_x, eve_y = gt.eve_location
    err = distance((declared_x, declared_y), (eve_x, eve_y))
    st_correct = (declared_st == gt.eve_status)
    success = (err <= 2.0) and st_correct

    # Outcome classification
    outcome = obs.done_reason or "declared"
    if outcome == "timeout" and not (err <= 2.0 and st_correct):
        outcome = "forced_declare"

    credible_hit = False
    final_entropy = 0.0
    clues_found = 0

    if isinstance(agent, BayesPlannerAgent) and agent._belief is not None:
        cred_cells = agent._belief.credible_region(mass=0.90)
        credible_hit = (eve_x, eve_y) in cred_cells
        final_entropy = round(agent._belief.entropy(), 3)
        clues_found = agent._clues_found

    net_battery_change = max(0, initial_battery - obs.battery)
    battery_consumed_by_actions = net_battery_change + recharge_energy_delivered
    battery_used = battery_consumed_by_actions
    ticks_used = cfg.resources.time_budget - obs.time_left

    final_belief = agent._belief if isinstance(agent, BayesPlannerAgent) else None
    loc_conf = round(final_belief.mass_within((declared_x, declared_y), radius=1.5), 3) if final_belief else 0.90
    st_conf = round(final_belief.status_marginal().get(declared_st, 0.0), 3) if final_belief else 0.90

    result = RunResult(
        config_name=cfg.mission.name,
        seed=cfg.mission.seed,
        agent_type=selected_agent_type,
        outcome=outcome,
        steps=obs.step,
        ticks_used=ticks_used,
        battery_used=battery_used,
        recharges_count=recharges_count,
        distance_travelled=round(distance_travelled, 2),
        min_battery_margin=min_battery_margin,
        declared_location=(declared_x, declared_y),
        declared_status=declared_st,
        true_location=(eve_x, eve_y),
        true_status=gt.eve_status,
        location_error=round(err, 2),
        status_correct=st_correct,
        success=success,
        credible_hit=credible_hit,
        final_entropy=final_entropy,
        location_confidence=loc_conf,
        status_confidence=st_conf,
        clues_found=clues_found,
        trace_records=trace_records,
        evidence_records=evidence_records,
        net_battery_change=net_battery_change,
        battery_consumed_by_actions=battery_consumed_by_actions,
        recharge_energy_delivered=recharge_energy_delivered,
    )

    # Generate markdown, JSON report, predictions.json, and run.log if out_dir specified
    if out_dir is not None:
        out_path = Path(out_dir)
        strat_history = agent.strategy_change_log if isinstance(agent, BayesPlannerAgent) else []
        final_belief = agent._belief if isinstance(agent, BayesPlannerAgent) else None
        confirmed_decoys = getattr(agent, "confirmed_decoys", [])
        generate_report(
            result=result,
            evidence_records=evidence_records,
            strategy_history=strat_history,
            out_dir=out_path,
            belief=final_belief,
            info=info,
            confirmed_decoys=confirmed_decoys,
        )

        # Write predictions.json
        pred_dict = {
            "mission": result.config_name,
            "seed": result.seed,
            "agent": result.agent_type,
            "declared_location": list(result.declared_location),
            "declared_status": result.declared_status,
            "location_confidence": result.location_confidence,
            "status_confidence": result.status_confidence,
            "credible_hit": result.credible_hit,
            "location_error": result.location_error,
            "status_correct": result.status_correct,
            "success": result.success,
            "outcome": result.outcome,
            "steps": result.steps,
            "ticks_used": result.ticks_used,
            "battery_used": result.battery_used,
            "net_battery_change": result.net_battery_change,
            "recharge_energy_delivered": result.recharge_energy_delivered,
            "recharges_count": result.recharges_count,
        }
        with open(out_path / "predictions.json", "w", encoding="utf-8") as pf:
            json.dump(pred_dict, pf, indent=2)

        # Write run.log
        txt_path = out_path / "trace.txt"
        log_path = out_path / "run.log"
        if txt_path.exists():
            log_path.write_text(txt_path.read_text(encoding="utf-8"), encoding="utf-8")

        json_file = out_path / "report.json"
        if json_file.exists():
            rep_dict = json.loads(json_file.read_text(encoding="utf-8"))
            result = replace(result, report_dict=rep_dict)

    return result
