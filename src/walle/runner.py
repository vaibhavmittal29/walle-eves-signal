"""Mission runner tying Environment, Agent, TraceLogger, and ReportGenerator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from walle.actions import Action, ActionType, cost_of
from walle.agent import BayesPlannerAgent, Decision
from walle.baselines import GreedyBearingAgent, RandomAgent
from walle.belief import Belief
from walle.config import AppConfig, MissionSectionConfig, load_config
from walle.environment import Environment
from walle.geometry import distance
from walle.observations import Observation, PublicMissionInfo
from walle.planner import return_reserve
from walle.report import generate_report
from walle.signal_model import sample_signal
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
    clues_found: int
    trace_records: List[Dict[str, Any]]


def run_mission(
    config_path: Union[str, Path, AppConfig],
    agent_type: Optional[str] = None,
    out_dir: Optional[Union[str, Path]] = None,
    master_seed: Optional[int] = None,
    agent_seed: Optional[int] = None,
) -> RunResult:
    """Execute a complete simulated mission from start to final declaration.

    Strict separation: agent only receives PublicMissionInfo and Observation.
    Ground truth is only inspected after termination for evaluation metrics.
    """
    if isinstance(config_path, AppConfig):
        cfg = config_path
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
        # Sample realistic initial signal at start cell for this specific seed
        env_temp = Environment(cfg)
        gt_temp = env_temp.ground_truth()
        init_sig_sampled = sample_signal(
            agent_pos=cfg.mission.start,
            eve_pos=gt_temp.eve_location,
            eve_status=gt_temp.eve_status,
            sensor=cfg.sensor,
            rng=np.random.default_rng(master_seed + 555),
        )
        from walle.config import InitialSignalConfig
        cfg = AppConfig(
            mission=m,
            initial_signal=InitialSignalConfig(
                bearing_deg=init_sig_sampled.bearing_deg,
                coordinates=None,
                strength=init_sig_sampled.strength,
                timestamp=0,
            ),
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
        )
    elif selected_agent_type == "greedy_bearing":
        agent = GreedyBearingAgent(seed=a_seed)
    elif selected_agent_type == "random":
        agent = RandomAgent(seed=a_seed)
    else:
        raise ValueError(f"Unknown agent type '{selected_agent_type}'.")

    # Reset agent with public info only
    agent.reset(info)

    # Setup logger if out_dir requested
    logger = TraceLogger(out_dir) if out_dir is not None else None

    # Tracking variables
    trace_records: List[Dict[str, Any]] = []
    evidence_records: List[Dict[str, Any]] = []
    initial_battery = obs.battery
    prev_pos = obs.position
    distance_travelled = 0.0
    recharges_count = 0
    min_battery_margin = 999999
    declared_x, declared_y = obs.position
    declared_st = "active"

    # Log initial signal as evidence item #0 if present
    if obs.signal is not None and (obs.signal.strength is not None or obs.signal.bearing_deg is not None):
        evidence_records.append({
            "step": 0,
            "type": "initial_signal",
            "raw_value": f"str={obs.signal.strength}, brg={obs.signal.bearing_deg}°",
            "info_gain_bits": 0.5,
            "effect": f"Initial prior pointing along bearing {obs.signal.bearing_deg}°",
        })

    while not obs.done:
        # Pre-step state capture
        curr_step = obs.step + 1
        curr_tick = cfg.resources.time_budget - obs.time_left
        strat_name = agent._strategy.value if isinstance(agent, BayesPlannerAgent) else "SEARCH"
        strat_changes_before = len(agent.strategy_change_log) if isinstance(agent, BayesPlannerAgent) else 0

        # Calculate reserve
        curr_res = return_reserve(
            pos=obs.position,
            chargers=info.chargers,
            move_battery_cost=info.costs.move.battery,
            margin_fraction=0.10,
            margin_flat=3,
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
        action, decision = agent.act(obs)

        # Detect if strategy changed during this act() call
        strat_change = None
        if isinstance(agent, BayesPlannerAgent):
            if len(agent.strategy_change_log) > strat_changes_before:
                strat_change = agent.strategy_change_log[-1]

        if action.type == ActionType.DECLARE:
            declared_x = action.declare_x if action.declare_x is not None else obs.position[0]
            declared_y = action.declare_y if action.declare_y is not None else obs.position[1]
            declared_st = action.declare_status if action.declare_status is not None else "active"

        # Step simulation
        obs = env.step(action)

        # Metric updates
        if action.type == ActionType.RECHARGE and obs.action_succeeded:
            recharges_count += 1

        dist_step = distance(prev_pos, obs.position)
        distance_travelled += dist_step
        prev_pos = obs.position

        if obs.battery < min_battery_margin:
            min_battery_margin = obs.battery

        # Evidence tracking
        is_susp = getattr(agent, "last_observation_suspicious", False)
        status_tag = "discounted" if is_susp else "trusted"

        if obs.signal is not None:
            gain = agent._belief.last_kl_divergence if isinstance(agent, BayesPlannerAgent) else 0.0
            map_est = agent._belief.map_estimate() if isinstance(agent, BayesPlannerAgent) else (0, 0)
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
                gain = agent._belief.last_kl_divergence if isinstance(agent, BayesPlannerAgent) else 0.0
                evidence_records.append({
                    "step": obs.step,
                    "type": f"clue_{cl.type}",
                    "raw_value": str(cl.value),
                    "info_gain_bits": gain,
                    "status": "trusted",
                    "effect": f"Direct {cl.type} evidence at {cl.position}",
                })

        # Compact step record
        step_rec = {
            "step": obs.step,
            "action": action.type.value,
            "position": obs.position,
            "battery": obs.battery,
            "time_left": obs.time_left,
            "bumped": obs.bumped,
            "reasoning": decision.reasoning,
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
            )

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

    battery_used = max(0, initial_battery - obs.battery + (recharges_count * cfg.resources.costs.recharge.battery_gain))
    ticks_used = cfg.resources.time_budget - obs.time_left

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
        clues_found=clues_found,
        trace_records=trace_records,
    )

    # Generate markdown and JSON report if out_dir specified
    if out_dir is not None:
        strat_history = agent.strategy_change_log if isinstance(agent, BayesPlannerAgent) else []
        final_belief = agent._belief if isinstance(agent, BayesPlannerAgent) else None
        generate_report(
            result=result,
            evidence_records=evidence_records,
            strategy_history=strat_history,
            out_dir=out_dir,
            belief=final_belief,
        )

    return result
