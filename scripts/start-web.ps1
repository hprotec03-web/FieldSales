# Starts the FieldSales web app (dev server) on http://localhost:5173, talking to the API on port 8001.
# Keep this window open while the web app should run.
#   powershell -ExecutionPolicy Bypass -File scripts\start-web.ps1
param([int]$ApiPort = 8001)
$ErrorActionPreference = "Stop"
$web = Join-Path $PSScriptRoot "..\web" | Resolve-Path
Set-Location $web

if (-not (Test-Path (Join-Path $web "node_modules"))) { throw "Web packages missing. Run scripts\setup.ps1 first." }

$env:VITE_API_PROXY = "http://127.0.0.1:$ApiPort"
Write-Host "Starting web app on http://localhost:5173 (API: $env:VITE_API_PROXY)  (Ctrl+C to stop)" -ForegroundColor Green
npm run dev
