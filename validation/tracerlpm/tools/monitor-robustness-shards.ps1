# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

param(
    [Parameter(Mandatory = $true)]
    [string] $RunnerProcessIdList
)

$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$logDirectory = Join-Path $repository 'validation\tracerlpm\output\robustness-study\campaign'
$monitorLog = Join-Path $logDirectory 'sharded-monitor.log'
$runnerProcessIds = @($RunnerProcessIdList.Split(',') | ForEach-Object { [int] $_ })
Set-Location $repository

while ($true) {
    $progress = (& python -m validation.tracerlpm.benchmark.scripts.check_robustness_progress) |
        ConvertFrom-Json
    Add-Content -LiteralPath $monitorLog -Value (
        "$(Get-Date -Format o) present=$($progress.present)/$($progress.expected) " +
        "epm=$($progress.epm_present) dm=$($progress.dm_present) invalid=$($progress.invalid)"
    )
    if ($progress.complete) {
        break
    }
    $active = @(Get-Process -Id $runnerProcessIds -ErrorAction SilentlyContinue)
    if ($active.Count -eq 0) {
        throw "Tous les runners sont arrêtés avec $($progress.present)/$($progress.expected) cas présents."
    }
    Start-Sleep -Seconds 30
}

# Resume queues are disjoint. After the final report is published, allow runners
# up to 30 seconds to close their Excel instance cleanly. Never search for or
# stop an Excel instance by date or title: it could belong to the user.
$shutdownDeadline = (Get-Date).AddSeconds(30)
while (@(Get-Process -Id $runnerProcessIds -ErrorAction SilentlyContinue).Count -gt 0 -and
       (Get-Date) -lt $shutdownDeadline) {
    Start-Sleep -Seconds 1
}
$stillActive = @(Get-Process -Id $runnerProcessIds -ErrorAction SilentlyContinue)
if ($stillActive.Count -gt 0) {
    Add-Content -LiteralPath $monitorLog -Value (
        "$(Get-Date -Format o) avertissement: $($stillActive.Count) runner(s) " +
        "encore actif(s) après 30 secondes; aucun processus n'a été forcé."
    )
}

& python -m validation.tracerlpm.benchmark.scripts.summarize_robustness_study `
    1> (Join-Path $logDirectory 'summary.stdout.log') `
    2> (Join-Path $logDirectory 'summary.stderr.log')
if ($LASTEXITCODE -ne 0) {
    throw "La synthèse de robustesse a échoué; consulter summary.stderr.log"
}

& python -m pytest validation/tracerlpm/benchmark/tests -q -p no:cacheprovider `
    --basetemp validation/tracerlpm/output/pytest-final `
    1> (Join-Path $logDirectory 'tests.stdout.log') `
    2> (Join-Path $logDirectory 'tests.stderr.log')
if ($LASTEXITCODE -ne 0) {
    throw "Les tests finaux ont échoué; consulter tests.stderr.log"
}

Set-Content -LiteralPath (Join-Path $logDirectory 'completed.txt') `
    -Value "$(Get-Date -Format o) robustness study complete" -Encoding utf8
