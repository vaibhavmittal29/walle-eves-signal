#!/usr/bin/env bash
set -e

echo "=== WALL-E: Generating All Sample Mission Runs & Visualizations ==="

# 1. Easy Mission
echo "[1/3] Running Mission Easy..."
python -m walle run --config configs/mission_easy.yaml --out outputs/mission_easy
python -m walle viz --run outputs/mission_easy

# 2. Medium Mission (Seed 7)
echo "[2/3] Running Mission Medium (Seed 7)..."
python -m walle run --config configs/mission_medium.yaml --out outputs/mission_medium_seed7
python -m walle viz --run outputs/mission_medium_seed7

# 3. Hard Decoys Mission
echo "[3/3] Running Mission Hard Decoys..."
python -m walle run --config configs/mission_hard_decoys.yaml --out outputs/mission_hard_decoys
python -m walle viz --run outputs/mission_hard_decoys

echo "=== All sample outputs successfully regenerated in outputs/ ==="
