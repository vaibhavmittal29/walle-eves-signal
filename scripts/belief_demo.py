"""Demo script visualizing belief convergence over successive signal scans."""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from walle.belief import Belief
from walle.config import load_config
from walle.geometry import distance
from walle.observations import SignalReading
from walle.signal_model import build_signal_likelihood, sample_signal
from walle.world import World


def run_belief_demo() -> None:
    cfg = load_config("configs/mission_medium.yaml")
    world = World(cfg)
    info = world.public_info()
    gt = world.ground_truth()
    rng = np.random.default_rng(42)

    belief = Belief(info)

    # Pick 6 diverse scan positions around the map
    scan_positions = [
        info.start,
        (info.start[0] + 4, info.start[1] + 2),
        (info.chargers[-1][0], info.chargers[-1][1]),
        (info.chargers[-1][0] - 5, info.chargers[-1][1] + 4),
        (8, 14),
        (12, 6),
    ]

    snapshots = []
    # Snapshot 0: Prior
    snapshots.append((0, belief.location_marginal().copy(), None))

    for idx, pos in enumerate(scan_positions, start=1):
        # Sample signal
        sig = sample_signal(
            agent_pos=pos,
            eve_pos=gt.eve_location,
            eve_status=gt.eve_status,
            sensor=cfg.sensor,
            rng=rng,
        )
        L = build_signal_likelihood(
            reading=sig,
            agent_pos=pos,
            prior=info.sensor_prior,
            width=info.width,
            height=info.height,
            walls=info.walls,
        )
        gain = belief.update(L)
        print(f"Scan {idx} at {pos}: gain={gain:.3f} bits, entropy={belief.entropy():.2f} bits, MAP={belief.map_estimate()}")

        if idx in (1, 3, 6):
            snapshots.append((idx, belief.location_marginal().copy(), pos))

    # Plot 4-panel figure
    fig, axes = plt.subplots(1, 4, figsize=(18, 4.5))
    ex, ey = gt.eve_location

    for ax, (scans_done, marginal, last_pos) in zip(axes, snapshots):
        im = ax.imshow(marginal, cmap="inferno", origin="upper")
        # Draw walls
        for wx, wy in info.walls:
            ax.plot(wx, wy, "s", color="cyan", markersize=3, alpha=0.6)
        # Mark EVE ground truth
        ax.plot(ex, ey, "*", color="lime", markersize=12, label="True EVE")
        if last_pos:
            ax.plot(last_pos[0], last_pos[1], "o", color="white", markersize=6, label="Last Scan")

        map_x, map_y = np.unravel_index(np.argmax(marginal), marginal.shape)[1], np.unravel_index(np.argmax(marginal), marginal.shape)[0]
        ax.plot(map_x, map_y, "x", color="red", markersize=8, label="MAP")

        ax.set_title(f"After {scans_done} Scans\nMAP=({map_x},{map_y}) Dist={distance((map_x, map_y), (ex, ey)):.1f}")
        ax.set_xticks(range(0, info.width, 5))
        ax.set_yticks(range(0, info.height, 5))

    axes[0].legend(loc="lower left", fontsize=8)
    plt.tight_layout()

    out_dir = Path("outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "belief_demo.png"
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved belief demo heatmap to {out_path}")


if __name__ == "__main__":
    run_belief_demo()
