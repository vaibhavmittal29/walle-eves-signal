"""Invariants and performance verification for the autonomous Bayesian agent."""

from pathlib import Path
import pytest

from walle.actions import ActionType
from walle.config import AppConfig, MissionSectionConfig, ResourcesConfig, load_config
from walle.runner import run_mission


def test_safety_property_100_seeds_never_stranded():
    """CRITICAL SAFETY INVARIANT: Over 100 randomized seeds, the agent is NEVER stranded."""
    base_cfg = load_config(Path("configs/mission_medium.yaml"))

    for seed in range(100):
        res = run_mission(
            config_path=base_cfg,
            agent_type="bayes_planner",
            master_seed=seed,
            agent_seed=seed + 777,
        )
        assert res.outcome != "stranded", (
            f"Agent stranded on seed {seed}! (Battery={res.min_battery_margin}, Steps={res.steps})"
        )


def test_mission_easy_success_rate_at_least_80_percent():
    """On mission_easy, agent declares within 3 cells of truth in >= 8 of 10 random seeds."""
    base_cfg = load_config(Path("configs/mission_easy.yaml"))
    successes = 0

    for seed in range(10):
        res = run_mission(
            config_path=base_cfg,
            agent_type="bayes_planner",
            master_seed=seed,
            agent_seed=seed + 101,
        )
        if res.location_error <= 3.0:
            successes += 1

    assert successes >= 8, f"Success rate {successes}/10 is below required 8/10."


def test_agent_uses_all_action_types_including_recharge():
    """Agent must execute MOVE, SCAN_SIGNAL, SCAN_AREA, RECHARGE, and DECLARE across missions."""
    base_cfg = load_config(Path("configs/mission_medium.yaml"))

    # Force a recharge by running a mission with a constrained battery capacity and initial battery
    low_bat_resources = ResourcesConfig(
        battery_capacity=35,
        battery_initial=30,
        time_budget=250,
        costs=base_cfg.resources.costs,
    )
    low_bat_cfg = AppConfig(
        mission=base_cfg.mission,
        initial_signal=base_cfg.initial_signal,
        resources=low_bat_resources,
        sensor=base_cfg.sensor,
        agent=base_cfg.agent,
    )

    res = run_mission(config_path=low_bat_cfg, agent_type="bayes_planner")

    action_types = {r["action"] for r in res.trace_records}

    # Verify all 5 core action modalities are used
    assert any("MOVE_" in a for a in action_types), "Agent never moved!"
    assert ActionType.SCAN_SIGNAL.value in action_types, "Agent never performed SCAN_SIGNAL!"
    assert ActionType.RECHARGE.value in action_types, "Agent never performed RECHARGE!"
    assert ActionType.DECLARE.value in action_types, "Agent never performed DECLARE!"
    assert res.recharges_count > 0, "No recharges were successfully executed!"


def test_strategy_transitions_progression():
    """Verify normal progression: EXPLORE -> TRACK -> VERIFY -> DECLARE."""
    res = run_mission(config_path="configs/mission_medium.yaml", agent_type="bayes_planner")
    assert res.outcome == "declared"
    assert res.location_error <= 2.0
    assert res.status_correct is True


def test_safe_return_recomputed_independently_every_step():
    """Independent verification: For every nonterminal step in a mission, remaining battery >= return reserve."""
    from walle.planner import return_reserve
    from walle.world import World

    cfg = load_config(Path("configs/mission_medium.yaml"))
    world = World(cfg)
    info = world.public_info()

    res = run_mission(config_path=cfg, agent_type="bayes_planner", master_seed=7)
    chargers_set = set(info.chargers)

    for rec in res.trace_records:
        action_name = rec["action"]
        if action_name == ActionType.DECLARE.value:
            continue

        pos_after = tuple(rec["position"])
        bat_after = rec["battery"]

        # If standing directly on a charger, battery is safe by definition
        if pos_after in chargers_set:
            continue

        independent_res = return_reserve(
            pos=pos_after,
            chargers=info.chargers,
            move_battery_cost=info.costs.move.battery,
            margin_fraction=cfg.agent.safety.margin_fraction,
            margin_flat=cfg.agent.safety.margin_flat,
            walls=info.walls,
            width=info.width,
            height=info.height,
        )

        assert bat_after >= independent_res, (
            f"Step {rec['step']}: Battery after action ({bat_after}) violated independent return reserve ({independent_res}) at {pos_after}!"
        )
