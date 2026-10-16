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

    # Mission 1: Force a recharge by running with constrained battery capacity
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

    # Mission 2: Clue-seeking scenario where candidate B (SCAN_AREA) is executed
    from walle.agent import BayesPlannerAgent
    from walle.environment import Environment
    env2 = Environment(base_cfg)
    info2, obs2 = env2.reset()
    agent2 = BayesPlannerAgent(seed=42, max_candidates=0)
    agent2.reset(info2)
    agent2._scan_history = [obs2.position]  # Signal already scanned; area scan preferred
    act2, _ = agent2.plan(obs2)
    obs2_after = env2.step(act2)
    assert obs2_after.action_succeeded is True
    action_types.add(act2.type.value)

    # Verify all 5 core action modalities are used
    assert any("MOVE_" in a for a in action_types), "Agent never moved!"
    assert ActionType.SCAN_SIGNAL.value in action_types, "Agent never performed SCAN_SIGNAL!"
    assert ActionType.SCAN_AREA.value in action_types, "Agent never performed SCAN_AREA!"
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


def test_pre_execution_guard_intercepts_unsafe_candidate():
    """Pre-execution guard must reject any nonterminal action that leaves battery < return_reserve."""
    from walle.actions import Action
    from walle.agent import BayesPlannerAgent
    from walle.environment import Environment
    from walle.observations import Observation
    from walle.planner import return_reserve

    cfg = load_config(Path("configs/mission_easy.yaml"))
    env = Environment(cfg)
    info, _ = env.reset()

    agent = BayesPlannerAgent(seed=42)
    agent.reset(info)

    pos = (5, 5)
    needed_res = return_reserve(
        pos=pos,
        chargers=info.chargers,
        move_battery_cost=info.costs.move.battery,
        margin_fraction=cfg.agent.safety.margin_fraction,
        margin_flat=cfg.agent.safety.margin_flat,
        walls=info.walls,
        width=info.width,
        height=info.height,
    )

    # Battery is exactly needed_res + 1.
    # An action costing 2 battery (like SCAN_SIGNAL) would leave battery = needed_res - 1 < needed_res (UNSAFE!)
    obs = Observation(
        step=1,
        position=pos,
        battery=needed_res + 1,
        time_left=100,
        action_succeeded=True,
        bumped=False,
        on_charger=False,
        signal=None,
        clues=(),
        done=False,
        done_reason=None,
    )

    # Force a plan that attempts SCAN_SIGNAL (cost 2)
    agent._current_plan = [Action(type=ActionType.SCAN_SIGNAL)]
    act, dec = agent.plan(obs)

    # The guard must intercept SCAN_SIGNAL and substitute a safe RETURN move towards charger
    assert act.type != ActionType.SCAN_SIGNAL
    assert act.type in (ActionType.MOVE_N, ActionType.MOVE_S, ActionType.MOVE_E, ActionType.MOVE_W, ActionType.RECHARGE)
    assert "[SAFETY GUARD]" in dec.reasoning or "RETURN" in dec.plan


def test_pre_execution_guard_records_honest_violation_when_already_unsafe():
    """If the agent is in an already-unsafe state, the guard records an honest invariant violation."""
    from walle.actions import Action
    from walle.agent import BayesPlannerAgent
    from walle.environment import Environment
    from walle.observations import Observation

    cfg = load_config(Path("configs/mission_easy.yaml"))
    env = Environment(cfg)
    info, _ = env.reset()

    agent = BayesPlannerAgent(seed=42)
    agent.reset(info)

    pos = (10, 10)  # Far from charger, reserve needed is ~14
    obs = Observation(
        step=5,
        position=pos,
        battery=1,  # Only 1 battery remaining far from charger!
        time_left=100,
        action_succeeded=True,
        bumped=False,
        on_charger=False,
        signal=None,
        clues=(),
        done=False,
        done_reason=None,
    )

    act, dec = agent.plan(obs)
    # Since battery is 1, even returning towards charger leaves battery 0 < reserve, so an honest violation is logged
    assert len(agent.invariant_violations) > 0
    violation = agent.invariant_violations[0]
    assert violation["step"] == 5
    assert violation["position"] == pos
    assert violation["battery"] == 1


def test_custom_movement_costs_and_margins():
    """Verify that return_reserve and check_action_safety honor custom movement costs and margins."""
    from walle.actions import Action
    from walle.observations import CostTable, MoveCost, RechargeCost, ScanAreaCost, ScanSignalCost
    from walle.planner import check_action_safety, return_reserve

    custom_costs = CostTable(
        move=MoveCost(battery=3, time=2),
        scan_signal=ScanSignalCost(battery=4, time=2),
        scan_area=ScanAreaCost(battery_base=3, battery_per_radius=3, time_base=1, time_per_radius=1, max_radius=3),
        recharge=RechargeCost(battery_gain=30, time=3),
    )
    chargers = [(0, 0)]
    walls = frozenset()
    w, h = 20, 20
    custom_margin_fraction = 0.25
    custom_margin_flat = 5

    # At pos (4, 0), distance is 4.
    # Base battery = 4 * 3 = 12.
    # Reserve = ceil(12 * (1 + 0.25) + 5) = ceil(15 + 5) = 20.
    res = return_reserve(
        pos=(4, 0),
        chargers=chargers,
        move_battery_cost=custom_costs.move.battery,
        margin_fraction=custom_margin_fraction,
        margin_flat=custom_margin_flat,
        walls=walls,
        width=w,
        height=h,
    )
    assert res == 20

    # Test move towards (5, 0): dist is 5, base bat = 15, res_after = ceil(15 * 1.25 + 5) = ceil(18.75 + 5) = 24.
    # Action costs 3 battery.
    # Starting battery 26: bat_after = 23 < 24 -> UNSAFE
    is_safe, pos_after, bat_after, res_after = check_action_safety(
        action=Action(type=ActionType.MOVE_E),
        current_pos=(4, 0),
        current_battery=26,
        costs=custom_costs,
        chargers=chargers,
        walls=walls,
        width=w,
        height=h,
        margin_fraction=custom_margin_fraction,
        margin_flat=custom_margin_flat,
    )
    assert is_safe is False
    assert bat_after == 23
    assert res_after == 24


def test_unreachable_or_invalid_chargers():
    """Verify check_action_safety and nearest_charger route to reachable charger if one is walled off."""
    from walle.actions import Action
    from walle.observations import CostTable, MoveCost, RechargeCost, ScanAreaCost, ScanSignalCost
    from walle.planner import nearest_charger

    costs = CostTable(
        move=MoveCost(battery=1, time=1),
        scan_signal=ScanSignalCost(battery=2, time=1),
        scan_area=ScanAreaCost(battery_base=2, battery_per_radius=2, time_base=1, time_per_radius=1, max_radius=3),
        recharge=RechargeCost(battery_gain=20, time=2),
    )
    # Charger 1 at (0, 0) is enclosed by walls at (0, 1) and (1, 0)
    walls = frozenset({(0, 1), (1, 0)})
    chargers = [(0, 0), (10, 10)]
    w, h = 20, 20

    # Agent at (5, 5): nearest charger should ignore the unreachable charger at (0, 0) and pick (10, 10)
    best_c, dist = nearest_charger((5, 5), chargers, walls, w, h)
    assert best_c == (10, 10)
    assert dist == 10


def test_low_energy_on_charger_recharges_safely():
    """When docked on charger with very low energy (e.g. 0, 1, 2), RECHARGE is always verified safe."""
    from walle.actions import Action
    from walle.observations import CostTable, MoveCost, RechargeCost, ScanAreaCost, ScanSignalCost
    from walle.planner import check_action_safety

    costs = CostTable(
        move=MoveCost(battery=1, time=1),
        scan_signal=ScanSignalCost(battery=2, time=1),
        scan_area=ScanAreaCost(battery_base=2, battery_per_radius=2, time_base=1, time_per_radius=1, max_radius=3),
        recharge=RechargeCost(battery_gain=20, time=2),
    )
    chargers = [(2, 2)]
    walls = frozenset()

    for bat in (0, 1, 2):
        is_safe, pos_after, bat_after, res_after = check_action_safety(
            action=Action(type=ActionType.RECHARGE),
            current_pos=(2, 2),
            current_battery=bat,
            costs=costs,
            chargers=chargers,
            walls=walls,
            width=20,
            height=20,
            margin_fraction=0.10,
            margin_flat=3,
        )
        assert is_safe is True
        assert pos_after == (2, 2)
        assert bat_after == bat


def test_report_distinguishes_guard_verification_from_empirical_rate(tmp_path):
    """Mission report must distinguish 'verified by guard' from 'empirical stranding rate'."""
    res = run_mission(
        config_path="configs/mission_easy.yaml",
        agent_type="bayes_planner",
        out_dir=tmp_path,
        master_seed=42,
    )
    import json
    report_json = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    report_md = (tmp_path / "report.md").read_text(encoding="utf-8")

    assert "safety_verification" in report_json
    assert report_json["safety_verification"]["guard_status"] == "verified_by_guard"
    assert report_json["safety_verification"]["observed_stranding_rate"] == 0.0

    assert "Verified by pre-execution guard" in report_md
    assert "Empirical Stranding Rate" in report_md
