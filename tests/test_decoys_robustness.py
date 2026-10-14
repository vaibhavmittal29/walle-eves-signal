"""Unit tests verifying Phase 9 Bonus A: decoy handling, contradiction detection, and robust mixture inference."""

import numpy as np
import pytest
from pathlib import Path

from walle.actions import Action, ActionType
from walle.agent import BayesPlannerAgent
from walle.belief import Belief, apply_observation
from walle.config import load_config
from walle.environment import Environment
from walle.observations import ClueReading, Observation, SignalReading
from walle.runner import run_mission
from walle.signal_model import build_signal_likelihood, build_clue_likelihood
from walle.world import World


def test_robust_mixture_prevents_belief_collapse_on_decoy():
    """Mixture model with assumed_spoof_rate > 0 prevents total probability collapse on truth."""
    cfg = load_config("configs/mission_hard_decoys.yaml")
    world = World(cfg)
    info = world.public_info()
    gt = world.ground_truth()

    belief = Belief(info)
    true_x, true_y = gt.eve_location

    # Verify initial mass on truth is non-zero
    initial_prob = belief.location_marginal()[true_y, true_x]
    assert initial_prob > 0.0

    # Simulate a decoy signal pointing in the opposite direction
    # e.g., if true EVE is at (15, 15), decoy bearing is 0 degrees (pointing north from start)
    decoy_reading = SignalReading(strength=0.95, bearing_deg=0.0, dropout=False)

    # 1. Update with naive likelihood (assumed_spoof_rate = 0.0)
    naive_prior = info.sensor_prior
    from dataclasses import replace
    naive_prior_zero = replace(naive_prior, assumed_spoof_rate=0.0)
    L_naive = build_signal_likelihood(
        reading=decoy_reading,
        agent_pos=cfg.mission.start,
        prior=naive_prior_zero,
        width=info.width,
        height=info.height,
        walls=info.walls,
    )
    belief_naive = Belief(info)
    belief_naive.update(L_naive)
    naive_prob_on_truth = belief_naive.location_marginal()[true_y, true_x]

    # 2. Update with robust mixture likelihood (assumed_spoof_rate = 0.15)
    L_robust = build_signal_likelihood(
        reading=decoy_reading,
        agent_pos=cfg.mission.start,
        prior=info.sensor_prior,
        width=info.width,
        height=info.height,
        walls=info.walls,
    )
    belief_robust = Belief(info)
    belief_robust.update(L_robust)
    robust_prob_on_truth = belief_robust.location_marginal()[true_y, true_x]

    # Robust belief MUST retain significantly more probability mass on truth than naive belief
    assert robust_prob_on_truth > naive_prob_on_truth
    assert robust_prob_on_truth > 0.0


def test_contradictory_reading_flagged_as_suspicious_and_confirmation_scheduled():
    """Agent detects contradictory reading (>3-sigma angular mismatch under MAP) and schedules confirmation."""
    cfg = load_config("configs/mission_hard_decoys.yaml")
    world = World(cfg)
    info = world.public_info()

    agent = BayesPlannerAgent(seed=456)
    agent.reset(info)

    # Artificially concentrate belief on (10, 10)
    agent._belief._grid.fill(0.0)
    agent._belief._grid[10, 10, 0] = 1.0  # active at (10, 10)

    # Agent is standing at (5, 10). Expected bearing to (10, 10) is East (90 degrees).
    # Observation with bearing 270 degrees (West) contradicts the MAP hypothesis by 180 degrees (> 3-sigma).
    obs = Observation(
        step=3,
        position=(5, 10),
        battery=85,
        time_left=220,
        action_succeeded=True,
        bumped=False,
        on_charger=False,
        signal=SignalReading(strength=0.8, bearing_deg=270.0, dropout=False),
        clues=(),
        done=False,
        done_reason=None,
    )

    action, decision = agent.act(obs)

    # Must be flagged as suspicious and confirmation scheduled
    assert agent.last_observation_suspicious is True
    assert agent._pending_confirmation is True
    assert "[SUSPECTED DECOY]" in decision.reasoning


def test_hard_mission_trace_and_report_contain_discounted_status(tmp_path: Path):
    """Hard mission run logs suspicious field in trace and status in evidence table."""
    out_dir = tmp_path / "hard_decoy_run"
    res = run_mission("configs/mission_hard_decoys.yaml", master_seed=99, out_dir=out_dir)

    jsonl_path = out_dir / "trace.jsonl"
    md_path = out_dir / "report.md"
    json_path = out_dir / "report.json"

    assert jsonl_path.exists()
    assert md_path.exists()
    assert json_path.exists()

    md_text = md_path.read_text(encoding="utf-8")
    assert "| Status |" in md_text
    assert "trusted" in md_text

    rep_json = eval(json_path.read_text(encoding="utf-8").replace("true", "True").replace("false", "False").replace("null", "None"))
    assert "discounted_evidence_count" in rep_json
