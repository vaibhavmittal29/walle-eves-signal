"""Monte-Carlo Expected Information Gain (EIG) estimators and candidate viewpoint generation."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Set, Tuple
import numpy as np

from walle.belief import Belief
from walle.config import ClueNoiseConfig, DecoyConfig, SensorConfig
from walle.geometry import bearing, distance, wrap_angle
from walle.observations import PublicMissionInfo, SignalReading
from walle.planner import bfs_distances
from walle.signal_model import (
    STATUSES,
    build_signal_likelihood,
    sample_signal,
)


def _sensor_config_from_prior(prior: any) -> SensorConfig:
    """Reconstruct a SensorConfig instance using the agent's assumed sensor prior."""
    return SensorConfig(
        noise_scale=prior.noise_scale,
        strength_sigma=prior.strength_sigma,
        bearing_sigma_base_deg=prior.bearing_sigma_base_deg,
        bearing_sigma_per_cell_deg=prior.bearing_sigma_per_cell_deg,
        d0=prior.d0,
        amplitude=dict(prior.amplitude),
        dropout=dict(prior.dropout),
        decoys=DecoyConfig(count=0, spoof_probability=0.0),
        clue_noise=ClueNoiseConfig(
            bearing_sigma_deg=prior.clue_bearing_sigma_deg,
            range_sigma=prior.clue_range_sigma,
            status_accuracy=prior.clue_status_accuracy,
            detect_probability=prior.clue_detect_probability,
            false_clue_probability=0.0,
        ),
    )


def eig_signal(
    belief: Belief,
    position: Tuple[int, int],
    rng: np.random.Generator,
    info: PublicMissionInfo,
    mc_samples: int = 40,
) -> float:
    """Calculate Monte-Carlo Expected Information Gain (EIG) in bits for a SCAN_SIGNAL at position.

    Formula:
        EIG = H(current) - E_{obs}[ H(posterior) ]
    """
    h_current = belief.entropy()
    flat_probs = belief.grid.ravel()
    total_p = float(np.sum(flat_probs))
    if total_p <= 0:
        return 0.0

    normalized_probs = flat_probs / total_p
    indices = rng.choice(len(flat_probs), size=mc_samples, p=normalized_probs)

    h_w = info.width
    assumed_sensor = _sensor_config_from_prior(info.sensor_prior)
    delta_h_list = []

    for idx in indices:
        # Unravel index into (y, x, k)
        y_x, k = divmod(idx, 3)
        y, x = divmod(y_x, h_w)
        hyp_eve_pos = (x, y)
        hyp_status = STATUSES[k]

        # Simulate hypothetical reading with assumed sensor model
        reading = sample_signal(
            agent_pos=position,
            eve_pos=hyp_eve_pos,
            eve_status=hyp_status,
            sensor=assumed_sensor,
            rng=rng,
        )

        L = build_signal_likelihood(
            reading=reading,
            agent_pos=position,
            prior=info.sensor_prior,
            width=info.width,
            height=info.height,
            walls=info.walls,
        )

        post_grid = belief.grid * L
        post_mass = float(np.sum(post_grid))
        if post_mass > 1e-12:
            post_grid /= post_mass
            flat_post = post_grid[post_grid > 1e-15]
            h_post = float(-np.sum(flat_post * np.log2(flat_post)))
            delta_h_list.append(max(0.0, h_current - h_post))
        else:
            delta_h_list.append(0.0)

    if not delta_h_list:
        return 0.0

    return float(np.mean(delta_h_list))


def eig_area(
    position: Tuple[int, int],
    radius: int,
    scanned_mask: np.ndarray,
    free_cells_mask: np.ndarray,
    total_clues_expected: int,
    clues_found: int,
    clue_gain_bits: float = 1.0,
) -> float:
    """Proxy estimator for expected information gain from a SCAN_AREA action.

    Formula:
        remaining_clues = max(0, total_expected - found)
        fraction = unscanned_within_radius / max(1, total_unscanned)
        proxy = remaining_clues * fraction * clue_gain_bits
    """
    remaining_clues = max(0, total_clues_expected - clues_found)
    if remaining_clues <= 0:
        return 0.0

    h, w = scanned_mask.shape
    px, py = position
    x_coords = np.arange(w)
    y_coords = np.arange(h)
    xx, yy = np.meshgrid(x_coords, y_coords)
    dists = np.hypot(xx - px, yy - py)

    # Unscanned free cells within radius
    within_radius_unscanned = (dists <= radius) & (~scanned_mask) & free_cells_mask
    count_within = int(np.sum(within_radius_unscanned))

    # Total unscanned free cells on the map
    total_unscanned = int(np.sum((~scanned_mask) & free_cells_mask))
    if total_unscanned <= 0:
        return 0.0

    fraction = count_within / float(total_unscanned)
    return float(remaining_clues * fraction * clue_gain_bits)


def generate_candidates(
    current_pos: Tuple[int, int],
    belief: Belief,
    scan_history: Sequence[Tuple[int, int]],
    info: PublicMissionInfo,
    rng: np.random.Generator,
    max_candidates: int = 25,
) -> List[Tuple[int, int]]:
    """Generate diverse, reachable, obstacle-free candidate viewpoints for lookahead planning.

    Candidate selection rules:
        - Current position and its 4-connected reachable neighbors.
        - Annulus of cells 4-8 units away from belief mean (triangulation baselines).
        - Cells maximizing angular baseline separation from previous scan locations.
        - Cells in proximity (1-3 cells) to the MAP hypothesis.
        - Battery charging stations.
        - A small sample of random reachable exploratory viewpoints.
    """
    reach_map = bfs_distances(current_pos, info.walls, info.width, info.height)
    if not reach_map:
        return [current_pos]

    candidates: Set[Tuple[int, int]] = {current_pos}
    cx, cy = current_pos

    # 1. Immediate reachable neighbors
    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        nbr = (cx + dx, cy + dy)
        if nbr in reach_map:
            candidates.add(nbr)

    # 2. Charging stations
    for c in info.chargers:
        if c in reach_map:
            candidates.add(c)

    # 3. Cells near MAP estimate (distance 1..3)
    map_x, map_y = belief.map_estimate()
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            dist = math.hypot(dx, dy)
            if 1.0 <= dist <= 3.0:
                cell = (map_x + dx, map_y + dy)
                if cell in reach_map:
                    candidates.add(cell)

    # 4. Ring of cells 4-8 units away from belief mean
    mean_x, mean_y = belief.mean_location()
    angles = [0, 45, 90, 135, 180, 225, 270, 315]
    for r in (4.0, 6.0, 8.0):
        for ang in angles:
            rad = math.radians(ang)
            # Compass convention: 0 is North (-y), 90 East (+x)
            tx = int(round(mean_x + r * math.sin(rad)))
            ty = int(round(mean_y - r * math.cos(rad)))
            cell = (tx, ty)
            if cell in reach_map:
                candidates.add(cell)

    # 5. Cells maximizing angular separation from recent scans as seen from belief mean
    if scan_history:
        recent_scans = scan_history[-3:]
        past_bearings = [bearing((mean_x, mean_y), p) for p in recent_scans]
        for cell in reach_map:
            b_cell = bearing((mean_x, mean_y), cell)
            # Min angular difference to past scans
            min_ang_sep = min(abs(wrap_angle(b_cell - pb)) for pb in past_bearings)
            if min_ang_sep > 60.0 and 3.0 <= distance((mean_x, mean_y), cell) <= 10.0:
                candidates.add(cell)
                if len(candidates) >= max_candidates * 2:
                    break

    # 6. Random reachable exploratory cells
    reachable_list = list(reach_map.keys())
    if reachable_list:
        sample_size = min(10, len(reachable_list))
        random_picks = rng.choice(len(reachable_list), size=sample_size, replace=False)
        for r_idx in random_picks:
            candidates.add(reachable_list[r_idx])

    # Convert to list, sort by distance from current_pos for deterministic ranking
    sorted_candidates = sorted(list(candidates), key=lambda p: reach_map.get(p, 999999))

    return sorted_candidates[:max_candidates]
