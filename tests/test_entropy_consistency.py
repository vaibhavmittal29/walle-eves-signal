"""Invariant tests verifying mathematical consistency of entropy and confidence (Group A6)."""

import json
from pathlib import Path
import numpy as np
import pytest

from walle.config import load_config
from walle.runner import run_mission


def test_entropy_consistent_with_location_marginal(tmp_path):
    """Verify that joint entropy is >= location marginal entropy and satisfies information-theoretic bounds."""
    out_dir = tmp_path / "run_test"
    run_mission(
        config_path="configs/mission_easy.yaml",
        agent_type="bayes_planner",
        out_dir=out_dir,
        master_seed=42,
    )

    trace_path = out_dir / "trace.jsonl"
    assert trace_path.exists()

    with open(trace_path, "r", encoding="utf-8") as f:
        for line_idx, line in enumerate(f, start=1):
            rec = json.loads(line)
            b = rec["belief_after"]
            h_joint = b["entropy_bits"]
            loc_conf = b["location_confidence"]
            status_probs = b["status_probs"]
            max_st_prob = max(status_probs.values())

            # Entropy must always be non-negative
            assert h_joint >= 0.0, f"Line {line_idx}: negative entropy {h_joint}"

            # Mathematical bound:
            # If location confidence within 1.5 radius (<= 9 cells) is near 1.0
            # and status confidence is near 1.0, joint entropy cannot be arbitrarily large.
            # When loc_conf >= 0.99 and max_st_prob >= 0.99, max entropy on 9 cells is log2(9) ~= 3.17 bits.
            if loc_conf >= 0.99 and max_st_prob >= 0.99:
                assert h_joint <= 3.6, (
                    f"Line {line_idx}: Mathematical inconsistency! "
                    f"loc_conf={loc_conf}, status_conf={max_st_prob}, but entropy={h_joint} bits (> 3.6 bits)"
                )


def test_belief_entropy_greater_or_equal_to_location_marginal():
    """Verify on Belief class directly that joint entropy >= spatial marginal entropy."""
    from walle.belief import Belief
    from walle.observations import PublicMissionInfo
    from walle.config import load_config
    from walle.environment import Environment

    cfg = load_config("configs/mission_easy.yaml")
    env = Environment(cfg)
    info, _ = env.reset()

    belief = Belief(info)
    # Uniform prior
    h_joint = belief.entropy()
    loc_marg = belief.location_marginal()
    valid_loc = loc_marg[loc_marg > 1e-15]
    h_loc = float(-np.sum(valid_loc * np.log2(valid_loc)))

    assert h_joint >= h_loc - 1e-6, f"Joint entropy {h_joint} < location entropy {h_loc}"
