"""Unit tests for Phase 10 benchmark harness."""

from pathlib import Path
import pytest

from walle.benchmark import generate_benchmark_config, run_benchmark
from walle.config import validate_config


def test_generate_benchmark_config_produces_valid_configs():
    """Benchmark configs must pass all validation rules across varied seeds."""
    for idx in range(10):
        cfg = generate_benchmark_config(base_seed=123, index=idx)
        validate_config(cfg)
        assert 12 <= cfg.mission.grid.width <= 24
        assert 12 <= cfg.mission.grid.height <= 24
        assert 60 <= cfg.resources.battery_capacity <= 120
        assert 0.8 <= cfg.sensor.noise_scale <= 1.5


def test_benchmark_execution_and_output_artifacts(tmp_path: Path):
    """run_benchmark produces benchmark_results.csv, benchmark_summary.md, and benchmark_chart.png."""
    out_dir = tmp_path / "bench_artifacts"
    md_p, csv_p, chart_p = run_benchmark(n_missions=3, base_seed=77, out_dir=out_dir)

    assert md_p.exists()
    assert csv_p.exists()
    assert chart_p.exists()

    # Verify CSV has rows for 3 missions * 3 agents = 9 rows (+ 1 header)
    lines = [l.strip() for l in csv_p.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 10

    # Verify MD summary contains key headers
    md_text = md_p.read_text(encoding="utf-8")
    assert "WALL-E Generalization Benchmark Results" in md_text
    assert "Bayes Planner Agent" in md_text
    assert "Random Agent" in md_text
    assert "Greedy Bearing Agent" in md_text

    # Verify chart size is non-trivial (> 20 KB)
    assert chart_p.stat().st_size > 20000


def test_benchmark_determinism(tmp_path: Path):
    """Running identical seeds produces identical benchmark results."""
    dir1 = tmp_path / "bench_1"
    dir2 = tmp_path / "bench_2"

    _, csv1, _ = run_benchmark(n_missions=2, base_seed=505, out_dir=dir1)
    _, csv2, _ = run_benchmark(n_missions=2, base_seed=505, out_dir=dir2)

    assert csv1.read_bytes() == csv2.read_bytes(), "Benchmark CSV results diverged with identical seed!"


def _make_mock_run(
    seed: int = 1,
    declared_location=(5, 5),
    declared_status="active",
    true_location=(5, 5),
    true_status="active",
    outcome="success",
    success=True,
    location_error=0.0,
    status_correct=True,
    steps=10,
    ticks_used=10,
    battery_used=15,
    recharges_count=0,
    min_battery_margin=10,
    location_confidence=0.8,
    status_confidence=0.8,
    credible_hit=True,
    clues_found=1,
    final_entropy=1.0,
):
    from walle.runner import RunResult
    return RunResult(
        config_name="mock_config",
        agent_type="bayes_planner",
        seed=seed,
        outcome=outcome,
        steps=steps,
        ticks_used=ticks_used,
        battery_used=battery_used,
        recharges_count=recharges_count,
        distance_travelled=float(steps),
        min_battery_margin=min_battery_margin,
        min_battery_absolute=5,
        declared_location=declared_location,
        declared_status=declared_status,
        true_location=true_location,
        true_status=true_status,
        location_error=location_error,
        status_correct=status_correct,
        success=success,
        credible_hit=credible_hit,
        final_entropy=final_entropy,
        location_confidence=location_confidence,
        status_confidence=status_confidence,
        clues_found=clues_found,
        trace_records=[],
    )


def test_calibration_bins_use_real_sample_means_not_midpoints():
    """Calibration bin means must reflect actual empirical samples rather than nominal midpoints."""
    from walle.benchmark import compute_calibration_bins

    # Craft 3 mock results falling into [0.70, 0.80) with specific confidences:
    # Midpoint of [0.70, 0.80) is 0.75, but sample mean is (0.71 + 0.72 + 0.73) / 3 = 0.72.
    mock_runs = [
        _make_mock_run(seed=1, location_confidence=0.71, location_error=0.0, credible_hit=True),
        _make_mock_run(seed=2, location_confidence=0.72, location_error=1.0, credible_hit=True),
        _make_mock_run(seed=3, location_confidence=0.73, location_error=2.0, credible_hit=False),
    ]

    bins = [(0.50, 0.70), (0.70, 0.80), (0.80, 0.90)]
    stats = compute_calibration_bins(mock_runs, bins=bins, distance_threshold=1.5)

    target_bin = [b for b in stats if b["low"] == 0.70 and b["high"] == 0.80][0]
    assert target_bin["count"] == 3
    # Empirical sample mean is exactly 0.72, whereas nominal midpoint is 0.75
    assert target_bin["mean_confidence"] == pytest.approx(0.72, abs=1e-5)
    assert target_bin["mean_confidence"] != 0.75

    # Patch accuracy: runs 1 and 2 (errors 0.0, 1.0 <= 1.5) hit, run 3 (error 2.0) misses -> 2/3
    assert target_bin["patch_accuracy"] == pytest.approx(2.0 / 3.0, abs=1e-5)
    # Credible coverage: runs 1 and 2 hit, run 3 misses -> 2/3
    assert target_bin["credible_coverage"] == pytest.approx(2.0 / 3.0, abs=1e-5)
    # Wilson CI exists and encloses the point estimate
    assert target_bin["ci_95_low"] <= target_bin["patch_accuracy"] <= target_bin["ci_95_high"]


def test_no_region_generated_not_counted_as_missed():
    """Runs with credible_hit=None must not be counted in credible coverage denominator."""
    from walle.benchmark import compute_calibration_bins

    runs = [
        _make_mock_run(seed=1, location_confidence=0.85, credible_hit=True),
        _make_mock_run(seed=2, location_confidence=0.85, credible_hit=None),  # Non-Bayesian / no region
    ]

    bins = [(0.80, 0.90)]
    stats = compute_calibration_bins(runs, bins=bins)
    target = stats[0]
    assert target["count"] == 2
    # Only run 1 had an evaluable credible region, and it was a hit -> 100%, NOT 50%!
    assert target["credible_coverage"] == pytest.approx(1.0)


def test_calibration_counts_reconcile_with_records():
    """Sum of bin counts must strictly equal the total number of valid runs with confidence."""
    from walle.benchmark import compute_calibration_bins
    import numpy as np

    rng = np.random.default_rng(42)
    runs = []
    for s in range(50):
        conf = float(rng.uniform(0.1, 0.99))
        err = float(rng.exponential(2.0))
        runs.append(_make_mock_run(seed=s, location_confidence=conf, location_error=err, success=(err <= 2.0)))

    stats = compute_calibration_bins(runs)
    total_binned = sum(b["count"] for b in stats)
    assert total_binned == len(runs) == 50


def test_benchmark_summaries_reconcile_with_csv(tmp_path: Path):
    """Markdown benchmark summary metrics must reconcile exactly with raw CSV averages."""
    import csv

    out_dir = tmp_path / "bench_reconcile"
    md_p, csv_p, _ = run_benchmark(n_missions=3, base_seed=101, out_dir=out_dir)

    # Read CSV
    with open(csv_p, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Reconcile per agent
    for at in ["random", "greedy_bearing", "bayes_planner"]:
        agent_rows = [r for r in rows if r["agent_type"] == at]
        assert len(agent_rows) == 3

        csv_successes = sum(1 for r in agent_rows if r["success"].lower() == "true")
        csv_success_rate = csv_successes / len(agent_rows)
        csv_mean_err = sum(float(r["location_error"]) for r in agent_rows) / len(agent_rows)
        csv_mean_bat = sum(float(r["battery_used"]) for r in agent_rows) / len(agent_rows)

        md_text = md_p.read_text(encoding="utf-8")
        # Check that the formatted success rate appears in MD table
        expected_rate_str = f"{csv_success_rate:.1%}"
        expected_err_str = f"{csv_mean_err:.2f}"
        expected_bat_str = f"{csv_mean_bat:.1f}"

        assert expected_rate_str in md_text
        assert expected_err_str in md_text
        assert expected_bat_str in md_text


def test_paired_seeds_benchmark_comparisons(tmp_path: Path):
    """In benchmark evaluation, all agent architectures must run against the identical mission worlds."""
    import csv

    out_dir = tmp_path / "bench_paired"
    _, csv_p, _ = run_benchmark(n_missions=2, base_seed=999, out_dir=out_dir)

    with open(csv_p, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Group by mission_id
    m0_rows = [r for r in rows if r["mission_id"] == "0"]
    m1_rows = [r for r in rows if r["mission_id"] == "1"]

    for group in [m0_rows, m1_rows]:
        assert len(group) == 3
        # Ensure world parameters are 100% identical across all 3 architectures
        seeds = set(r["seed"] for r in group)
        widths = set(r["grid_width"] for r in group)
        heights = set(r["grid_height"] for r in group)
        densities = set(r["obstacle_density"] for r in group)
        capacities = set(r["battery_capacity"] for r in group)
        noises = set(r["noise_scale"] for r in group)

        assert len(seeds) == 1
        assert len(widths) == 1
        assert len(heights) == 1
        assert len(densities) == 1
        assert len(capacities) == 1
        assert len(noises) == 1

