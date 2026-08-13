# Start Postgres, wait until ready, then launch the API in the same session.
# Usage (from backend/):
#   .\scripts\start_dev.ps1

$ErrorActionPreference = "Stop"
$BackendRoot = Split-Path $PSScriptRoot -Parent
Set-Location $BackendRoot

& "$PSScriptRoot\start_rankify_postgres.ps1"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Starting API (Postgres must stay up — start uvicorn immediately)..."
$python = Join-Path $BackendRoot "..\image_automation_313\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
& uvicorn main:app --host 0.0.0.0 --port 8750
