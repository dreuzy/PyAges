$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

$env:PYTHONUNBUFFERED = "1"
$env:PYAGE_PLOEMEUR_IG_PILOT_STEPS = "1200"
$env:PYAGE_PLOEMEUR_IG_PRODUCTION_STEPS = "32000"
$env:PYAGE_PLOEMEUR_IG_WARMUP_STEPS = "2000"

$logDirectory = Join-Path $projectRoot "results\ploemeur_targeted_ig_reproduction\logs"
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $logDirectory "external_batch_$stamp.log"

Write-Host "Ploemeur targeted physical-IG reproduction"
Write-Host "Five chains; 30,000 retained production draws per chain"
Write-Host "Log: $logPath"
Write-Host "The conditioned stages run only if both full-series gates pass."

& python -u -m scripts.run_ploemeur_targeted_ig_reproduction --stage all 2>&1 |
    Tee-Object -FilePath $logPath
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Error "Benchmark failed with exit code $exitCode. See $logPath"
}

Write-Host "Benchmark completed."
Write-Host "Report: $projectRoot\results\ploemeur_targeted_ig_reproduction\PLOEMEUR_TARGETED_IG_REPRODUCTION.md"
Write-Host "CSV: $projectRoot\results\ploemeur_targeted_ig_reproduction\ploemeur_targeted_nonregression_results.csv"
