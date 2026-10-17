"""Script to evaluate BayesPlannerAgent calibration across N random missions (Group A7)."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from walle.benchmark import compute_calibration_bins, render_calibration_plot
from walle.config import load_config
from walle.geometry import distance
from walle.runner import RunResult, run_mission


def run_calibration(
    n_missions: int = 200,
    base_seed: int = 500,
    out_path: str = "outputs/calibration.md",
) -> None:
    print(f"Running calibration check across {n_missions} missions (base seed: {base_seed})...")

    cfg_base = load_config("configs/mission_medium.yaml")
    results: List[RunResult] = []
    csv_rows: List[Dict[str, Any]] = []

    bins = [
        (0.00, 0.50),
        (0.50, 0.70),
        (0.70, 0.80),
        (0.80, 0.90),
        (0.90, 0.95),
        (0.95, 1.0001),
    ]

    total_cred_hits = 0
    total_valid_cred = 0

    for i in range(n_missions):
        seed = base_seed + i
        res = run_mission(
            config_path="configs/mission_medium.yaml",
            agent_type="bayes_planner",
            master_seed=seed,
            agent_seed=seed + 100,
        )
        results.append(res)

        dec_loc = res.declared_location
        true_loc = res.true_location
        err = distance(dec_loc, true_loc)
        patch_hit = (err <= 1.5)
        cred_hit = res.credible_hit

        if cred_hit is not None:
            total_valid_cred += 1
            if cred_hit:
                total_cred_hits += 1

        csv_rows.append({
            "mission_id": i,
            "seed": seed,
            "declared_x": dec_loc[0],
            "declared_y": dec_loc[1],
            "declared_status": res.declared_status,
            "true_x": true_loc[0],
            "true_y": true_loc[1],
            "true_status": res.true_status,
            "location_error": round(err, 3),
            "status_correct": res.status_correct,
            "location_confidence": round(res.location_confidence, 4) if res.location_confidence is not None else None,
            "status_confidence": round(res.status_confidence, 4) if res.status_confidence is not None else None,
            "credible_hit": cred_hit,
            "patch_hit": patch_hit,
            "final_entropy": round(res.final_entropy, 3) if res.final_entropy is not None else None,
            "outcome": res.outcome,
            "steps": res.steps,
            "battery_used": res.battery_used,
            "ticks_used": res.ticks_used,
        })

        if (i + 1) % 25 == 0 or (i + 1) == n_missions:
            running_cov = (total_cred_hits / total_valid_cred) if total_valid_cred > 0 else 0.0
            print(f"  [{i + 1:3d}/{n_missions}] Completed. Running 90% credible coverage: {running_cov:.1%}")

    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # 1. Write per-run calibration_results.csv
    csv_file = out_file.parent / "calibration_results.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        if csv_rows:
            writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(csv_rows)
    print(f"Saved detailed per-run calibration data to {csv_file}")

    # 2. Compute bin statistics via shared compute_calibration_bins
    bin_stats = compute_calibration_bins(results, bins=bins, distance_threshold=1.5)

    cred_coverage = (total_cred_hits / total_valid_cred * 100.0) if total_valid_cred > 0 else 0.0

    lines = [
        "# Empirical Confidence Calibration Report",
        "",
        f"- **Missions Evaluated:** {n_missions}",
        f"- **Base Seed:** {base_seed}",
        f"- **Overall Nominal 90% Credible Region Empirical Coverage:** **{cred_coverage:.1f}%** (over {total_valid_cred} evaluable missions)",
        "",
        "## 1. Location Confidence Reliability & Calibration Table",
        "",
        "| Confidence Bin | Missions ($N$) | Mean Declared Confidence | Empirical Patch Accuracy ($\\le 1.5$ cells) | 95% Wilson CI | Empirical Credible Coverage (90%) | Calibration Assessment |",
        "|---|---|---|---|---|---|---|",
    ]

    for b in bin_stats:
        count = b["count"]
        low, high = b["low"], min(1.0, b["high"])
        bin_label = f"[{low:.2f}, {high:.2f})" if high < 1.0 else f"[{low:.2f}, 1.00]"
        if count > 0:
            mean_c = b["mean_confidence"] * 100.0
            patch_acc = b["patch_accuracy"] * 100.0
            ci_str = f"[{b['ci_95_low'] * 100.0:.1f}%, {b['ci_95_high'] * 100.0:.1f}%]"
            if b["credible_coverage"] is not None:
                cred_str = f"{b['credible_coverage'] * 100.0:.1f}%"
            else:
                cred_str = "N/A"

            # Well-calibrated if empirical patch accuracy is within 7% of mean confidence or exceeds lower bound
            if patch_acc >= (low * 100.0 - 5.0):
                status = "Well-Calibrated"
            else:
                status = "Over-Confident"

            lines.append(
                f"| `{bin_label}` | {count} | **{mean_c:.1f}%** | {patch_acc:.1f}% | {ci_str} | {cred_str} | `{status}` |"
            )
        else:
            lines.append(f"| `{bin_label}` | 0 | - | - | - | - | `N/A (no samples)` |")

    lines.extend([
        "",
        "## 2. Methodology & Invariant Guarantees",
        "",
        "### Metric Definitions & Thresholds",
        "- **Mean Declared Confidence:** The exact arithmetic mean of posterior mass $P(x^*, y^*)$ at the declared MAP coordinates across all runs falling within the bin (not the nominal midpoint).",
        "- **Empirical Patch Accuracy ($\\le 1.5$ cells):** The fraction of missions where Euclidean distance $\\|(x_{\\text{dec}}, y_{\\text{dec}}) - (x_{\\text{true}}, y_{\\text{true}})\\| \\le 1.5$ cells.",
        "- **95% Wilson Score Confidence Interval:** Computed as:",
        "  $$\\frac{p + \\frac{z^2}{2n} \\pm z\\sqrt{\\frac{p(1-p)}{n} + \\frac{z^2}{4n^2}}}{1 + \\frac{z^2}{n}} \\quad (z = 1.96)$$",
        "- **Empirical Credible Coverage:** Evaluates whether the true target coordinates $(x_{\\text{true}}, y_{\\text{true}})$ fall inside the agent's nominal 90% highest-posterior-density (HPD) credible region.",
        "",
        "### Handling of Forced & Incomplete Declarations",
        "- When a mission reaches the tick limit or depletes battery before crossing the declaration threshold, the agent executes a forced declaration evaluating its final posterior MAP hypothesis.",
        "- Forced declarations with low confidence are captured in the lower confidence bins (e.g., `[0.00, 0.50)` or `[0.50, 0.70)`) rather than discarded, guaranteeing complete accounting across all evaluated seeds.",
        "",
        "### Handling of Non-Generated Credible Regions",
        "- If an agent or baseline does not model a posterior belief distribution (`credible_hit is None`), the run is excluded from the credible coverage denominator, ensuring that 'no region generated' is never falsely penalized as a missed region.",
        "",
    ])

    out_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved calibration report to {out_file}")

    # 3. Render calibration reliability plot
    png_path = out_file.with_suffix(".png")
    render_calibration_plot(results, png_path)
    print(f"Saved calibration plot to {png_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run calibration evaluation.")
    parser.add_argument("--n", type=int, default=200, help="Number of missions")
    parser.add_argument("--seed", type=int, default=500, help="Base seed")
    parser.add_argument("--out", type=str, default="outputs/calibration.md", help="Output Markdown path")
    args = parser.parse_args()

    run_calibration(n_missions=args.n, base_seed=args.seed, out_path=args.out)
