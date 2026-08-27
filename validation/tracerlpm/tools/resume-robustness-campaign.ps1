# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

param(
    [ValidateRange(1, 12)]
    [int] $ShardCount = 6
)

$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$runner = Join-Path $repository 'validation\tracerlpm\bin\campaign-session\TracerLpmRunner.exe'
$runnerConfig = Join-Path $repository 'validation\tracerlpm\config\runner-config.robustness-session.local.yaml'
$monitorScript = Join-Path $PSScriptRoot 'monitor-robustness-shards.ps1'
$logDirectory = Join-Path $repository 'validation\tracerlpm\output\robustness-study\campaign'
$prefix = 'tracerlpm-robustness-missing'
Set-Location $repository

if (@(Get-Process -Name TracerLpmRunner -ErrorAction SilentlyContinue).Count -gt 0) {
    throw 'Un runner TracerLPM est déjà actif. La reprise n''a pas été lancée.'
}

# Excel COM doit être activé depuis la session Windows interactive de
# l'utilisateur. Cette sonde ferme immédiatement sa propre instance et ne touche
# à aucun classeur existant.
$excel = $null
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.DisplayAlerts = $false
    $excel.Quit()
}
catch {
    throw (
        'Excel COM est indisponible dans cette session Windows. Exécuter ce script ' +
        'depuis la session interactive de l''utilisateur. Détail : ' + $_.Exception.Message
    )
}
finally {
    if ($null -ne $excel) {
        [void] [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($excel)
    }
}

$manifestJson = & python -m `
    validation.tracerlpm.benchmark.scripts.prepare_remaining_robustness_shards `
    --shards $ShardCount --prefix $prefix
if ($LASTEXITCODE -ne 0) {
    throw 'La préparation des cas manquants a échoué.'
}
$manifest = $manifestJson | ConvertFrom-Json
if ($manifest.remaining -eq 0) {
    Write-Output 'Les 480 cas sont déjà présents et valides.'
    exit 0
}

$runners = @()
for ($index = 0; $index -lt $manifest.shards.Count; $index++) {
    $number = $index + 1
    $stdout = Join-Path $logDirectory "missing-shard$number.stdout.log"
    $stderr = Join-Path $logDirectory "missing-shard$number.stderr.log"
    $runners += Start-Process -FilePath $runner `
        -ArgumentList @('--config', $runnerConfig, '--cases', $manifest.shards[$index].path) `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr `
        -WindowStyle Hidden -PassThru
}

$runnerIds = $runners.Id -join ','
$monitorStdout = Join-Path $logDirectory 'missing-monitor.stdout.log'
$monitorStderr = Join-Path $logDirectory 'missing-monitor.stderr.log'
$monitor = Start-Process -FilePath 'powershell.exe' `
    -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $monitorScript,
        '-RunnerProcessIdList', $runnerIds
    ) `
    -RedirectStandardOutput $monitorStdout -RedirectStandardError $monitorStderr `
    -WindowStyle Hidden -PassThru

$launch = [ordered]@{
    launched_at = (Get-Date -Format o)
    valid_before_launch = $manifest.valid
    remaining = $manifest.remaining
    runner_process_ids = @($runners.Id)
    monitor_process_id = $monitor.Id
    manifest = $manifest.manifest_path
}
$launchPath = Join-Path $logDirectory 'missing-launch.json'
$launch | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $launchPath -Encoding utf8
$launch | ConvertTo-Json -Depth 4
