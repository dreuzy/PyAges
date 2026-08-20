param(
    [Parameter(Mandatory = $true)]
    [int] $RunnerProcessId1,
    [Parameter(Mandatory = $true)]
    [int] $RunnerProcessId2
)

$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$logDirectory = Join-Path $repository 'validation\tracerlpm\output\four-tracer\campaign-60'

foreach ($processId in @($RunnerProcessId1, $RunnerProcessId2)) {
    Wait-Process -Id $processId -ErrorAction SilentlyContinue
}

Set-Location $repository
$stdout = Join-Path $logDirectory 'summary.stdout.log'
$stderr = Join-Path $logDirectory 'summary.stderr.log'
& python -m validation.tracerlpm.benchmark.scripts.summarize_tracerlpm_sf6_campaign 1> $stdout 2> $stderr
if ($LASTEXITCODE -ne 0) {
    throw "La synthèse de la campagne SF6 a échoué; consulter $stderr"
}
