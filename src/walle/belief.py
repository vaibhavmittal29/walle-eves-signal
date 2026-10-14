"""Bayesian belief state over EVE's location and operational status."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Set, Tuple
import numpy as np

from walle.geometry import distance
from walle.observations import Observation, PublicMissionInfo
from walle.signal_model import (
    STATUSES,
    STATUS_TO_IDX,
    build_clue_likelihood,
    build_signal_likelihood,
)


class Belief:
    """Joint Bayesian belief tensor B[y, x, k] over EVE's 2D position and operational status."""

    def __init__(
        self,
        info: PublicMissionInfo,
        status_prior: Optional[Dict[str, float]] = None,
    ):
        self._info = info
        self._width = info.width
        self._height = info.height
        self._walls = info.walls

        # Tensor shape: (height, width, 3)
        self._grid = np.zeros((self._height, self._width, 3), dtype=np.float64)

        if status_prior is None:
            status_weights = [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0]
        else:
            status_weights = [status_prior.get(st, 1.0 / 3.0) for st in STATUSES]

        # Uniform prior over all free cells
        for y in range(self._height):
            for x in range(self._width):
                if (x, y) not in self._walls:
                    for idx in range(3):
                        self._grid[y, x, idx] = status_weights[idx]

        # Normalize so total mass is exactly 1.0
        total = float(np.sum(self._grid))
        if total > 0:
            self._grid /= total

        self._uniform_prior = self._grid.copy()
        self.contradiction_count: int = 0
        self.last_kl_divergence: float = 0.0

    @property
    def grid(self) -> np.ndarray:
        """Raw (H, W, 3) probability tensor."""
        return self._grid

    def update(self, likelihood: np.ndarray) -> float:
        """Apply Bayesian update: B <- normalize(B * L).

        Returns:
            Information gained in bits (Kullback-Leibler divergence D_KL(new || old)).
        """
        unnormalized = self._grid * likelihood
        total_mass = float(np.sum(unnormalized))

        # Contradiction fallback: blend with uniform prior if mass collapses
        if total_mass < 1e-12:
            new_grid = 0.9 * self._grid + 0.1 * self._uniform_prior
            self.contradiction_count += 1
        else:
            new_grid = unnormalized / total_mass

        # Compute KL divergence in bits: D_KL(new || old) = sum new * log2(new / old)
        valid = (new_grid > 1e-15) & (self._grid > 1e-15)
        kl = np.sum(new_grid[valid] * np.log2(new_grid[valid] / self._grid[valid]))
        self.last_kl_divergence = max(0.0, float(kl))

        self._grid = new_grid
        return self.last_kl_divergence

    def predict(self, drift_sigma: float = 0.5) -> None:
        """Diffuse location marginal with a Gaussian blur respecting walls (random walk bonus)."""
        from scipy.ndimage import gaussian_filter  # type: ignore

        for k in range(3):
            blurred = gaussian_filter(self._grid[:, :, k], sigma=drift_sigma, mode="constant")
            for wx, wy in self._walls:
                blurred[wy, wx] = 0.0
            self._grid[:, :, k] = blurred

        total = float(np.sum(self._grid))
        if total > 0:
            self._grid /= total

    def location_marginal(self) -> np.ndarray:
        """Compute 2D spatial marginal distribution M[y, x] = sum_k B[y, x, k]."""
        return np.sum(self._grid, axis=2)

    def status_marginal(self) -> Dict[str, float]:
        """Compute status marginal distribution P(status)."""
        probs = np.sum(self._grid, axis=(0, 1))
        return {st: float(probs[STATUS_TO_IDX[st]]) for st in STATUSES}

    def entropy(self) -> float:
        """Calculate joint Shannon entropy in bits: H(B) = -sum B * log2(B)."""
        flat = self._grid[self._grid > 1e-15]
        return float(-np.sum(flat * np.log2(flat)))

    def map_estimate(self) -> Tuple[int, int]:
        """Maximum A Posteriori (MAP) location estimate (x, y)."""
        loc_marg = self.location_marginal()
        idx_flat = int(np.argmax(loc_marg))
        y, x = divmod(idx_flat, self._width)
        return (x, y)

    def mean_location(self) -> Tuple[float, float]:
        """Expected target location (E[X], E[Y]) under the spatial marginal."""
        loc_marg = self.location_marginal()
        x_coords = np.arange(self._width)
        y_coords = np.arange(self._height)
        xx, yy = np.meshgrid(x_coords, y_coords)

        mean_x = float(np.sum(xx * loc_marg))
        mean_y = float(np.sum(yy * loc_marg))
        return (mean_x, mean_y)

    def mass_within(self, center: Tuple[float, float], radius: float) -> float:
        """Compute probability mass within Euclidean radius of a center coordinate."""
        loc_marg = self.location_marginal()
        cx, cy = center
        x_coords = np.arange(self._width)
        y_coords = np.arange(self._height)
        xx, yy = np.meshgrid(x_coords, y_coords)

        dists = np.hypot(xx - cx, yy - cy)
        return float(np.sum(loc_marg[dists <= radius]))

    def credible_region(self, mass: float = 0.90) -> List[Tuple[int, int]]:
        """Return the minimal set of cells containing at least the specified mass."""
        loc_marg = self.location_marginal()
        flat_indices = np.argsort(-loc_marg.ravel())
        sorted_probs = loc_marg.ravel()[flat_indices]

        cum_mass = 0.0
        cells: List[Tuple[int, int]] = []
        for idx, p in zip(flat_indices, sorted_probs):
            y, x = divmod(idx, self._width)
            cells.append((x, y))
            cum_mass += float(p)
            if cum_mass >= mass:
                break
        return cells

    def second_mode(self, exclude_radius: float = 3.0) -> Tuple[Tuple[int, int], float]:
        """Find the most likely cell outside exclude_radius from the MAP estimate."""
        map_x, map_y = self.map_estimate()
        loc_marg = self.location_marginal().copy()

        x_coords = np.arange(self._width)
        y_coords = np.arange(self._height)
        xx, yy = np.meshgrid(x_coords, y_coords)
        mask = np.hypot(xx - map_x, yy - map_y) <= exclude_radius
        loc_marg[mask] = 0.0

        best_idx = int(np.argmax(loc_marg))
        y, x = divmod(best_idx, self._width)
        return (x, y), float(loc_marg[y, x])

    def snapshot(self) -> Dict[str, object]:
        """Generate compact dictionary snapshot for structured trace logging."""
        loc_marg = self.location_marginal()
        map_x, map_y = self.map_estimate()
        return {
            "map": [map_x, map_y],
            "map_prob": round(float(loc_marg[map_y, map_x]), 4),
            "entropy_bits": round(self.entropy(), 3),
            "info_gain_bits": round(self.last_kl_divergence, 3),
            "location_confidence": round(self.mass_within((map_x, map_y), radius=1.5), 3),
            "status_probs": {st: round(p, 4) for st, p in self.status_marginal().items()},
        }


def apply_observation(
    belief: Belief,
    obs: Observation,
    agent_pos: Tuple[int, int],
    info: PublicMissionInfo,
    incorporated_clue_ids: Optional[Set[int]] = None,
    effective_prior: Optional[SensorPrior] = None,
) -> float:
    """Incorporate an observation into the belief and return total bits gained.

    Ensures clues are incorporated exactly once to prevent double-counting.
    If effective_prior is provided, uses it instead of info.sensor_prior (e.g. for discounting).
    """
    total_gain = 0.0
    prior = effective_prior if effective_prior is not None else info.sensor_prior

    # 1. Update from signal reading
    if obs.signal is not None:
        L_sig = build_signal_likelihood(
            reading=obs.signal,
            agent_pos=agent_pos,
            prior=prior,
            width=info.width,
            height=info.height,
            walls=info.walls,
        )
        total_gain += belief.update(L_sig)

    # 2. Update from clues (each clue incorporated only once)
    if obs.clues:
        for clue in obs.clues:
            if incorporated_clue_ids is not None:
                if clue.clue_id in incorporated_clue_ids:
                    continue
                incorporated_clue_ids.add(clue.clue_id)

            L_clue = build_clue_likelihood(
                clue_pos=clue.position,
                clue_type=clue.type,
                clue_value=clue.value,
                prior=prior,
                width=info.width,
                height=info.height,
                walls=info.walls,
            )
            total_gain += belief.update(L_clue)

    return total_gain
