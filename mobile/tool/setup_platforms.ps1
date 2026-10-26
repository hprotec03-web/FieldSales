# Windows: generates android/ (and ios/ for later use on a Mac) and applies FieldSales permissions.
# Run from the mobile\ directory:   powershell -ExecutionPolicy Bypass -File tool\setup_platforms.ps1
$ErrorActionPreference = "Stop"
if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) { throw "Flutter SDK not found. See https://docs.flutter.dev/get-started/install" }
flutter create . --project-name fieldsales_mobile --org com.fieldsales --platforms android,ios
flutter pub get

if (Get-Command py -ErrorAction SilentlyContinue) { $python = "py" } else { $python = "python" }
$script = Get-Content -Raw (Join-Path $PSScriptRoot "setup_platforms.sh")
$py = [regex]::Match($script, "python3 - <<'PY'\r?\n(.*?)\r?\nPY", "Singleline").Groups[1].Value
$py | & $python -
Write-Host "`nManual steps: set minSdk = 23 and enable core-library desugaring in android/app/build.gradle(.kts) (see mobile/README.md)."
