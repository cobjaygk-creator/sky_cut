# Probe remotion-service, FastAPI /health and /ready.
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\health-check.ps1

$ErrorActionPreference = "Continue"
$failed = 0

function Show-Probe([string]$Name, [string]$Url) {
  Write-Host ""
  Write-Host "==> $Name  $Url" -ForegroundColor Cyan
  try {
    $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 8
    Write-Host "HTTP $($resp.StatusCode)" -ForegroundColor Green
    Write-Host $resp.Content
    if ($resp.StatusCode -ge 400) { $script:failed += 1 }
  } catch {
    Write-Host "FAIL: $($_.Exception.Message)" -ForegroundColor Red
    $script:failed += 1
  }
}

Show-Probe "remotion-service" "http://127.0.0.1:3100/health"
Show-Probe "backend /health" "http://127.0.0.1:8000/health"
Show-Probe "backend /ready" "http://127.0.0.1:8000/ready"

Write-Host ""
if ($failed -gt 0) {
  Write-Host "Health check failed ($failed probe(s))." -ForegroundColor Red
  Write-Host "Tip: run .\scripts\dev-up.ps1 and wait for Remotion 'bundle ready'."
  exit 1
}
Write-Host "All probes OK." -ForegroundColor Green
exit 0
