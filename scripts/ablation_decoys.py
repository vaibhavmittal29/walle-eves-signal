"""Ablation experiment: compares Naive (assumed_spoof_rate=0.0) vs Robust (assumed_spoof_rate=0.15) on hard decoy missions."""

import argparse
import csv
from dataclasses import replace
from pathlib import Path
import sys
import time

import numpy as np

from walle.config import load_config
from walle.runner import run_mission


def run_ablation(n_seeds: int = 50, base_seed: int = 100, out_csv: str = "outputs/ablation_decoys.csv"):
    cfg_path = "configs/mission_hard_decoys.yaml"
    base_cfg = load_config(cfg_path)

    print(f"================================================================================")
    print(f"WALL-E Phase 9 Ablation Experiment: Decoy Spoofing & Sensor Noise Robustness")
    print(f"Configuration: {cfg_path} (Noise scale: {base_cfg.sensor.noise_scale}, Decoys: {base_cfg.sensor.decoys.count})")
    print(f"Sample Size:   {n_seeds} randomized seeds")
    print(f"================================================================================\n")

    results_naive = []
    results_robust = []
    csv_rows = []

    start_time = time.time()

    for i in range(n_seeds):
        seed = base_seed + i
        if (i + 1) % 5 == 0 or i == 0 or i == n_seeds - 1:
            print(f"  [Progress] Running seed {i + 1:2d}/{n_seeds} (Master Seed: {seed})...")

        # 1. Run Naive Agent (assumed_spoof_rate = 0.0)
        cfg_naive = replace(base_cfg, agent=replace(base_cfg.agent, assumed_spoof_rate=0.0))
        res_naive = run_mission(cfg_naive, master_seed=seed, agent_seed=seed + 1000)
        results_naive.append(res_naive)

        # 2. Run Robust Agent (assumed_spoof_rate = 0.15)
        cfg_robust = replace(base_cfg, agent=replace(base_cfg.agent, assumed_spoof_rate=0.15))
        res_robust = run_mission(cfg_robust, master_seed=seed, agent_seed=seed + 1000)
        results_robust.append(res_robust)

        csv_rows.append({
            "seed": seed,
            "naive_success": res_naive.success,
            "naive_loc_error": res_naive.location_error,
            "naive_battery": res_naive.battery_used,
            "naive_steps": res_naive.steps,
            "naive_outcome": res_naive.outcome,
            "robust_success": res_robust.success,
            "robust_loc_error": res_robust.location_error,
            "robust_battery": res_robust.battery_used,
            "robust_steps": res_robust.steps,
            "robust_outcome": res_robust.outcome,
        })

    elapsed = time.time() - start_time

    # Calculate aggregate metrics
    def calc_stats(results):
        n = len(results)
        successes = sum(1 for r in results if r.success)
        stranded = sum(1 for r in results if r.outcome == "stranded")
        mean_err = np.mean([r.location_error for r in results])
        median_err = np.median([r.location_error for r in results])
        mean_bat = np.mean([r.battery_used for r in results])
        mean_steps = np.mean([r.steps for r in results])
        status_acc = np.mean([1.0 if r.status_correct else 0.0 for r in results])
        return {
            "success_rate": successes / n,
            "mean_loc_err": mean_err,
            "median_loc_err": median_err,
            "mean_battery": mean_bat,
            "mean_steps": mean_steps,
            "status_accuracy": status_acc,
            "stranded_rate": stranded / n,
        }

    stats_naive = calc_stats(results_naive)
    stats_robust = calc_stats(results_robust)

    # Save CSV
    out_path = Path(out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows)

    # Print summary table
    print(f"\n================================================================================")
    print(f"ABLATION RESULTS SUMMARY (Completed in {elapsed:.1f}s)")
    print(f"================================================================================")
    print(f"| Metric                      | Naive Agent (eps=0.0) | Robust Agent (eps=0.15) | Delta (Robust vs Naive) |")
    print(f"|-----------------------------|-----------------------|-------------------------|-------------------------|")
    print(f"| Success Rate (error<=2 cells)| {stats_naive['success_rate']:>20.1%} | {stats_robust['success_rate']:>23.1%} | {stats_robust['success_rate'] - stats_naive['success_rate']:>+22.1%} |")
    print(f"| Mean Location Error (cells) | {stats_naive['mean_loc_err']:>20.2f} | {stats_robust['mean_loc_err']:>23.2f} | {stats_robust['mean_loc_err'] - stats_naive['mean_loc_err']:>+22.2f} |")
    print(f"| Median Location Error       | {stats_naive['median_loc_err']:>20.2f} | {stats_robust['median_loc_err']:>23.2f} | {stats_robust['median_loc_err'] - stats_naive['median_loc_err']:>+22.2f} |")
    print(f"| Status Classification Acc   | {stats_naive['status_accuracy']:>20.1%} | {stats_robust['status_accuracy']:>23.1%} | {stats_robust['status_accuracy'] - stats_naive['status_accuracy']:>+22.1%} |")
    print(f"| Mean Battery Consumed       | {stats_naive['mean_battery']:>20.1f} | {stats_robust['mean_battery']:>23.1f} | {stats_robust['mean_battery'] - stats_naive['mean_battery']:>+22.1f} |")
    print(f"| Mean Steps                  | {stats_naive['mean_steps']:>20.1f} | {stats_robust['mean_steps']:>23.1f} | {stats_robust['mean_steps'] - stats_naive['mean_steps']:>+22.1f} |")
    print(f"| Stranded Rate               | {stats_naive['stranded_rate']:>20.1%} | {stats_robust['stranded_rate']:>23.1%} | {stats_robust['stranded_rate'] - stats_naive['stranded_rate']:>+22.1%} |")
    print(f"================================================================================")
    print(f"Detailed per-seed comparison saved to: {out_path}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Phase 9 Decoy Robustness Ablation Study.")
    parser.add_argument("--n", type=int, default=50, help="Number of random seeds (default: 50)")
    parser.add_argument("--base-seed", type=int, default=100, help="Base master seed (default: 100)")
    parser.add_argument("--out", type=str, default="outputs/ablation_decoys.csv", help="Output CSV path")
    args = parser.parse_args()

    run_ablation(n_seeds=args.n, base_seed=args.base_seed, out_csv=args.out)
