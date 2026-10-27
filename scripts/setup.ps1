# One-time setup on a new machine (or after cloning): Python environment + web packages.
# Needs Python 3.12, Node.js 20+ and the Microsoft ODBC Driver 18 for SQL Server.
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
$root = Join-Path $PSScriptRoot ".." | Resolve-Path
$backend = Join-Path $root "backend"
$web = Join-Path $root "web"

# ---- backend ----
Set-Location $backend
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating Python environment..." -ForegroundColor Cyan
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create the Python 3.12 environment (is Python 3.12 installed?)." }
}
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.lock   # exact, known-working versions
if ($LASTEXITCODE -ne 0) { throw "pip install failed." }
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created backend\.env from the example - edit DB_* and JWT_SECRET before starting." -ForegroundColor Yellow
}

# ---- web ----
Set-Location $web
Write-Host "Installing web packages..." -ForegroundColor Cyan
npm install
if ($LASTEXITCODE -ne 0) { throw "npm install failed." }

Write-Host "`nSetup complete. Start with:" -ForegroundColor Green
Write-Host "  scripts\start-backend.ps1   (window 1)"
Write-Host "  scripts\start-web.ps1       (window 2)"
