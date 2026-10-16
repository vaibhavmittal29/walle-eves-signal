"""Visualizations: ASCII terminal renderer, Matplotlib summary charts, and animated GIFs."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

from walle.belief import Belief
from walle.observations import Observation, PublicMissionInfo
from walle.world import GroundTruth

STRATEGY_COLORS = {
    "EXPLORE": "#3b82f6",   # Blue
    "TRACK": "#8b5cf6",     # Purple
    "VERIFY": "#ec4899",    # Pink
    "RETURN": "#f59e0b",    # Amber
    "RECHARGE": "#10b981",  # Emerald
    "DECLARE": "#ef4444",   # Red
}

ASCII_RAMP = " .:-=+*#%@"


def render_ascii(
    position: Tuple[int, int],
    belief: Belief,
    info: PublicMissionInfo,
    show_truth: bool = False,
    ground_truth: Optional[GroundTruth] = None,
    discovered_clues: Optional[Sequence[Tuple[int, int]]] = None,
) -> str:
    """Render an ASCII grid representation showing belief heatmap intensity, agent, and landmarks."""
    w, h = info.width, info.height
    loc_marg = belief.location_marginal()
    max_p = float(np.max(loc_marg)) if np.max(loc_marg) > 0 else 1.0

    charger_set = set(info.chargers)
    clue_set = set(discovered_clues) if discovered_clues else set()

    border = "+" + "-" * w + "+"
    lines = [border]

    for y in range(h):
        row = []
        for x in range(w):
            cell = (x, y)
            if cell in info.walls:
                row.append("#")
            elif cell == position:
                row.append("W")
            elif show_truth and ground_truth and cell == ground_truth.eve_location:
                row.append("E")
            elif cell in charger_set:
                row.append("C")
            elif cell in clue_set:
                row.append("!")
            else:
                p_norm = loc_marg[y, x] / max_p
                ramp_idx = min(len(ASCII_RAMP) - 1, int(p_norm * (len(ASCII_RAMP) - 1)))
                row.append(ASCII_RAMP[ramp_idx])
        lines.append("|" + "".join(row) + "|")

    lines.append(border)
    legend = "Legend: W=WALL-E, C=Charger, #=Wall, !=Clue"
    if show_truth and ground_truth:
        legend += f", E=True EVE {ground_truth.eve_location}"
    legend += f" | Belief ramp: '{ASCII_RAMP}'"
    lines.append(legend)

    return "\n".join(lines)


def render_mission_frame(
    step_idx: int,
    total_steps: int,
    records: List[Dict[str, Any]],
    belief_grid: np.ndarray,
    walls: Sequence[Tuple[int, int]],
    chargers: Sequence[Tuple[int, int]],
    grid_size: Tuple[int, int],
    battery_capacity: int = 100,
    true_location: Optional[Tuple[int, int]] = None,
    true_status: Optional[str] = None,
    is_final_frame: bool = False,
) -> Image.Image:
    """Render a single 3-panel figure representing mission state at step_idx."""
    w, h = grid_size
    fig = plt.figure(figsize=(16, 5), dpi=100)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.2, 1.0, 1.0])

    ax_map = fig.add_subplot(gs[0])
    ax_res = fig.add_subplot(gs[1])
    ax_info = fig.add_subplot(gs[2])

    current_rec = records[step_idx]
    pos = tuple(current_rec["observation"]["pos"])
    strat = current_rec["strategy"]

    # -------------------------------------------------------------
    # PANEL 1: Map, Belief Marginal, Path & Landmarks
    # -------------------------------------------------------------
    im = ax_map.imshow(belief_grid, cmap="magma", origin="upper", extent=(0, w, h, 0), alpha=0.85)

    # Walls
    for wx, wy in walls:
        ax_map.add_patch(plt.Rectangle((wx, wy), 1, 1, facecolor="#374151", edgecolor="#1f2937", linewidth=0.5))

    # Chargers
    for cx, cy in chargers:
        ax_map.plot(cx + 0.5, cy + 0.5, "D", color="#10b981", markersize=9, markeredgecolor="white", label="Charger" if (cx, cy) == chargers[0] else "")

    # Start Position
    if records:
        start_p = records[0]["state_before"]["pos"]
        ax_map.plot(start_p[0] + 0.5, start_p[1] + 0.5, "s", color="#94a3b8", markersize=7, markeredgecolor="white", label="Start")

    # Path up to current step, colored by strategy
    for i in range(step_idx):
        p1 = records[i]["state_before"]["pos"]
        p2 = records[i]["observation"]["pos"]
        st = records[i]["strategy"]
        color = STRATEGY_COLORS.get(st, "#3b82f6")
        ax_map.plot([p1[0] + 0.5, p2[0] + 0.5], [p1[1] + 0.5, p2[1] + 0.5], "-", color=color, linewidth=2.5, alpha=0.9)

    # Scans performed up to current step
    for i in range(step_idx + 1):
        if records[i]["observation"]["signal"] is not None:
            sp = records[i]["state_before"]["pos"]
            ax_map.plot(sp[0] + 0.5, sp[1] + 0.5, "o", color="#ec4899", markersize=5, alpha=0.8)

    # Current Agent Position
    ax_map.plot(pos[0] + 0.5, pos[1] + 0.5, "o", color="#38bdf8", markersize=11, markeredgecolor="white", markeredgewidth=2, label="WALL-E")

    # MAP Estimate
    map_x, map_y = current_rec["belief_after"]["map"]
    ax_map.plot(map_x + 0.5, map_y + 0.5, "*", color="#fbbf24", markersize=12, markeredgecolor="black", label="MAP Est")

    # Final frame only: Show true EVE
    if is_final_frame and true_location is not None:
        ax_map.plot(true_location[0] + 0.5, true_location[1] + 0.5, "*", color="#22c55e", markersize=16, markeredgecolor="white", markeredgewidth=1.5, label=f"EVE (True: {true_status})")

    ax_map.set_xlim(0, w)
    ax_map.set_ylim(h, 0)
    ax_map.set_title(f"Action Step {step_idx + 1}/{total_steps} | Strategy: {strat}\nAgent Pos: {pos} | MAP: ({map_x}, {map_y})", fontsize=10, fontweight="bold")
    ax_map.legend(loc="lower left", fontsize=7, framealpha=0.7)

    # -------------------------------------------------------------
    # PANEL 2: Battery & Time Resources
    # -------------------------------------------------------------
    steps_x = list(range(1, step_idx + 2))
    battery_y = [records[i]["observation"]["battery"] for i in range(step_idx + 1)]
    reserve_y = [records[i]["state_before"]["reserve"] for i in range(step_idx + 1)]

    ax_res.plot(steps_x, battery_y, color="#10b981", linewidth=2.2, label="Battery")
    ax_res.plot(steps_x, reserve_y, "--", color="#f59e0b", linewidth=1.8, label="Return Reserve")
    ax_res.set_xlim(1, max(2, total_steps))
    y_min = -max(2.0, 0.02 * battery_capacity)
    y_max = battery_capacity * 1.05
    ax_res.set_ylim(y_min, y_max)
    ax_res.axhline(0, color="#9ca3af", linestyle="-", linewidth=0.8, alpha=0.7)
    ax_res.set_xlabel("Action Step", fontsize=9)
    ax_res.set_ylabel(f"Battery (capacity: {battery_capacity})", fontsize=9)
    ax_res.set_title(f"Energy Reserves (Bat: {battery_y[-1]}, Res: {reserve_y[-1]})", fontsize=10, fontweight="bold")
    ax_res.grid(True, linestyle=":", alpha=0.5)
    ax_res.legend(loc="upper right", fontsize=8)

    # -------------------------------------------------------------
    # PANEL 3: Entropy & Location Confidence
    # -------------------------------------------------------------
    entropy_y = [records[i]["belief_after"]["entropy_bits"] for i in range(step_idx + 1)]
    conf_y = [records[i]["belief_after"]["location_confidence"] * 100.0 for i in range(step_idx + 1)]

    ax_info.plot(steps_x, entropy_y, color="#3b82f6", linewidth=2.0, label="Entropy (bits)")
    ax_info.set_xlim(1, max(2, total_steps))
    ax_info.set_xlabel("Mission Step", fontsize=9)
    ax_info.set_ylabel("Entropy (bits)", color="#3b82f6", fontsize=9)
    ax_info.tick_params(axis="y", labelcolor="#3b82f6")
    ax_info.grid(True, linestyle=":", alpha=0.5)

    ax_conf = ax_info.twinx()
    ax_conf.plot(steps_x, conf_y, color="#8b5cf6", linewidth=2.0, linestyle="-.", label="Loc Conf (%)")
    ax_conf.set_ylim(0, 105)
    ax_conf.set_ylabel("Confidence (%)", color="#8b5cf6", fontsize=9)
    ax_conf.tick_params(axis="y", labelcolor="#8b5cf6")

    # Strategy change markers
    for i in range(step_idx + 1):
        sc = records[i]["strategy_change"]
        if sc:
            ax_info.axvline(x=i + 1, color="#ec4899", linestyle=":", alpha=0.7)

    ax_info.set_title(f"Belief Convergence (H: {entropy_y[-1]:.2f}b, Conf: {conf_y[-1]:.0f}%)", fontsize=10, fontweight="bold")

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    image = Image.open(buf)
    return image.copy()


def render_path_map(
    records: List[Dict[str, Any]],
    belief_grid: np.ndarray,
    walls: Sequence[Tuple[int, int]],
    chargers: Sequence[Tuple[int, int]],
    grid_size: Tuple[int, int],
    true_location: Optional[Tuple[int, int]] = None,
    true_status: Optional[str] = None,
    out_path: Optional[Union[str, Path]] = None,
) -> Path:
    """Render high-resolution 2D mission path map with strategy colors, scans, and credible contour."""
    w, h = grid_size
    fig, ax = plt.subplots(figsize=(10, 10), dpi=150)

    # Background heatmap of final belief marginal
    ax.imshow(belief_grid, cmap="magma", origin="upper", extent=(0, w, h, 0), alpha=0.60)

    # 90% credible contour: identify cells containing top 90% mass
    flat_indices = np.argsort(belief_grid.ravel())[::-1]
    sorted_probs = belief_grid.ravel()[flat_indices]
    cum_probs = np.cumsum(sorted_probs)
    threshold_idx = np.searchsorted(cum_probs, 0.90)
    if threshold_idx < len(sorted_probs):
        threshold_val = sorted_probs[threshold_idx]
        X, Y = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
        ax.contour(X, Y, belief_grid, levels=[threshold_val], colors=["#06b6d4"], linewidths=2.0, linestyles="--")

    # Walls
    for wx, wy in walls:
        ax.add_patch(plt.Rectangle((wx, wy), 1, 1, facecolor="#374151", edgecolor="#1f2937", linewidth=0.8, alpha=0.9))

    # Chargers
    for i, (cx, cy) in enumerate(chargers):
        ax.plot(cx + 0.5, cy + 0.5, "D", color="#10b981", markersize=10, markeredgecolor="white", markeredgewidth=1.5, label="Charger" if i == 0 else "")

    # Path segments colored by strategy
    for i in range(len(records) - 1):
        p1 = records[i]["observation"]["pos"]
        p2 = records[i + 1]["observation"]["pos"]
        strat = records[i + 1]["strategy"]
        color = STRATEGY_COLORS.get(strat, "#3b82f6")
        ax.plot([p1[0] + 0.5, p2[0] + 0.5], [p1[1] + 0.5, p2[1] + 0.5], "-", color=color, linewidth=2.5, alpha=0.85)

        # Draw direction arrows every 3 steps or on turns
        if (i % 3 == 0 or (p1[0] != p2[0] and p1[1] != p2[1])) and (p1 != p2):
            dx = (p2[0] - p1[0]) * 0.35
            dy = (p2[1] - p1[1]) * 0.35
            ax.annotate(
                "",
                xy=(p2[0] + 0.5, p2[1] + 0.5),
                xytext=(p1[0] + 0.5 + dx, p1[0] + 0.5 + dy),
                arrowprops=dict(arrowstyle="->", color=color, lw=1.5, mutation_scale=12),
            )

    # Scans performed
    scan_plotted = False
    for r in records:
        dec = r.get("decision", {})
        act = dec.get("action", "")
        params = dec.get("action_params", {})
        p = r["observation"]["pos"]
        if act == "SCAN_AREA":
            rad = params.get("radius", 2)
            circ = plt.Circle((p[0] + 0.5, p[1] + 0.5), rad, fill=False, edgecolor="#ec4899", linestyle=":", linewidth=1.4, alpha=0.7)
            ax.add_patch(circ)
            ax.plot(p[0] + 0.5, p[1] + 0.5, "o", color="#ec4899", markersize=4, label="Scan Area" if not scan_plotted else "")
            scan_plotted = True
        elif act == "SCAN_SIGNAL" and r["observation"].get("signal"):
            ax.plot(p[0] + 0.5, p[1] + 0.5, "o", color="#8b5cf6", markersize=4)

    # Start and Final positions
    start_pos = records[0]["state_before"]["pos"]
    ax.plot(start_pos[0] + 0.5, start_pos[1] + 0.5, "s", color="#38bdf8", markersize=11, markeredgecolor="white", markeredgewidth=2, label="Start")

    final_pos = records[-1]["observation"]["pos"]
    ax.plot(final_pos[0] + 0.5, final_pos[1] + 0.5, "o", color="#38bdf8", markersize=11, markeredgecolor="white", markeredgewidth=2, label="Final WALL-E")

    # Final MAP Estimate
    final_map = records[-1]["belief_after"]["map"]
    ax.plot(final_map[0] + 0.5, final_map[1] + 0.5, "*", color="#fbbf24", markersize=16, markeredgecolor="black", markeredgewidth=1.2, label=f"MAP Declared ({final_map[0]},{final_map[1]})")

    # True EVE location (post-mission ground truth)
    if true_location is not None:
        ax.plot(true_location[0] + 0.5, true_location[1] + 0.5, "X", color="#22c55e", markersize=14, markeredgecolor="white", markeredgewidth=1.5, label=f"True EVE ({true_status or 'target'})")

    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)
    ax.set_xlabel("X Coordinate", fontsize=11)
    ax.set_ylabel("Y Coordinate", fontsize=11)
    ax.set_title(f"WALL-E Mission Path & Spatial Posterior (Steps: {len(records)})", fontsize=13, fontweight="bold")
    ax.legend(loc="upper right", fontsize=8, framealpha=0.85)
    plt.tight_layout()

    target_path = Path(out_path) if out_path else Path("path_map.png")
    fig.savefig(target_path, dpi=150)
    plt.close(fig)
    return target_path


def render_path_3d(
    records: List[Dict[str, Any]],
    walls: Sequence[Tuple[int, int]],
    chargers: Sequence[Tuple[int, int]],
    grid_size: Tuple[int, int],
    final_belief_grid: np.ndarray,
    out_path: Optional[Union[str, Path]] = None,
) -> Path:
    """Render 3D space-time trajectory (x, y, t) with floor belief projection and stems."""
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    w, h = grid_size
    fig = plt.figure(figsize=(11, 9), dpi=150)
    ax = fig.add_subplot(111, projection="3d")

    xs = [r["observation"]["pos"][0] + 0.5 for r in records]
    ys = [r["observation"]["pos"][1] + 0.5 for r in records]
    ts = [r["step"] for r in records]

    # Floor walls at t=0
    for wx, wy in walls:
        ax.bar3d(wx, wy, 0, 1, 1, 0.2, color="#374151", alpha=0.4, shade=True)

    # Floor chargers at t=0
    for cx, cy in chargers:
        ax.scatter([cx + 0.5], [cy + 0.5], [0], color="#10b981", marker="D", s=50, edgecolors="white", depthshade=False)

    # Floor belief projection contour
    X, Y = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    ax.contourf(X, Y, final_belief_grid, zdir="z", offset=0, cmap="magma", alpha=0.35)

    # Drop stems from path to floor
    for x, y, t in zip(xs, ys, ts):
        if t % 2 == 0 or t == ts[-1]:
            ax.plot([x, x], [y, y], [0, t], color="#9ca3af", linestyle=":", linewidth=0.8, alpha=0.5)

    # 3D Path segments colored by strategy
    for i in range(len(records) - 1):
        strat = records[i + 1]["strategy"]
        col = STRATEGY_COLORS.get(strat, "#3b82f6")
        ax.plot(
            [xs[i], xs[i + 1]],
            [ys[i], ys[i + 1]],
            [ts[i], ts[i + 1]],
            "-",
            color=col,
            linewidth=2.8,
            alpha=0.9,
        )

    # Scatter points along trajectory
    ax.scatter(xs, ys, ts, c="#38bdf8", s=25, edgecolors="black", linewidths=0.5)

    # Final declared MAP position at final time
    final_map = records[-1]["belief_after"]["map"]
    ax.scatter([final_map[0] + 0.5], [final_map[1] + 0.5], [ts[-1]], color="#fbbf24", marker="*", s=160, edgecolors="black", label="Declared MAP")

    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.set_zlim(0, max(10, max(ts) + 1))
    ax.set_xlabel("Grid X", labelpad=8)
    ax.set_ylabel("Grid Y", labelpad=8)
    ax.set_zlabel("Time Step (t)", labelpad=8)
    ax.set_title("WALL-E Space-Time Trajectory $(x, y, t)$", fontsize=12, fontweight="bold", pad=12)
    ax.view_init(elev=28, azim=-55)

    target_path = Path(out_path) if out_path else Path("path_3d.png")
    plt.tight_layout()
    fig.savefig(target_path, dpi=150)
    plt.close(fig)
    return target_path


def render_belief_evolution(
    belief_frames: Any,
    records: List[Dict[str, Any]],
    grid_size: Tuple[int, int],
    out_path: Optional[Union[str, Path]] = None,
) -> Path:
    """Render small multiples showing spatial belief evolution over 6 key mission checkpoints."""
    w, h = grid_size
    frame_steps = belief_frames.get("steps", []) if isinstance(belief_frames, dict) or hasattr(belief_frames, "get") else []

    total_steps = len(records)
    if total_steps <= 6:
        selected_steps = [r["step"] for r in records]
    else:
        indices = np.linspace(0, total_steps - 1, 6, dtype=int)
        selected_steps = [records[i]["step"] for i in indices]

    fig, axes = plt.subplots(2, 3, figsize=(15, 9), dpi=130)
    axes = axes.flatten()

    def get_marginal(s: int) -> np.ndarray:
        if f"frame_{s}" in belief_frames:
            return belief_frames[f"frame_{s}"]
        if len(frame_steps) > 0:
            closest = frame_steps[int(np.argmin([abs(fs - s) for fs in frame_steps]))]
            return belief_frames[f"frame_{closest}"]
        return np.ones((h, w), dtype=np.float64) / (w * h)

    for idx in range(6):
        ax = axes[idx]
        if idx < len(selected_steps):
            s = selected_steps[idx]
            grid = get_marginal(s)
            im = ax.imshow(grid, cmap="magma", origin="upper", extent=(0, w, h, 0))

            matching_rec = next((r for r in records if r["step"] == s), records[min(s - 1, len(records) - 1)])
            strat = matching_rec["strategy"]
            pos = matching_rec["observation"]["pos"]
            map_pos = matching_rec["belief_after"]["map"]
            entropy = matching_rec["belief_after"]["entropy_bits"]

            ax.plot(pos[0] + 0.5, pos[1] + 0.5, "o", color="#38bdf8", markersize=8, markeredgecolor="white", markeredgewidth=1.2)
            ax.plot(map_pos[0] + 0.5, map_pos[1] + 0.5, "*", color="#fbbf24", markersize=10, markeredgecolor="black")

            ax.set_xlim(0, w)
            ax.set_ylim(h, 0)
            ax.set_title(f"Step {s} [{strat}]\nEntropy: {entropy:.2f}b | MAP: ({map_pos[0]},{map_pos[1]})", fontsize=9, fontweight="bold")
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        else:
            ax.axis("off")

    fig.suptitle("Bayesian Spatial Belief Evolution: $P(\\mathbf{x}_{eve} \\mid \\mathbf{z}_{1:t})$", fontsize=14, fontweight="bold")
    plt.tight_layout()

    target_path = Path(out_path) if out_path else Path("belief_evolution.png")
    fig.savefig(target_path, dpi=130)
    plt.close(fig)
    return target_path


def render_metrics_dashboard(
    records: List[Dict[str, Any]],
    report_data: Dict[str, Any],
    battery_capacity: int = 100,
    out_path: Optional[Union[str, Path]] = None,
) -> Path:
    """Render 2x2 dashboard: energy vs reserve, entropy vs info gain, confidence, and strategy regimes."""
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10), dpi=140)

    steps = [r["step"] for r in records]
    batteries = [r["observation"]["battery"] for r in records]
    reserves = [r["state_before"]["reserve"] for r in records]
    entropies = [r["belief_after"]["entropy_bits"] for r in records]
    info_gains = [r["belief_after"].get("info_gain_bits", 0.0) for r in records]
    cum_info_gains = np.cumsum(info_gains)
    loc_confs = [r["belief_after"]["location_confidence"] for r in records]
    status_confs = [
        max(r["belief_after"]["status_probs"].values()) if r["belief_after"].get("status_probs") else 0.5
        for r in records
    ]

    # Panel 1: Energy & Safety Margin
    ax1.plot(steps, batteries, color="#10b981", linewidth=2.4, label="Battery Level")
    ax1.plot(steps, reserves, "--", color="#f59e0b", linewidth=2.0, label="Safe Return Reserve")
    ax1.fill_between(steps, reserves, batteries, color="#10b981", alpha=0.15, label="Safe Operating Margin")
    ax1.set_xlabel("Action Step", fontsize=10)
    ax1.set_ylabel(f"Battery (units / {battery_capacity})", fontsize=10)
    ax1.set_title("Energy Budget & Invariant Return Reserve", fontsize=11, fontweight="bold")
    y_min = -max(2.0, 0.02 * battery_capacity)
    y_max = battery_capacity * 1.05
    ax1.set_ylim(y_min, y_max)
    ax1.axhline(0, color="#9ca3af", linestyle="-", linewidth=0.8, alpha=0.7)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend(loc="lower left", fontsize=8)

    # Panel 2: Uncertainty Reduction
    ax2.plot(steps, entropies, color="#3b82f6", linewidth=2.2, label="Spatial Entropy (bits)")
    ax2.plot(steps, cum_info_gains, color="#8b5cf6", linewidth=2.2, label="Cumulative KL Divergence (bits)")
    ax2.set_xlabel("Mission Step", fontsize=10)
    ax2.set_ylabel("Information Measure (bits)", fontsize=10)
    ax2.set_title("Belief Convergence: Entropy vs Cumulative Info Gain", fontsize=11, fontweight="bold")
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="center right", fontsize=8)

    # Panel 3: Confidence Trajectories
    ax3.plot(steps, loc_confs, color="#ec4899", linewidth=2.4, label="Location Confidence (Credible Mass)")
    ax3.plot(steps, status_confs, color="#06b6d4", linewidth=2.2, label="Status Confidence (MAP Mode)")
    ax3.axhline(0.80, color="#ef4444", linestyle="--", linewidth=1.5, label="Declaration Threshold (80%)")
    ax3.set_xlabel("Mission Step", fontsize=10)
    ax3.set_ylabel("Posterior Probability", fontsize=10)
    ax3.set_title("Target Confidence Progression", fontsize=11, fontweight="bold")
    ax3.set_ylim(0, 1.05)
    ax3.grid(True, linestyle=":", alpha=0.6)
    ax3.legend(loc="lower right", fontsize=8)

    # Panel 4: Evidence Events & Strategy Regimes
    ax4.bar(steps, info_gains, color="#6366f1", alpha=0.7, width=0.6, label="Step Info Gain (bits)")
    strat_changes = [r for r in records if r.get("strategy_change")]
    max_gain = max(info_gains + [0.5])
    for sc in strat_changes:
        st_step = sc["step"]
        to_strat = sc["strategy_change"]["to"]
        ax4.axvline(st_step, color=STRATEGY_COLORS.get(to_strat, "#6b7280"), linestyle=":", linewidth=1.8)
        ax4.text(st_step + 0.15, max_gain * 0.82, to_strat, rotation=90, fontsize=8, fontweight="bold", color=STRATEGY_COLORS.get(to_strat, "#374151"))

    ax4.set_xlabel("Mission Step", fontsize=10)
    ax4.set_ylabel("Information Gain (bits)", fontsize=10)
    ax4.set_title("Evidence Events & Strategy Transitions", fontsize=11, fontweight="bold")
    ax4.grid(True, linestyle=":", alpha=0.6)
    ax4.legend(loc="upper right", fontsize=8)

    mission_name = report_data.get("mission_summary", {}).get("config_name", "Mission")
    fig.suptitle(f"Mission Metrics & Dynamic Evaluation: {mission_name}", fontsize=13, fontweight="bold")
    plt.tight_layout()

    target_path = Path(out_path) if out_path else Path("metrics_dashboard.png")
    fig.savefig(target_path, dpi=140)
    plt.close(fig)
    return target_path


def generate_visuals_from_run(run_dir: Union[str, Path]) -> Tuple[Path, Path]:
    """Generate all 6 required visual artifacts from run artifacts:
    summary.png, run.gif, path_map.png, path_3d.png, belief_evolution.png, metrics_dashboard.png.
    """
    run_dir = Path(run_dir)
    jsonl_path = run_dir / "trace.jsonl"
    report_path = run_dir / "report.json"
    npz_path = run_dir / "belief_frames.npz"

    if not jsonl_path.exists() or not report_path.exists():
        raise FileNotFoundError(f"Missing required artifacts in {run_dir} (trace.jsonl or report.json)")

    with open(jsonl_path, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    with open(report_path, "r", encoding="utf-8") as f:
        report_data = json.load(f)

    # Load belief frames
    belief_frames = np.load(npz_path) if npz_path.exists() else {}
    frame_steps = belief_frames.get("steps", [])

    total_steps = len(records)
    true_loc = tuple(report_data["ground_truth_check"]["true_location"])
    true_st = report_data["ground_truth_check"]["true_status"]

    # Extract chargers, walls, and grid size
    w, h = 20, 20
    chargers: List[Tuple[int, int]] = [(2, 2), (15, 9)]
    walls: List[Tuple[int, int]] = []

    if "grid_size" in belief_frames:
        w, h = int(belief_frames["grid_size"][0]), int(belief_frames["grid_size"][1])
    elif "environment" in report_data and "grid_size" in report_data["environment"]:
        w, h = report_data["environment"]["grid_size"]

    if "chargers" in belief_frames and len(belief_frames["chargers"]) > 0:
        chargers = [tuple(c) for c in belief_frames["chargers"]]
    elif "environment" in report_data and "chargers" in report_data["environment"]:
        chargers = [tuple(c) for c in report_data["environment"]["chargers"]]

    if "walls" in belief_frames and len(belief_frames["walls"]) > 0:
        walls = [tuple(w) for w in belief_frames["walls"]]
    elif "environment" in report_data and "walls" in report_data["environment"]:
        walls = [tuple(w) for w in report_data["environment"]["walls"]]

    # Helper to retrieve closest belief marginal for step i
    def get_belief_marginal(step: int) -> np.ndarray:
        if f"frame_{step}" in belief_frames:
            return belief_frames[f"frame_{step}"]
        if len(frame_steps) > 0:
            closest_step = frame_steps[int(np.argmin([abs(s - step) for s in frame_steps]))]
            return belief_frames[f"frame_{closest_step}"]
        return np.ones((h, w), dtype=np.float64) / (w * h)

    # Detect battery capacity
    bat_capacity = 100
    cfg_file = run_dir / "config.yaml"
    if cfg_file.exists():
        try:
            from walle.config import load_config
            cfg = load_config(cfg_file)
            bat_capacity = cfg.resources.battery_capacity
        except Exception:
            pass
    elif "resource_utilization" in report_data and "battery_capacity" in report_data.get("resources", {}):
        bat_capacity = report_data["resources"]["battery_capacity"]
    elif "mission_summary" in report_data:
        cfg_name = report_data["mission_summary"].get("config_name")
        for cp in [Path(f"configs/{cfg_name}.yaml"), Path(f"configs/{cfg_name}"), Path(f"configs/mission_{cfg_name}.yaml")]:
            if cp.exists():
                try:
                    from walle.config import load_config
                    bat_capacity = load_config(cp).resources.battery_capacity
                    break
                except Exception:
                    pass

    # 1. Render Summary PNG (Final step with true EVE revealed)
    final_marginal = get_belief_marginal(total_steps)
    summary_img = render_mission_frame(
        step_idx=total_steps - 1,
        total_steps=total_steps,
        records=records,
        belief_grid=final_marginal,
        walls=walls,
        chargers=chargers,
        grid_size=(w, h),
        battery_capacity=bat_capacity,
        true_location=true_loc,
        true_status=true_st,
        is_final_frame=True,
    )
    summary_path = run_dir / "summary.png"
    summary_img.save(summary_path)

    # 2. Render GIF frames
    gif_frames: List[Image.Image] = []
    step_interval = 1 if total_steps <= 40 else 2
    render_indices = list(range(0, total_steps, step_interval))
    if render_indices[-1] != total_steps - 1:
        render_indices.append(total_steps - 1)

    for idx in render_indices:
        is_last = (idx == total_steps - 1)
        b_grid = get_belief_marginal(idx + 1)
        img = render_mission_frame(
            step_idx=idx,
            total_steps=total_steps,
            records=records,
            belief_grid=b_grid,
            walls=walls,
            chargers=chargers,
            grid_size=(w, h),
            battery_capacity=bat_capacity,
            true_location=true_loc if is_last else None,
            true_status=true_st if is_last else None,
            is_final_frame=is_last,
        )
        gif_frames.append(img)

    for _ in range(12):
        gif_frames.append(gif_frames[-1])

    gif_path = run_dir / "run.gif"
    gif_frames[0].save(
        gif_path,
        save_all=True,
        append_images=gif_frames[1:],
        duration=150,
        loop=0,
    )

    # 3. Render 2D Path Map
    render_path_map(
        records=records,
        belief_grid=final_marginal,
        walls=walls,
        chargers=chargers,
        grid_size=(w, h),
        true_location=true_loc,
        true_status=true_st,
        out_path=run_dir / "path_map.png",
    )

    # 4. Render 3D Space-Time Path
    render_path_3d(
        records=records,
        walls=walls,
        chargers=chargers,
        grid_size=(w, h),
        final_belief_grid=final_marginal,
        out_path=run_dir / "path_3d.png",
    )

    # 5. Render Belief Evolution Small Multiples
    render_belief_evolution(
        belief_frames=belief_frames,
        records=records,
        grid_size=(w, h),
        out_path=run_dir / "belief_evolution.png",
    )

    # 6. Render Metrics Dashboard
    render_metrics_dashboard(
        records=records,
        report_data=report_data,
        battery_capacity=bat_capacity,
        out_path=run_dir / "metrics_dashboard.png",
    )

    return summary_path, gif_path
