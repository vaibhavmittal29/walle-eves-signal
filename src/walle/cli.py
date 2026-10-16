"""Command Line Interface for WALL-E and EVE's Signal."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from walle.runner import run_mission
from walle.viz import generate_visuals_from_run


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser for the walle CLI."""
    parser = argparse.ArgumentParser(
        prog="walle",
        description="WALL-E and EVE's Signal: Autonomous Bayesian Search Agent.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # run command
    run_parser = subparsers.add_parser("run", help="Run a mission simulation")
    run_parser.add_argument("--config", type=str, required=True, help="Path to YAML configuration")
    run_parser.add_argument("--agent", type=str, default="bayes_planner", choices=["bayes_planner", "greedy_bearing", "random"], help="Agent type")
    run_parser.add_argument("--out", type=str, default=None, help="Output directory")
    run_parser.add_argument("--seed", type=int, default=None, help="Optional mission seed override")
    run_parser.add_argument("--ascii", action="store_true", help="Print ASCII frames live")

    # viz command
    viz_parser = subparsers.add_parser("viz", help="Render visuals from a saved run")
    viz_parser.add_argument("run_pos", nargs="?", default=None, help="Directory containing run artifacts (positional)")
    viz_parser.add_argument("--run", type=str, default=None, help="Directory containing run artifacts")

    # benchmark command
    bench_parser = subparsers.add_parser("benchmark", help="Run generalization benchmark")
    bench_parser.add_argument("--n", type=int, default=100, help="Number of missions")
    bench_parser.add_argument("--out", type=str, default="outputs/benchmark", help="Benchmark output directory")
    bench_parser.add_argument("--seed", type=int, default=42, help="Benchmark master seed")

    return parser


def main(args: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    if parsed_args.command is None:
        parser.print_help()
        return 0

    if parsed_args.command == "run":
        print(f"\n[WALL-E] Launching mission: {parsed_args.config} (Agent: {parsed_args.agent})")
        res = run_mission(
            config_path=parsed_args.config,
            agent_type=parsed_args.agent,
            out_dir=parsed_args.out,
            master_seed=parsed_args.seed,
            print_ascii=parsed_args.ascii,
        )

        print("\n" + "=" * 50)
        print("MISSION RESULT SUMMARY")
        print("=" * 50)
        print(f"Config:              {res.config_name} (Seed: {res.seed})")
        print(f"Outcome:             {res.outcome.upper()}")
        print(f"Steps / Ticks:       {res.steps} steps / {res.ticks_used} ticks")
        print(f"Battery Used:        {res.battery_used} (Recharges: {res.recharges_count})")
        print(f"Min Battery Margin:  {res.min_battery_margin}")
        print(f"Declared Location:   {res.declared_location} [True: {res.true_location}]")
        print(f"Location Error:      {res.location_error:.2f} cells")
        print(f"Declared Status:     '{res.declared_status}' [True: '{res.true_status}']")
        print(f"Status Correct:      {res.status_correct}")
        print(f"Credible Region Hit: {res.credible_hit}")
        print(f"Mission Success:     {'SUCCESS' if res.success else 'FAILED'}")
        print("=" * 50 + "\n")
        return 0

    if parsed_args.command == "viz":
        target_run = parsed_args.run or parsed_args.run_pos
        if not target_run:
            parser.error("walle viz requires a run directory (e.g. 'walle viz outputs/mission_medium_seed7' or '--run outputs/mission_medium_seed7')")
        print(f"\n[WALL-E Viz] Generating full visualization suite from {target_run}...")
        summary_p, gif_p = generate_visuals_from_run(target_run)
        print(f"Saved summary frame:       {summary_p}")
        print(f"Saved animated GIF:        {gif_p}")
        print(f"Saved 2D path map:         {Path(target_run) / 'path_map.png'}")
        print(f"Saved 3D space-time path:  {Path(target_run) / 'path_3d.png'}")
        print(f"Saved belief evolution:    {Path(target_run) / 'belief_evolution.png'}")
        print(f"Saved metrics dashboard:   {Path(target_run) / 'metrics_dashboard.png'}\n")
        return 0

    if parsed_args.command == "benchmark":
        from walle.benchmark import run_benchmark
        run_benchmark(
            n_missions=parsed_args.n,
            base_seed=parsed_args.seed,
            out_dir=parsed_args.out,
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
