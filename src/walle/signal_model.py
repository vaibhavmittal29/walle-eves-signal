"""Forward sensor simulation and Bayesian likelihood builders."""

from __future__ import annotations

import math
from typing import Any, Mapping, Optional, Sequence, Set, Tuple
import numpy as np

from walle.config import SensorConfig
from walle.geometry import bearing, distance, wrap_angle
from walle.observations import SensorPrior, SignalReading

STATUSES = ("active", "low_power", "damaged")
STATUS_TO_IDX = {"active": 0, "low_power": 1, "damaged": 2}


def expected_strength(
    d: float,
    status: str,
    amplitude: Mapping[str, float],
    d0: float,
) -> float:
    """Calculate the expected noise-free signal strength at distance d for a status.

    Formula:
        mu(d, k) = A_k / (1 + (d / d0)^2)
    """
    amp = amplitude.get(status, 1.0)
    return float(amp / (1.0 + (d / d0) ** 2))


def sample_signal(
    agent_pos: Tuple[int, int],
    eve_pos: Tuple[int, int],
    eve_status: str,
    sensor: SensorConfig,
    rng: np.random.Generator,
    decoys: Optional[Sequence[Tuple[int, int]]] = None,
) -> SignalReading:
    """Sample a noisy signal reading from the environment forward sensor model."""
    # 1. Decoy spoofing check
    if decoys and len(decoys) > 0 and sensor.decoys.spoof_probability > 0:
        if rng.random() < sensor.decoys.spoof_probability:
            decoy_idx = rng.integers(0, len(decoys))
            decoy_pos = decoys[decoy_idx]
            d_decoy = distance(agent_pos, decoy_pos)
            mu_decoy = 1.0 / (1.0 + (d_decoy / sensor.d0) ** 2)
            s_noise = rng.normal(0.0, sensor.strength_sigma * sensor.noise_scale)
            s_obs = float(np.clip(mu_decoy + s_noise, 0.0, 1.0))

            if d_decoy < 1e-6:
                return SignalReading(strength=s_obs, bearing_deg=None, dropout=False)

            sigma_theta = (
                sensor.bearing_sigma_base_deg + sensor.bearing_sigma_per_cell_deg * d_decoy
            ) * sensor.noise_scale
            b_noise = rng.normal(0.0, sigma_theta)
            b_obs = float((bearing(agent_pos, decoy_pos) + b_noise) % 360.0)
            return SignalReading(strength=s_obs, bearing_deg=b_obs, dropout=False)

    # 2. Check for dropout based on EVE's status
    p_drop = sensor.dropout.get(eve_status, 0.05)
    if rng.random() < p_drop:
        return SignalReading(strength=None, bearing_deg=None, dropout=True)

    # 3. Compute true distance and noise-free strength
    d = distance(agent_pos, eve_pos)
    mu = expected_strength(d, eve_status, sensor.amplitude, sensor.d0)
    s_noise = rng.normal(0.0, sensor.strength_sigma * sensor.noise_scale)
    s_obs = float(np.clip(mu + s_noise, 0.0, 1.0))

    # 4. Bearing calculation
    if d < 1e-6:
        return SignalReading(strength=s_obs, bearing_deg=None, dropout=False)

    sigma_theta = (
        sensor.bearing_sigma_base_deg + sensor.bearing_sigma_per_cell_deg * d
    ) * sensor.noise_scale
    b_noise = rng.normal(0.0, sigma_theta)
    true_b = bearing(agent_pos, eve_pos)
    b_obs = float((true_b + b_noise) % 360.0)

    return SignalReading(strength=s_obs, bearing_deg=b_obs, dropout=False)


def sample_clue_value(
    clue_pos: Tuple[int, int],
    eve_pos: Tuple[int, int],
    eve_status: str,
    clue_type: str,
    sensor: SensorConfig,
    rng: np.random.Generator,
) -> Any:
    """Sample a noisy clue reading according to sensor clue noise characteristics."""
    noise_cfg = sensor.clue_noise

    # False clue check (bonus)
    if noise_cfg.false_clue_probability > 0 and rng.random() < noise_cfg.false_clue_probability:
        if clue_type == "bearing":
            return float(rng.uniform(0.0, 360.0))
        if clue_type == "range":
            return float(rng.uniform(1.0, 20.0))
        if clue_type == "status":
            statuses = ["active", "low_power", "damaged"]
            return str(rng.choice(statuses))

    if clue_type == "bearing":
        true_b = bearing(clue_pos, eve_pos)
        noise = rng.normal(0.0, noise_cfg.bearing_sigma_deg * sensor.noise_scale)
        return float((true_b + noise) % 360.0)

    if clue_type == "range":
        true_r = distance(clue_pos, eve_pos)
        noise = rng.normal(0.0, noise_cfg.range_sigma * sensor.noise_scale)
        return float(max(0.0, true_r + noise))

    if clue_type == "status":
        if rng.random() < noise_cfg.status_accuracy:
            return str(eve_status)
        wrong = [s for s in ("active", "low_power", "damaged") if s != eve_status]
        return str(rng.choice(wrong))

    raise ValueError(f"Unknown clue type '{clue_type}'.")


# =========================================================================
# BAYESIAN INFERENCE LIKELIHOOD BUILDERS (Vectorized over H x W x 3 tensor)
# =========================================================================

def _compute_grid_distances_and_bearings(
    origin: Tuple[int, int],
    width: int,
    height: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Precompute Euclidean distance and compass bearings from origin to all grid cells.

    Returns:
        dist_grid: shape (height, width)
        bearing_grid: shape (height, width) in degrees [0, 360)
    """
    ox, oy = origin
    x = np.arange(width)
    y = np.arange(height)
    xx, yy = np.meshgrid(x, y)  # shape (height, width)

    dx = xx - ox
    dy = yy - oy
    dist_grid = np.hypot(dx, dy)

    # Compass bearing: 0=North (-y), 90=East (+x), 180=South (+y), 270=West (-x)
    # atan2(dx, -dy) mod 360
    bearings = np.degrees(np.arctan2(dx, -dy)) % 360.0

    return dist_grid, bearings


def build_signal_likelihood(
    reading: SignalReading,
    agent_pos: Tuple[int, int],
    prior: SensorPrior,
    width: int,
    height: int,
    walls: Set[Tuple[int, int]] | frozenset[Tuple[int, int]],
) -> np.ndarray:
    """Build joint likelihood tensor L[y, x, k] for a SCAN_SIGNAL observation.

    Args:
        reading: SignalReading with strength, bearing, and dropout flag.
        agent_pos: Current sensor coordinate.
        prior: Sensor parameters assumed by agent.
        width: Grid width.
        height: Grid height.
        walls: Set of wall coordinates (zeroed out).

    Returns:
        Array of shape (height, width, 3) representing likelihood values.
    """
    L = np.ones((height, width, 3), dtype=np.float64)

    # 1. Handle Dropout
    if reading.dropout:
        for st, idx in STATUS_TO_IDX.items():
            p_drop = prior.dropout.get(st, 0.05)
            L[:, :, idx] = p_drop
    else:
        # Non-dropout: multiply by (1 - P_drop[k])
        for st, idx in STATUS_TO_IDX.items():
            p_nodrop = max(1e-6, 1.0 - prior.dropout.get(st, 0.05))
            L[:, :, idx] *= p_nodrop

        d_grid, b_grid = _compute_grid_distances_and_bearings(agent_pos, width, height)

        # 2. Strength Likelihood: N(strength_obs; mu(d, k), sigma_s)
        if reading.strength is not None:
            s_obs = reading.strength
            sigma_s = prior.strength_sigma * prior.noise_scale
            norm_const_s = 1.0 / (math.sqrt(2.0 * math.pi) * sigma_s)

            for st, idx in STATUS_TO_IDX.items():
                amp = prior.amplitude.get(st, 1.0)
                mu_grid = amp / (1.0 + (d_grid / prior.d0) ** 2)
                z = (s_obs - mu_grid) / sigma_s
                L_s = norm_const_s * np.exp(-0.5 * (z ** 2))
                L[:, :, idx] *= L_s

        # 3. Bearing Likelihood: N(wrap(theta_obs - theta_grid); 0, sigma_theta(d))
        if reading.bearing_deg is not None:
            b_obs = reading.bearing_deg
            sigma_b = (
                prior.bearing_sigma_base_deg + prior.bearing_sigma_per_cell_deg * d_grid
            ) * prior.noise_scale
            # Angle difference wrapped to (-180, 180]
            diff = (b_obs - b_grid + 180.0) % 360.0 - 180.0
            diff[diff <= -180.0] += 360.0

            z_b = diff / sigma_b
            norm_const_b = 1.0 / (np.sqrt(2.0 * math.pi) * sigma_b)
            L_b = norm_const_b * np.exp(-0.5 * (z_b ** 2))

            # Directly on agent position, bearing is undefined -> neutral likelihood (1.0)
            ax, ay = agent_pos
            if 0 <= ax < width and 0 <= ay < height:
                L_b[ay, ax] = 1.0

            for idx in range(3):
                L[:, :, idx] *= L_b

    # Robust mixture model if assumed_spoof_rate > 0
    eps = prior.assumed_spoof_rate
    if eps > 0:
        num_free = (width * height) - len(walls)
        uniform_density = 1.0 / max(1, num_free * 3)
        L = (1.0 - eps) * L + eps * uniform_density

    # Zero out walls
    for wx, wy in walls:
        if 0 <= wx < width and 0 <= wy < height:
            L[wy, wx, :] = 0.0

    return L


def build_clue_likelihood(
    clue_pos: Tuple[int, int],
    clue_type: str,
    clue_value: Any,
    prior: SensorPrior,
    width: int,
    height: int,
    walls: Set[Tuple[int, int]] | frozenset[Tuple[int, int]],
) -> np.ndarray:
    """Build joint likelihood tensor L[y, x, k] for a clue observation.

    Args:
        clue_pos: Coordinate where clue was revealed.
        clue_type: 'bearing', 'range', or 'status'.
        clue_value: Observed clue value.
        prior: Sensor parameters assumed by agent.
        width: Grid width.
        height: Grid height.
        walls: Set of wall coordinates.

    Returns:
        Array of shape (height, width, 3).
    """
    L = np.ones((height, width, 3), dtype=np.float64)
    d_grid, b_grid = _compute_grid_distances_and_bearings(clue_pos, width, height)

    if clue_type == "bearing":
        b_obs = float(clue_value)
        sigma_b = prior.clue_bearing_sigma_deg * prior.noise_scale
        diff = (b_obs - b_grid + 180.0) % 360.0 - 180.0
        diff[diff <= -180.0] += 360.0
        z = diff / sigma_b
        L_b = (1.0 / (math.sqrt(2.0 * math.pi) * sigma_b)) * np.exp(-0.5 * (z ** 2))
        cx, cy = clue_pos
        if 0 <= cx < width and 0 <= cy < height:
            L_b[cy, cx] = 1.0
        for idx in range(3):
            L[:, :, idx] *= L_b

    elif clue_type == "range":
        r_obs = float(clue_value)
        sigma_r = prior.clue_range_sigma * prior.noise_scale
        z = (r_obs - d_grid) / sigma_r
        L_r = (1.0 / (math.sqrt(2.0 * math.pi) * sigma_r)) * np.exp(-0.5 * (z ** 2))
        for idx in range(3):
            L[:, :, idx] *= L_r

    elif clue_type == "status":
        label = str(clue_value)
        q = prior.clue_status_accuracy
        for st, idx in STATUS_TO_IDX.items():
            prob = q if st == label else (1.0 - q) / 2.0
            L[:, :, idx] *= prob

    # Robust mixture if assumed_spoof_rate > 0
    eps = prior.assumed_spoof_rate
    if eps > 0:
        num_free = (width * height) - len(walls)
        uniform_density = 1.0 / max(1, num_free * 3)
        L = (1.0 - eps) * L + eps * uniform_density

    # Zero out walls
    for wx, wy in walls:
        if 0 <= wx < width and 0 <= wy < height:
            L[wy, wx, :] = 0.0

    return L
