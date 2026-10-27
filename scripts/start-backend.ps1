# Starts the FieldSales API on port 8001 (reachable from phones at http://<server-ip>:8001).
# Applies any pending database migrations first. Keep this window open while the API should run.
#   powershell -ExecutionPolicy Bypass -File scripts\start-backend.ps1
param([int]$Port = 8001)
$ErrorActionPreference = "Stop"
$backend = Join-Path $PSScriptRoot "..\backend" | Resolve-Path
Set-Location $backend

$python = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Python environment missing. Run scripts\setup.ps1 first." }
if (-not (Test-Path (Join-Path $backend ".env"))) { throw "backend\.env missing. Copy backend\.env.example to backend\.env and fill it in." }

Write-Host "Applying database migrations..." -ForegroundColor Cyan
& $python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }

Write-Host "Starting API on http://0.0.0.0:$Port  (Ctrl+C to stop)" -ForegroundColor Green
& $python -m uvicorn app.main:app --host 0.0.0.0 --port $Port --proxy-headers
