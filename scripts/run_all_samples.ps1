# PowerShell script to run all sample missions and visualizations

Write-Host "=== WALL-E: Generating All Sample Mission Runs & Visualizations ===" -ForegroundColor Cyan

$PYTHON = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

# 1. Easy Mission
Write-Host "`n[1/3] Running Mission Easy..." -ForegroundColor Yellow
& $PYTHON -m walle run --config configs/mission_easy.yaml --out outputs/mission_easy
& $PYTHON -m walle viz --run outputs/mission_easy

# 2. Medium Mission (Seed 7)
Write-Host "`n[2/3] Running Mission Medium (Seed 7)..." -ForegroundColor Yellow
& $PYTHON -m walle run --config configs/mission_medium.yaml --out outputs/mission_medium_seed7
& $PYTHON -m walle viz --run outputs/mission_medium_seed7

# 3. Hard Decoys Mission
Write-Host "`n[3/3] Running Mission Hard Decoys..." -ForegroundColor Yellow
& $PYTHON -m walle run --config configs/mission_hard_decoys.yaml --out outputs/mission_hard_decoys
& $PYTHON -m walle viz --run outputs/mission_hard_decoys

Write-Host "`n=== All sample outputs successfully regenerated in outputs/ ===" -ForegroundColor Green
