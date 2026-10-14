"""Forward sensor simulation and Bayesian likelihood builders."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence, Tuple
import numpy as np

from walle.config import SensorConfig
from walle.geometry import bearing, distance
from walle.observations import SignalReading


def expected_strength(
    d: float,
    status: str,
    amplitude: Mapping[str, float],
    d0: float,
) -> float:
    """Calculate the expected noise-free signal strength at distance d for a status.

    Formula:
        mu(d, k) = A_k / (1 + (d / d0)^2)

    Args:
        d: Distance from sensor to transmitter.
        status: Status string ('active', 'low_power', 'damaged').
        amplitude: Status-to-amplitude mapping A_k.
        d0: Characteristic half-power distance scale.

    Returns:
        Expected signal strength.
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
    """Sample a noisy signal reading from the environment forward sensor model.

    Features:
        - Distance-dependent strength decay.
        - Distance-dependent bearing noise: sigma_theta = (base + per_cell * d) * noise_scale.
        - Status-dependent packet dropouts (Bernoulli).
        - Optional decoy spoofing.
        - Undefined bearing when standing directly on target.

    Args:
        agent_pos: Receiver coordinate (x, y).
        eve_pos: True EVE coordinate (x, y).
        eve_status: True EVE status ('active', 'low_power', 'damaged').
        sensor: Sensor configuration parameters.
        rng: Seeded random number generator.
        decoys: Optional list of decoy transmitter locations.

    Returns:
        SignalReading dataclass instance.
    """
    # 1. Decoy spoofing check
    if decoys and len(decoys) > 0 and sensor.decoys.spoof_probability > 0:
        if rng.random() < sensor.decoys.spoof_probability:
            decoy_idx = rng.integers(0, len(decoys))
            decoy_pos = decoys[decoy_idx]
            d_decoy = distance(agent_pos, decoy_pos)
            # Decoy emits with active amplitude (1.0)
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
        # Standing on EVE's cell: bearing is undefined
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
