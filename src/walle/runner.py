"""Mission runner tying Environment, Agent, TraceLogger, and ReportGenerator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from walle.actions import Action, ActionType
from walle.agent import BayesPlannerAgent, Decision
from walle.baselines import GreedyBearingAgent, RandomAgent
from walle.config import AppConfig, MissionSectionConfig, load_config
from walle.environment import Environment
from walle.geometry import distance
from walle.observations import Observation, PublicMissionInfo
from walle.signal_model import sample_signal
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

    # Tracking variables
    trace_records: List[Dict[str, Any]] = []
    initial_battery = obs.battery
    prev_pos = obs.position
    distance_travelled = 0.0
    recharges_count = 0
    min_battery_margin = 999999
    declared_x, declared_y = obs.position
    declared_st = "active"

    while not obs.done:
        # Pre-step state capture
        curr_bat = obs.battery

        # Agent decision
        action, decision = agent.act(obs)

        if action.type == ActionType.DECLARE:
            declared_x = action.declare_x if action.declare_x is not None else obs.position[0]
            declared_y = action.declare_y if action.declare_y is not None else obs.position[1]
            declared_st = action.declare_status if action.declare_status is not None else "active"

        # Step simulation
        obs = env.step(action)

        # Post-step metric updates
        if action.type == ActionType.RECHARGE and obs.action_succeeded:
            recharges_count += 1

        dist_step = distance(prev_pos, obs.position)
        distance_travelled += dist_step
        prev_pos = obs.position

        # Track minimum battery margin
        margin = obs.battery
        if margin < min_battery_margin:
            min_battery_margin = margin

        # Build compact step record
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

    # Credible region check (if BayesPlannerAgent)
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

    return result
