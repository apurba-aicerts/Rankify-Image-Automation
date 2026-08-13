# Start the WSL Postgres container that holds Rankify data (port 5432).
# Run from backend/:
#   .\scripts\start_rankify_postgres.ps1

$BackendRoot = Split-Path $PSScriptRoot -Parent

function Test-WindowsPostgres {
    param([string]$PythonExe)
    $code = @"
import os
from dotenv import load_dotenv
load_dotenv()
import psycopg
url = (os.getenv('DATABASE_URL') or '').replace('postgresql+psycopg://', 'postgresql://')
with psycopg.connect(url, connect_timeout=5) as c:
    c.execute('SELECT 1')
print('windows-ok')
"@
    $tmp = Join-Path $env:TEMP "rankify_pg_check.py"
    Set-Content -Path $tmp -Value $code -Encoding UTF8
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        $out = & $PythonExe $tmp 2>&1 | Out-String
        return ($LASTEXITCODE -eq 0) -and ($out -match "windows-ok")
    }
    finally {
        $ErrorActionPreference = $prev
        Remove-Item -Path $tmp -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Starting WSL postgres container..."
$ErrorActionPreference = "SilentlyContinue"
wsl docker update --restart unless-stopped postgres 2>$null | Out-Null
wsl docker start postgres 2>$null | Out-Null
$ErrorActionPreference = "Continue"

Write-Host "Waiting for Postgres inside WSL..."
$wslReady = $false
for ($i = 0; $i -lt 30; $i++) {
    wsl docker exec postgres pg_isready -U rankify -d rankify 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $wslReady = $true
        break
    }
    Start-Sleep -Seconds 2
}

if (-not $wslReady) {
    Write-Host "Postgres did not start inside WSL."
    Write-Host "Try: open Docker Desktop, wait until it is running, then run this script again."
    exit 1
}

$counts = (wsl docker exec postgres psql -U rankify -d rankify -tAc "SELECT COUNT(*) || ' images, ' || (SELECT COUNT(*) FROM brands) || ' brands' FROM generated_images;" 2>$null).Trim()
Write-Host "Inside WSL: Postgres is ready ($counts)"

$python = Join-Path $BackendRoot "..\image_automation_313\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

Push-Location $BackendRoot
try {
    if (Test-WindowsPostgres -PythonExe $python) {
        Write-Host "From Windows: Connection OK (localhost:5432 reachable)"
        Write-Host ""
        Write-Host "You can start the API:"
        Write-Host "  uvicorn main:app --host 0.0.0.0 --port 8750"
        exit 0
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "WARNING: Postgres runs in WSL, but Windows CANNOT reach localhost:5432."
Write-Host "That is why test_db_connection.py fails even though the container is up."
Write-Host ""
Write-Host "Fix (try in order):"
Write-Host "  1. Start Docker Desktop fully, then run this script again"
Write-Host "  2. In PowerShell (Admin): wsl --shutdown   then reopen terminal and retry"
Write-Host "  3. Run the API from inside WSL instead of Windows PowerShell"
Write-Host ""
Write-Host "DATABASE_URL: postgresql+psycopg://rankify:rankify@localhost:5432/rankify"
exit 1
