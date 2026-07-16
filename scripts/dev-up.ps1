# Start New Cut local stack: remotion-service, FastAPI, Vite.
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File .\scripts\dev-up.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "backend"))) {
  throw "Could not find backend/ under $Root. Run scripts from the new_cut repo."
}

$BackendPy = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $BackendPy)) {
  throw "Missing backend venv: $BackendPy — create it and pip install -r requirements.txt"
}

Write-Host "Starting remotion-service (3100), backend (8000), frontend (5173)..." -ForegroundColor Cyan

Start-Process powershell -WorkingDirectory (Join-Path $Root "remotion") -ArgumentList @(
  "-NoExit",
  "-Command",
  "npm.cmd run service"
)

Start-Process powershell -WorkingDirectory (Join-Path $Root "backend") -ArgumentList @(
  "-NoExit",
  "-Command",
  ".\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
)

Start-Process powershell -WorkingDirectory (Join-Path $Root "frontend") -ArgumentList @(
  "-NoExit",
  "-Command",
  "npm.cmd run dev"
)

Write-Host ""
Write-Host "Windows opened. Wait ~10s for Remotion bundle, then:" -ForegroundColor Green
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\health-check.ps1"
Write-Host "  Frontend  http://127.0.0.1:5173"
Write-Host "  API       http://127.0.0.1:8000/docs"
Write-Host "  Remotion  http://127.0.0.1:3100/health"
