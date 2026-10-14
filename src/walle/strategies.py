"""High-level strategy state machine and utility scoring weights."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from walle.config import AgentThresholds


class Strategy(str, Enum):
    """High-level autonomous search strategies."""
    EXPLORE = "EXPLORE"
    TRACK = "TRACK"
    VERIFY = "VERIFY"
    RETURN = "RETURN"
    RECHARGE = "RECHARGE"
    DECLARE = "DECLARE"


@dataclass(frozen=True)
class StrategyWeights:
    """Weights for the candidate viewpoint utility scoring function."""
    w_info: float
    w_clue: float
    w_prog: float
    w_cost: float


# Prescribed weights per strategy from PLAN.md (Section 5.9)
STRATEGY_WEIGHTS: dict[Strategy, StrategyWeights] = {
    Strategy.EXPLORE: StrategyWeights(w_info=1.0, w_clue=0.6, w_prog=0.1, w_cost=1.5),
    Strategy.TRACK: StrategyWeights(w_info=0.7, w_clue=0.2, w_prog=0.5, w_cost=1.5),
    Strategy.VERIFY: StrategyWeights(w_info=1.0, w_clue=0.0, w_prog=0.3, w_cost=1.0),
    Strategy.RETURN: StrategyWeights(w_info=0.0, w_clue=0.0, w_prog=1.0, w_cost=0.0),
    Strategy.RECHARGE: StrategyWeights(w_info=0.0, w_clue=0.0, w_prog=0.0, w_cost=0.0),
    Strategy.DECLARE: StrategyWeights(w_info=0.0, w_clue=0.0, w_prog=0.0, w_cost=0.0),
}


def evaluate_strategy_transition(
    current_strategy: Strategy,
    previous_search_strategy: Strategy,
    location_confidence: float,
    status_confidence: float,
    battery: int,
    reserve_needed: int,
    cheapest_useful_cost: int,
    battery_capacity: int,
    time_left: int,
    on_charger: bool,
    thresholds: AgentThresholds,
    forced_declare_time: int = 8,
) -> Tuple[Strategy, Strategy, str | None]:
    """Evaluate finite state transitions for the autonomous search agent.

    Returns:
        Tuple of (new_strategy, updated_previous_search_strategy, transition_trigger_or_none)
    """
    # 1. Forced declaration on time depletion
    if time_left <= forced_declare_time:
        if current_strategy != Strategy.DECLARE:
            trigger = f"time budget critical ({time_left} ticks left), forced DECLARE"
            return Strategy.DECLARE, previous_search_strategy, trigger

    # 2. Recharging logic
    if current_strategy == Strategy.RECHARGE:
        if battery >= int(0.90 * battery_capacity):
            # Recharge complete, resume previous exploratory state
            target_strat = previous_search_strategy if previous_search_strategy in (Strategy.EXPLORE, Strategy.TRACK, Strategy.VERIFY) else Strategy.EXPLORE
            trigger = f"battery replenished ({battery}/{battery_capacity}), resuming {target_strat.value}"
            return target_strat, previous_search_strategy, trigger
        return Strategy.RECHARGE, previous_search_strategy, None

    # 3. Low-battery safety interrupt -> RETURN
    # Trigger if current battery cannot safely cover reserve + cheapest useful action
    if current_strategy not in (Strategy.RETURN, Strategy.RECHARGE, Strategy.DECLARE):
        if battery < reserve_needed + cheapest_useful_cost:
            trigger = f"battery {battery} near reserve {reserve_needed} (+ cost {cheapest_useful_cost}), initiating RETURN"
            return Strategy.RETURN, current_strategy, trigger

    # 4. Arrived at charger during RETURN -> RECHARGE
    if current_strategy == Strategy.RETURN:
        if on_charger:
            if battery < int(0.90 * battery_capacity):
                trigger = f"docked at charger with battery {battery}/{battery_capacity}, initiating RECHARGE"
                return Strategy.RECHARGE, previous_search_strategy, trigger
            else:
                target_strat = previous_search_strategy if previous_search_strategy in (Strategy.EXPLORE, Strategy.TRACK, Strategy.VERIFY) else Strategy.EXPLORE
                trigger = f"on charger with sufficient charge ({battery}), resuming {target_strat.value}"
                return target_strat, previous_search_strategy, trigger
        return Strategy.RETURN, previous_search_strategy, None

    # 5. Normal Search State Machine Progression: EXPLORE -> TRACK -> VERIFY -> DECLARE
    if current_strategy == Strategy.EXPLORE:
        if location_confidence >= thresholds.track:
            trigger = f"location confidence {location_confidence:.2f} >= {thresholds.track:.2f}, switching to TRACK"
            return Strategy.TRACK, Strategy.TRACK, trigger

    elif current_strategy == Strategy.TRACK:
        # Hysteresis: fallback to EXPLORE if evidence contradicts/collapses
        if location_confidence < 0.30:
            trigger = f"belief collapsed/conflicting evidence ({location_confidence:.2f} < 0.30), falling back to EXPLORE"
            return Strategy.EXPLORE, Strategy.EXPLORE, trigger
        elif location_confidence >= thresholds.verify:
            trigger = f"location confidence {location_confidence:.2f} >= {thresholds.verify:.2f}, switching to VERIFY"
            return Strategy.VERIFY, Strategy.VERIFY, trigger

    elif current_strategy == Strategy.VERIFY:
        if location_confidence >= thresholds.declare_location and status_confidence >= thresholds.declare_status:
            trigger = (
                f"location conf {location_confidence:.2f} >= {thresholds.declare_location:.2f} and "
                f"status conf {status_confidence:.2f} >= {thresholds.declare_status:.2f}, DECLARING"
            )
            return Strategy.DECLARE, previous_search_strategy, trigger
        elif location_confidence < thresholds.track:
            trigger = f"location confidence degraded ({location_confidence:.2f} < {thresholds.track:.2f}), reverting to TRACK"
            return Strategy.TRACK, Strategy.TRACK, trigger

    return current_strategy, previous_search_strategy, None
