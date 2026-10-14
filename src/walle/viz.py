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
    ax_map.set_title(f"Step {step_idx + 1}/{total_steps} | Strategy: {strat}\nAgent Pos: {pos} | MAP: ({map_x}, {map_y})", fontsize=10, fontweight="bold")
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
    ax_res.set_ylim(0, 105)
    ax_res.set_xlabel("Mission Step", fontsize=9)
    ax_res.set_ylabel("Battery Level", fontsize=9)
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


def generate_visuals_from_run(run_dir: Union[str, Path]) -> Tuple[Path, Path]:
    """Generate summary.png and run.gif from run artifacts (trace.jsonl, report.json, belief_frames.npz)."""
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

    # Extract chargers and grid size from records
    w, h = 20, 20
    chargers = [(2, 2), (15, 9)]  # Default fallback
    walls: List[Tuple[int, int]] = []

    # Map grid sizes from frames if available
    first_frame_key = "frame_0" if "frame_0" in belief_frames else (f"frame_{frame_steps[0]}" if len(frame_steps) > 0 else None)
    if first_frame_key and first_frame_key in belief_frames:
        h, w = belief_frames[first_frame_key].shape

    # Helper to retrieve closest belief marginal for step i
    def get_belief_marginal(step: int) -> np.ndarray:
        if f"frame_{step}" in belief_frames:
            return belief_frames[f"frame_{step}"]
        # Find closest available frame
        if len(frame_steps) > 0:
            closest_step = frame_steps[int(np.argmin([abs(s - step) for s in frame_steps]))]
            return belief_frames[f"frame_{closest_step}"]
        return np.ones((h, w), dtype=np.float64) / (w * h)

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
        true_location=true_loc,
        true_status=true_st,
        is_final_frame=True,
    )
    summary_path = run_dir / "summary.png"
    summary_img.save(summary_path)

    # 2. Render GIF frames (every step or every 2 steps for smooth animation)
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
            true_location=true_loc if is_last else None,
            true_status=true_st if is_last else None,
            is_final_frame=is_last,
        )
        gif_frames.append(img)

    # Append 12 extra copies of the final frame for a 2-second hold
    for _ in range(12):
        gif_frames.append(gif_frames[-1])

    gif_path = run_dir / "run.gif"
    gif_frames[0].save(
        gif_path,
        save_all=True,
        append_images=gif_frames[1:],
        duration=150,  # ~6.6 fps
        loop=0,
    )

    return summary_path, gif_path
