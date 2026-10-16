"""Autonomous Bayesian agent with receding-horizon lookahead and safe return constraints."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Dict, List, Optional, Sequence, Set, Tuple
import numpy as np

from walle.actions import Action, ActionType, MOVE_DELTAS, cost_of
from walle.belief import Belief, apply_observation
from walle.config import AgentSafety, AgentThresholds
from walle.geometry import bearing, distance, wrap_angle
from walle.info_gain import eig_area, eig_signal, generate_candidates
from walle.observations import Observation, PublicMissionInfo
from walle.planner import (
    bfs_distances,
    check_action_safety,
    is_action_safe,
    nearest_charger,
    path_to_move_action,
    return_reserve,
    shortest_path,
)
from walle.strategies import (
    STRATEGY_WEIGHTS,
    Strategy,
    evaluate_strategy_transition,
)


@dataclass(frozen=True)
class CandidateScore:
    """Scored viewpoint/goal candidate evaluated during decision planning."""
    goal: str
    eig_bits: float
    cost: float
    utility: float
    safe: bool


@dataclass(frozen=True)
class Decision:
    """Comprehensive decision record produced by the agent at each step."""
    action: Action
    plan: List[str]
    top_candidates: List[CandidateScore]
    reasoning: str


class BayesPlannerAgent:
    """Autonomous search agent executing active Bayesian perception under safety constraints."""

    def __init__(
        self,
        seed: int = 123,
        mc_samples: int = 40,
        max_candidates: int = 25,
        thresholds: Optional[AgentThresholds] = None,
        safety: Optional[AgentSafety] = None,
        assumed_spoof_rate: float = 0.0,
        expected_clues: int = 5,
        drift_sigma: float = 0.0,
        mobility: str = "stationary",
        diffusion_sigma: float = 0.5,
    ):
        self._master_seed = seed
        self._mc_samples = mc_samples
        self._max_candidates = max_candidates
        self._thresholds = thresholds if thresholds is not None else AgentThresholds()
        self._safety = safety if safety is not None else AgentSafety()
        self._assumed_spoof_rate = assumed_spoof_rate
        self._expected_clues = expected_clues
        self._drift_sigma = drift_sigma
        self._mobility = mobility
        self._diffusion_sigma = diffusion_sigma
        if drift_sigma > 0.0 and self._mobility in ("stationary", "static"):
            self._mobility = "random_walk" if drift_sigma == 0.5 else "diffusion"
            self._diffusion_sigma = drift_sigma

        self._info: Optional[PublicMissionInfo] = None
        self._belief: Optional[Belief] = None
        self._rng: np.random.Generator = np.random.default_rng(seed)

        self._strategy: Strategy = Strategy.EXPLORE
        self._previous_search_strategy: Strategy = Strategy.EXPLORE
        self._scan_history: List[Tuple[int, int]] = []
        self._pos_history: List[Tuple[int, int]] = []
        self._scanned_area_mask: Optional[np.ndarray] = None
        self._free_cells_mask: Optional[np.ndarray] = None
        self._clues_found: int = 0
        self._incorporated_clue_ids: Set[int] = set()

        # Multi-step plan execution
        self._current_plan: List[Action] = []
        self._current_plan_goal: Optional[str] = None
        self._current_plan_utility: float = -999.0
        self._last_planned_action: Optional[Action] = None

        # Precomputed BFS distance maps from each charger
        self._charger_dist_maps: Dict[Tuple[int, int], Dict[Tuple[int, int], int]] = {}
        self.strategy_change_log: List[Dict[str, object]] = []

        # Decoy and contradiction tracking
        self.last_observation_suspicious: bool = False
        self._pending_confirmation: bool = False
        self._confirmation_step: int = 0
        self._suspicious_readings_count: int = 0
        self._suspicious_hypothesis: Optional[Tuple[int, int]] = None
        self._suspicious_reading: Optional[SignalReading] = None
        self._suspicious_origin_pos: Optional[Tuple[int, int]] = None
        self._confirmed_decoys: List[Dict[str, Any]] = []
        self.invariant_violations: List[Dict[str, Any]] = []

    @property
    def scanned_area_mask(self) -> Optional[np.ndarray]:
        """Boolean mask of grid cells covered by successful area scans."""
        return self._scanned_area_mask

    @property
    def pending_confirmation(self) -> bool:
        """Flag indicating whether a decoy confirmation scan is currently pending."""
        return self._pending_confirmation

    @property
    def confirmation_step(self) -> int:
        """Current number of confirmation attempts made for the pending decoy hypothesis."""
        return self._confirmation_step

    @property
    def confirmed_decoys(self) -> List[Dict[str, Any]]:
        """List of confirmed decoy records that have failed verification."""
        return list(self._confirmed_decoys)

    def reset(self, info: PublicMissionInfo) -> None:
        """Initialize the agent with public mission specification."""
        self._info = info
        self._rng = np.random.default_rng(self._master_seed)
        self._belief = Belief(info)
        if info.sensor_prior.assumed_spoof_rate > 0:
            self._assumed_spoof_rate = max(
                self._assumed_spoof_rate, info.sensor_prior.assumed_spoof_rate
            )

        self._strategy = Strategy.EXPLORE
        self._previous_search_strategy = Strategy.EXPLORE
        self._scan_history.clear()
        self._pos_history.clear()
        self._incorporated_clue_ids.clear()
        self._clues_found = 0
        self._current_plan.clear()
        self._current_plan_goal = None
        self._current_plan_utility = -999.0
        self._last_planned_action = None
        self.strategy_change_log.clear()

        self.last_observation_suspicious = False
        self._pending_confirmation = False
        self._confirmation_step = 0
        self._suspicious_readings_count = 0
        self._suspicious_hypothesis = None
        self._suspicious_reading = None
        self._suspicious_origin_pos = None
        self._confirmed_decoys.clear()
        self.invariant_violations.clear()

        # Precompute charger distance maps
        self._charger_dist_maps = {
            c: bfs_distances(c, info.walls, info.width, info.height)
            for c in info.chargers
        }

        # Initialize spatial masks
        self._scanned_area_mask = np.zeros((info.height, info.width), dtype=bool)
        self._free_cells_mask = np.ones((info.height, info.width), dtype=bool)
        for wx, wy in info.walls:
            self._free_cells_mask[wy, wx] = False

    def observe(self, obs: Observation, action: Optional[Action] = None) -> None:
        """Process observation, update belief, evaluate strategies, and track clues."""
        if self._info is None or self._belief is None:
            raise RuntimeError("Agent must be reset with PublicMissionInfo before observing.")

        if action is not None:
            self._last_planned_action = action

        pos = obs.position

        # Update scanned area memory AFTER action execution, only when the action succeeded
        if (
            self._last_planned_action is not None
            and self._last_planned_action.type == ActionType.SCAN_AREA
            and obs.action_succeeded
            and not obs.bumped
            and self._scanned_area_mask is not None
        ):
            r = self._last_planned_action.radius
            px, py = pos
            h, w = self._scanned_area_mask.shape
            x_coords = np.arange(w)
            y_coords = np.arange(h)
            xx, yy = np.meshgrid(x_coords, y_coords)
            dists = np.hypot(xx - px, yy - py)
            scanned_now = (dists <= float(r)) & (self._free_cells_mask if self._free_cells_mask is not None else True)
            self._scanned_area_mask |= scanned_now

        self._last_planned_action = None

        info = self._info
        belief = self._belief
        self._pos_history.append(pos)

        # 1. Contradiction / decoy check against current MAP hypothesis (only if assumed_spoof_rate > 0)
        is_suspicious = False
        effective_prior = None

        if (
            not self._pending_confirmation
            and self._assumed_spoof_rate > 0
            and obs.signal is not None
            and obs.step > 0
            and obs.signal.bearing_deg is not None
            and not obs.signal.dropout
        ):
            prev_map_x, prev_map_y = belief.map_estimate()
            prev_conf = belief.mass_within((prev_map_x, prev_map_y), radius=1.5)
            if prev_conf >= 0.25:
                d_target = distance(pos, (prev_map_x, prev_map_y))
                if d_target >= 1.0:
                    exp_b = bearing(pos, (prev_map_x, prev_map_y))
                    ang_err = abs(wrap_angle(obs.signal.bearing_deg - exp_b))
                    sigma_b = (
                        info.sensor_prior.bearing_sigma_base_deg
                        + info.sensor_prior.bearing_sigma_per_cell_deg * d_target
                    ) * info.sensor_prior.noise_scale
                    if ang_err > max(3.0 * sigma_b, 45.0):
                        is_suspicious = True
                        self._pending_confirmation = True
                        self._confirmation_step = 0
                        self._suspicious_readings_count += 1
                        self._suspicious_reading = obs.signal
                        self._suspicious_hypothesis = (prev_map_x, prev_map_y)
                        self._suspicious_origin_pos = pos

        self.last_observation_suspicious = is_suspicious

        # Robust discounting via mixture model if assumed_spoof_rate > 0
        if is_suspicious and self._assumed_spoof_rate > 0:
            effective_prior = replace(
                info.sensor_prior,
                assumed_spoof_rate=max(0.80, self._assumed_spoof_rate),
            )

        # 2. Update belief from latest observation FIRST (observation reflects target at time t)
        if obs.signal is not None and obs.step > 0:
            self._scan_history.append(pos)
            # Evaluate confirmation evidence under documented rule
            if self._pending_confirmation and self._suspicious_hypothesis is not None:
                # Confirmation requires a NEW reading from a DIFFERENT position. A reading from the same cell CANNOT confirm.
                if self._suspicious_origin_pos is not None and pos != self._suspicious_origin_pos:
                    self._confirmation_step += 1
                    confirmed = False
                    if obs.signal.bearing_deg is not None and not obs.signal.dropout:
                        d_hyp = distance(pos, self._suspicious_hypothesis)
                        exp_b = bearing(pos, self._suspicious_hypothesis)
                        ang_err = abs(wrap_angle(obs.signal.bearing_deg - exp_b))
                        sigma_b = (
                            info.sensor_prior.bearing_sigma_base_deg
                            + info.sensor_prior.bearing_sigma_per_cell_deg * d_hyp
                        ) * info.sensor_prior.noise_scale
                        # Exit Condition 1: second scan from distinct position agrees with hypothesis (within 3 sigma or 45 deg)
                        if ang_err <= max(3.0 * sigma_b, 45.0):
                            confirmed = True

                    # Exit Condition 2: mass on an alternative mode (distinct from hypothesis) exceeds threshold (0.70)
                    map_est = belief.map_estimate()
                    if not confirmed and distance(map_est, self._suspicious_hypothesis) > 1.5:
                        if belief.mass_within(map_est, radius=1.5) >= 0.70:
                            confirmed = True

                    if confirmed:
                        self._pending_confirmation = False
                        self._confirmation_step = 0
                        self._suspicious_hypothesis = None
                        self._suspicious_origin_pos = None
                    elif self._confirmation_step >= 3:
                        # Exit Condition 3: 3 confirmation attempts fail -> flag as confirmed decoy and permanently discount
                        self._confirmed_decoys.append({
                            "step": obs.step,
                            "hypothesis": list(self._suspicious_hypothesis),
                            "origin_position": list(self._suspicious_origin_pos),
                            "attempts": self._confirmation_step,
                            "status": "confirmed_decoy",
                        })
                        self._pending_confirmation = False
                        self._confirmation_step = 0
                        self._suspicious_hypothesis = None
                        self._suspicious_origin_pos = None

        apply_observation(
            belief=belief,
            obs=obs,
            agent_pos=pos,
            info=info,
            incorporated_clue_ids=self._incorporated_clue_ids,
            effective_prior=effective_prior,
        )
        self._clues_found = len(self._incorporated_clue_ids)

        # Target mobility forward prediction for next decision step (t -> t+1)
        if obs.step > 0 and not obs.done:
            if self._mobility in ("random_walk", "diffusion"):
                belief.predict(mobility_type=self._mobility, diffusion_sigma=self._diffusion_sigma)
            elif self._drift_sigma > 0.0:
                belief.predict(drift_sigma=self._drift_sigma)

        # 3. Strategy State Machine Transitions
        map_x, map_y = belief.map_estimate()
        loc_conf = belief.mass_within((map_x, map_y), radius=1.5)
        status_marg = belief.status_marginal()
        best_status = max(status_marg.items(), key=lambda it: it[1])[0]
        status_conf = status_marg[best_status]

        current_res = return_reserve(
            pos=pos,
            chargers=info.chargers,
            move_battery_cost=info.costs.move.battery,
            margin_fraction=self._safety.margin_fraction,
            margin_flat=self._safety.margin_flat,
            walls=info.walls,
            width=info.width,
            height=info.height,
            charger_dist_maps=self._charger_dist_maps,
        )

        cheapest_useful_cost = min(info.costs.move.battery, info.costs.scan_signal.battery)
        new_strat, prev_strat, trigger = evaluate_strategy_transition(
            current_strategy=self._strategy,
            previous_search_strategy=self._previous_search_strategy,
            location_confidence=loc_conf,
            status_confidence=status_conf,
            battery=obs.battery,
            reserve_needed=current_res,
            cheapest_useful_cost=cheapest_useful_cost,
            battery_capacity=info.battery_capacity,
            time_left=obs.time_left,
            on_charger=obs.on_charger,
            thresholds=self._thresholds,
        )

        # Delay declaration if waiting for decoy confirmation scan (A8)
        if (
            self._pending_confirmation
            and self._assumed_spoof_rate > 0
            and new_strat == Strategy.DECLARE
        ):
            new_strat = Strategy.VERIFY
            trigger = "[DECOY CONFIRMATION] Verification scan pending; delaying DECLARE"

        if new_strat != self._strategy:
            self.strategy_change_log.append({
                "step": obs.step,
                "from": self._strategy.value,
                "to": new_strat.value,
                "trigger": trigger or "unspecified",
                "location_confidence": round(loc_conf, 3),
                "battery": obs.battery,
            })
            self._strategy = new_strat
            self._previous_search_strategy = prev_strat
            self._current_plan.clear()

        # A4 Rule (c): New clue or signal reading arrived triggers re-planning
        if (obs.signal is not None and not obs.signal.dropout and obs.step > 0) or bool(obs.clues):
            self._current_plan.clear()

    def plan(self, obs: Observation) -> Tuple[Action, Decision]:
        """Evaluate candidate actions and select optimal action using receding-horizon EIG."""
        if self._info is None or self._belief is None:
            raise RuntimeError("Agent must be reset with PublicMissionInfo before planning.")

        info = self._info
        belief = self._belief
        pos = obs.position

        map_x, map_y = belief.map_estimate()
        loc_conf = belief.mass_within((map_x, map_y), radius=1.5)
        status_marg = belief.status_marginal()
        best_status = max(status_marg.items(), key=lambda it: it[1])[0]
        status_conf = status_marg[best_status]

        current_res = return_reserve(
            pos=pos,
            chargers=info.chargers,
            move_battery_cost=info.costs.move.battery,
            margin_fraction=self._safety.margin_fraction,
            margin_flat=self._safety.margin_flat,
            walls=info.walls,
            width=info.width,
            height=info.height,
            charger_dist_maps=self._charger_dist_maps,
        )

        # 4. Handle DECLARE strategy (strictly blocked while pending_confirmation is True)
        if self._strategy == Strategy.DECLARE:
            if self._pending_confirmation:
                self._strategy = Strategy.VERIFY
            else:
                dec_action = Action(
                    type=ActionType.DECLARE,
                    declare_x=map_x,
                    declare_y=map_y,
                    declare_status=best_status,
                )
                decision = Decision(
                    action=dec_action,
                    plan=["DECLARE"],
                    top_candidates=[],
                    reasoning=(
                        f"Mission complete: target localized at ({map_x}, {map_y}) "
                        f"with confidence {loc_conf:.2f} and status '{best_status}' ({status_conf:.2f})."
                    ),
                )
                return self._finalize_decision(dec_action, decision, obs)

        # 5. Handle RECHARGE strategy
        if self._strategy == Strategy.RECHARGE:
            if obs.on_charger and obs.battery < int(0.90 * info.battery_capacity):
                recharge_action = Action(type=ActionType.RECHARGE)
                decision = Decision(
                    action=recharge_action,
                    plan=["RECHARGE"],
                    top_candidates=[],
                    reasoning=f"Battery {obs.battery}/{info.battery_capacity}; recharging at station {pos}.",
                )
                return self._finalize_decision(recharge_action, decision, obs)

        # 6. Handle RETURN strategy
        if self._strategy == Strategy.RETURN:
            best_charger, _ = nearest_charger(
                pos, info.chargers, info.walls, info.width, info.height, self._charger_dist_maps
            )
            path_to_charger = shortest_path(pos, best_charger, info.walls, info.width, info.height)
            if len(path_to_charger) > 1:
                next_cell = path_to_charger[1]
                return_action = path_to_move_action(pos, next_cell)
                decision = Decision(
                    action=return_action,
                    plan=["RETURN", "RECHARGE"],
                    top_candidates=[],
                    reasoning=f"Low battery ({obs.battery}); navigating along safe return path to charger {best_charger}.",
                )
                return self._finalize_decision(return_action, decision, obs)
            elif obs.on_charger:
                recharge_action = Action(type=ActionType.RECHARGE)
                decision = Decision(
                    action=recharge_action,
                    plan=["RECHARGE"],
                    top_candidates=[],
                    reasoning="Reached charger safely; initiating recharge.",
                )
                return self._finalize_decision(recharge_action, decision, obs)

        # Check safety of next action in existing plan (A4 Rule a)
        if self._current_plan:
            next_act = self._current_plan[0]
            b_cost = cost_of(next_act, info.costs)[0]
            next_pos = pos
            if next_act.type in MOVE_DELTAS:
                dx, dy = MOVE_DELTAS[next_act.type]
                next_pos = (pos[0] + dx, pos[1] + dy)

            safe = is_action_safe(
                current_battery=obs.battery,
                pos_after=next_pos,
                action_battery_cost=b_cost,
                chargers=info.chargers,
                move_battery_cost=info.costs.move.battery,
                margin_fraction=self._safety.margin_fraction,
                margin_flat=self._safety.margin_flat,
                walls=info.walls,
                width=info.width,
                height=info.height,
                charger_dist_maps=self._charger_dist_maps,
            )
            if not safe:
                self._current_plan.clear()

        # 8. Plan Next Viewpoint (Receding-Horizon Candidate Evaluation)
        weights = STRATEGY_WEIGHTS[self._strategy]
        viewpoints = generate_candidates(
            current_pos=pos,
            belief=belief,
            scan_history=self._scan_history,
            info=info,
            rng=self._rng,
            max_candidates=self._max_candidates,
        )

        mean_loc = belief.mean_location()
        dist_mean_curr = distance(pos, mean_loc)
        scored_candidates: List[Tuple[float, CandidateScore, List[Action]]] = []

        # Candidate A: SCAN_SIGNAL at current position
        can_scan_signal = (len(self._scan_history) == 0 or self._scan_history[-1] != pos)
        if self._pending_confirmation and self._suspicious_origin_pos == pos:
            can_scan_signal = False  # Confirmation requires a NEW reading from a DIFFERENT position

        if can_scan_signal:
            sig_bat = info.costs.scan_signal.battery
            sig_safe = is_action_safe(
                current_battery=obs.battery,
                pos_after=pos,
                action_battery_cost=sig_bat,
                chargers=info.chargers,
                move_battery_cost=info.costs.move.battery,
                margin_fraction=self._safety.margin_fraction,
                margin_flat=self._safety.margin_flat,
                walls=info.walls,
                width=info.width,
                height=info.height,
                charger_dist_maps=self._charger_dist_maps,
            )
            eig_here = eig_signal(belief, pos, self._rng, info, mc_samples=self._mc_samples)
            cost_norm = (sig_bat / info.battery_capacity) + (info.costs.scan_signal.time / info.time_budget)
            u_here = (weights.w_info * eig_here) / (1.0 + weights.w_cost * cost_norm)

            score_here = CandidateScore(
                goal=f"SCAN_SIGNAL@{pos}",
                eig_bits=round(eig_here, 3),
                cost=round(cost_norm, 3),
                utility=round(u_here, 3),
                safe=sig_safe,
            )
            scored_candidates.append(
                (u_here if sig_safe else -999.0, score_here, [Action(type=ActionType.SCAN_SIGNAL)])
            )

        # Candidate B: SCAN_AREA(r) for r in (1, 2, 3) at current position (A3!)
        if weights.w_clue > 0 and self._clues_found < self._expected_clues:
            max_r = min(3, info.costs.scan_area.max_radius)
            for r in range(1, max_r + 1):
                area_bat = info.costs.scan_area.battery_cost(r)
                area_time = info.costs.scan_area.time_cost(r)
                area_safe = is_action_safe(
                    current_battery=obs.battery,
                    pos_after=pos,
                    action_battery_cost=area_bat,
                    chargers=info.chargers,
                    move_battery_cost=info.costs.move.battery,
                    margin_fraction=self._safety.margin_fraction,
                    margin_flat=self._safety.margin_flat,
                    walls=info.walls,
                    width=info.width,
                    height=info.height,
                    charger_dist_maps=self._charger_dist_maps,
                )
                eig_clue = eig_area(
                    position=pos,
                    radius=r,
                    scanned_mask=self._scanned_area_mask,
                    free_cells_mask=self._free_cells_mask,
                    total_clues_expected=self._expected_clues,
                    clues_found=self._clues_found,
                )
                cost_norm_area = (area_bat / info.battery_capacity) + (area_time / info.time_budget)
                u_area = (weights.w_clue * eig_clue) / (1.0 + weights.w_cost * cost_norm_area)

                score_area = CandidateScore(
                    goal=f"SCAN_AREA({r})@{pos}",
                    eig_bits=round(eig_clue, 3),
                    cost=round(cost_norm_area, 3),
                    utility=round(u_area, 3),
                    safe=area_safe,
                )
                scored_candidates.append(
                    (u_area if area_safe else -999.0, score_area, [Action(type=ActionType.SCAN_AREA, radius=r)])
                )

        # Candidate C: Move to viewpoint vp and scan there
        for vp in viewpoints:
            if vp == pos:
                continue

            path_to_vp = shortest_path(pos, vp, info.walls, info.width, info.height)
            if not path_to_vp:
                continue

            travel_steps = len(path_to_vp) - 1
            travel_bat = travel_steps * info.costs.move.battery
            travel_time = travel_steps * info.costs.move.time
            total_bat = travel_bat + info.costs.scan_signal.battery
            total_time = travel_time + info.costs.scan_signal.time

            move_actions = [
                path_to_move_action(path_to_vp[i], path_to_vp[i + 1])
                for i in range(travel_steps)
            ]

            first_step_safe = is_action_safe(
                current_battery=obs.battery,
                pos_after=path_to_vp[1],
                action_battery_cost=info.costs.move.battery,
                chargers=info.chargers,
                move_battery_cost=info.costs.move.battery,
                margin_fraction=self._safety.margin_fraction,
                margin_flat=self._safety.margin_flat,
                walls=info.walls,
                width=info.width,
                height=info.height,
                charger_dist_maps=self._charger_dist_maps,
            )

            full_path_safe = is_action_safe(
                current_battery=obs.battery,
                pos_after=vp,
                action_battery_cost=total_bat,
                chargers=info.chargers,
                move_battery_cost=info.costs.move.battery,
                margin_fraction=self._safety.margin_fraction,
                margin_flat=self._safety.margin_flat,
                walls=info.walls,
                width=info.width,
                height=info.height,
                charger_dist_maps=self._charger_dist_maps,
            )

            safe = first_step_safe and full_path_safe
            eig_vp = eig_signal(belief, vp, self._rng, info, mc_samples=self._mc_samples)
            cost_norm_vp = (total_bat / info.battery_capacity) + (total_time / info.time_budget)
            dist_vp_mean = distance(vp, mean_loc)
            approach_bonus = max(0.0, dist_mean_curr - dist_vp_mean) * weights.w_prog

            utility_numerator = (weights.w_info * eig_vp) + approach_bonus
            utility_denominator = 1.0 + (weights.w_cost * cost_norm_vp)
            u_vp = utility_numerator / utility_denominator

            # Next action MUST be confirmation: plan a viewpoint with angular separation 45..135 deg relative to target
            if self._pending_confirmation and self._suspicious_hypothesis is not None:
                if self._suspicious_origin_pos is not None and vp == self._suspicious_origin_pos:
                    u_vp = -999.0
                else:
                    orig = self._suspicious_origin_pos or pos
                    hyp = self._suspicious_hypothesis
                    if distance(orig, hyp) > 0 and distance(vp, hyp) > 0:
                        b_orig = bearing(orig, hyp)
                        b_vp = bearing(vp, hyp)
                        ang_sep = abs(wrap_angle(b_vp - b_orig))
                        if 45.0 <= ang_sep <= 135.0:
                            u_vp *= 3.0
                        else:
                            u_vp *= 0.25

            if travel_steps > 0 and self._is_dithering(path_to_vp[1]):
                u_vp *= 0.50

            score_vp = CandidateScore(
                goal=f"GO_TO@{vp}->SCAN",
                eig_bits=round(eig_vp, 3),
                cost=round(cost_norm_vp, 3),
                utility=round(u_vp, 3),
                safe=safe,
            )
            full_plan = move_actions + [Action(type=ActionType.SCAN_SIGNAL)]
            scored_candidates.append(
                (u_vp if safe else -999.0, score_vp, full_plan)
            )

        scored_candidates.sort(key=lambda it: it[0], reverse=True)
        top_candidates = [it[1] for it in scored_candidates[:5]]

        # Safety Fallback
        safe_candidates = [it for it in scored_candidates if it[1].safe and it[0] > -900.0]
        if not safe_candidates:
            self._strategy = Strategy.RETURN
            best_charger, _ = nearest_charger(
                pos, info.chargers, info.walls, info.width, info.height, self._charger_dist_maps
            )
            path_to_charger = shortest_path(pos, best_charger, info.walls, info.width, info.height)
            if len(path_to_charger) > 1:
                return_action = path_to_move_action(pos, path_to_charger[1])
                decision = Decision(
                    action=return_action,
                    plan=["RETURN"],
                    top_candidates=top_candidates,
                    reasoning=f"No safe search actions available (battery {obs.battery}); returning to charger.",
                )
                return self._finalize_decision(return_action, decision, obs)
            else:
                recharge_action = Action(type=ActionType.RECHARGE)
                decision = Decision(
                    action=recharge_action,
                    plan=["RECHARGE"],
                    top_candidates=top_candidates,
                    reasoning="Safety forced return; currently on charger, recharging.",
                )
                return self._finalize_decision(recharge_action, decision, obs)

        best_u, best_cand, best_plan = safe_candidates[0]

        # Plan persistence vs re-planning (A4 Rule d)
        # If current plan is active and safe, only switch if fresh candidate beats it by > 15%
        if self._current_plan and best_u <= 1.15 * self._current_plan_utility:
            chosen_action = self._current_plan.pop(0)
            b_cost = cost_of(chosen_action, info.costs)[0]
            bat_after = obs.battery - b_cost
            plan_desc = [a.type.value for a in [chosen_action] + self._current_plan]
            decision = Decision(
                action=chosen_action,
                plan=plan_desc,
                top_candidates=top_candidates,
                reasoning=(
                    f"Executing plan towards {self._current_plan_goal}; "
                    f"reserve {current_res} satisfied ({obs.battery}-{b_cost}={bat_after})."
                ),
            )
            return self._finalize_decision(chosen_action, decision, obs)

        # Adopt optimal plan (fresh plan or replacement)
        self._current_plan = list(best_plan)
        self._current_plan_goal = best_cand.goal
        self._current_plan_utility = best_u

        chosen_action = self._current_plan.pop(0)
        b_cost = cost_of(chosen_action, info.costs)[0]
        bat_after = obs.battery - b_cost

        if self._pending_confirmation and self._assumed_spoof_rate > 0:
            reasoning = (
                f"[SUSPECTED DECOY] Contradictory reading detected (>3σ under MAP); "
                f"confirming from viewpoint {best_cand.goal}; reserve {current_res} "
                f"satisfied ({obs.battery}-{b_cost}={bat_after})."
            )
        else:
            reasoning = (
                f"Entropy {belief.entropy():.2f} bits; best goal {best_cand.goal} gives "
                f"{best_cand.eig_bits:.2f} bits (cost {b_cost} bat); reserve {current_res} "
                f"satisfied ({obs.battery}-{b_cost}={bat_after})."
            )

        plan_desc = [a.type.value for a in [chosen_action] + self._current_plan]
        decision = Decision(
            action=chosen_action,
            plan=plan_desc,
            top_candidates=top_candidates,
            reasoning=reasoning,
        )

        return self._finalize_decision(chosen_action, decision, obs)

    def _finalize_decision(
        self, action: Action, decision: Decision, obs: Observation
    ) -> Tuple[Action, Decision]:
        """Record the selected action for execution monitoring and return decision.

        Pre-execution guard:
            Verifies that the nonterminal action satisfies battery_after >= return_reserve(pos_after).
            If violated, substitutes a verified safe fallback action (RETURN or RECHARGE).
            The fallback action is also validated through the same safety guard.
            If the agent's current state was already unsafe, an honest invariant violation is logged.
        """
        info = self._info
        is_safe, pos_after, bat_after, res_after = check_action_safety(
            action=action,
            current_pos=obs.position,
            current_battery=obs.battery,
            costs=info.costs,
            chargers=info.chargers,
            walls=info.walls,
            width=info.width,
            height=info.height,
            margin_fraction=self._safety.margin_fraction,
            margin_flat=self._safety.margin_flat,
            charger_dist_maps=self._charger_dist_maps,
        )

        if not is_safe:
            # Action violates return reserve; clear active plan and substitute safe fallback
            self._current_plan.clear()
            if obs.on_charger:
                self._strategy = Strategy.RECHARGE
                fallback_act = Action(type=ActionType.RECHARGE)
                fallback_plan = ["RECHARGE"]
                reasoning = (
                    f"[SAFETY GUARD] Action {action.type.value} rejected (bat_after {bat_after} < "
                    f"reserve {res_after}). Recharging on station."
                )
            else:
                self._strategy = Strategy.RETURN
                best_c, _ = nearest_charger(
                    obs.position, info.chargers, info.walls, info.width, info.height, self._charger_dist_maps
                )
                path = shortest_path(obs.position, best_c, info.walls, info.width, info.height)
                if len(path) > 1:
                    fallback_act = path_to_move_action(obs.position, path[1])
                    fallback_plan = ["RETURN"]
                    reasoning = (
                        f"[SAFETY GUARD] Action {action.type.value} rejected (bat_after {bat_after} < "
                        f"reserve {res_after}). Returning to nearest charger {best_c}."
                    )
                else:
                    self._strategy = Strategy.RECHARGE
                    fallback_act = Action(type=ActionType.RECHARGE)
                    fallback_plan = ["RECHARGE"]
                    reasoning = (
                        f"[SAFETY GUARD] Action {action.type.value} rejected; at charger {best_c}, recharging."
                    )

            # Fallback must go through the same guard
            fb_safe, fb_pos_after, fb_bat_after, fb_res_after = check_action_safety(
                action=fallback_act,
                current_pos=obs.position,
                current_battery=obs.battery,
                costs=info.costs,
                chargers=info.chargers,
                walls=info.walls,
                width=info.width,
                height=info.height,
                margin_fraction=self._safety.margin_fraction,
                margin_flat=self._safety.margin_flat,
                charger_dist_maps=self._charger_dist_maps,
            )
            if not fb_safe:
                # Agent was already in an unsafe state! Record honest invariant violation.
                self.invariant_violations.append({
                    "step": obs.step,
                    "position": obs.position,
                    "battery": obs.battery,
                    "action_attempted": action.type.value,
                    "fallback_action": fallback_act.type.value,
                    "battery_after": fb_bat_after,
                    "reserve_needed": fb_res_after,
                })

            action = fallback_act
            decision = Decision(
                action=action,
                plan=fallback_plan,
                top_candidates=decision.top_candidates,
                reasoning=reasoning,
            )

        self._last_planned_action = action
        return action, decision

    def act(self, obs: Observation) -> Tuple[Action, Decision]:
        """Process observation, update belief, evaluate strategies, and select optimal action."""
        self.observe(obs)
        return self.plan(obs)

    def _is_dithering(self, next_pos: Tuple[int, int]) -> bool:
        """Detect 2-cell oscillation loops across the last 4 movements."""
        if len(self._pos_history) < 3:
            return False
        if self._pos_history[-1] == self._pos_history[-3] and next_pos == self._pos_history[-2]:
            return True
        return False
