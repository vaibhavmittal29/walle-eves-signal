"""Command Line Interface for WALL-E and EVE's Signal."""

from __future__ import annotations

import argparse
import sys


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
    run_parser.add_argument("--out", type=str, default="outputs", help="Output directory")
    run_parser.add_argument("--ascii", action="store_true", help="Print ASCII frames live")

    # viz command
    viz_parser = subparsers.add_parser("viz", help="Render visuals from a saved run")
    viz_parser.add_argument("--run", type=str, required=True, help="Directory containing run artifacts")

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

    print(f"WALL-E CLI: command '{parsed_args.command}' called.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
