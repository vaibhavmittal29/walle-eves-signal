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
