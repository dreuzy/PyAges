param(
    [Parameter(Mandatory = $true)]
    [int] $EpmRunnerProcessId,
    [Parameter(Mandatory = $true)]
    [int] $DmRunnerProcessId
)

$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$logDirectory = Join-Path $repository 'validation\tracerlpm\output\robustness-study\campaign'

foreach ($processId in @($EpmRunnerProcessId, $DmRunnerProcessId)) {
    Wait-Process -Id $processId -ErrorAction SilentlyContinue
}

Set-Location $repository
& python -m validation.tracerlpm.benchmark.scripts.summarize_robustness_study `
    1> (Join-Path $logDirectory 'summary.stdout.log') `
    2> (Join-Path $logDirectory 'summary.stderr.log')
if ($LASTEXITCODE -ne 0) {
    throw "La synthèse de robustesse a échoué; consulter summary.stderr.log"
}

& python -m pytest validation/tracerlpm/benchmark/tests -q `
    1> (Join-Path $logDirectory 'tests.stdout.log') `
    2> (Join-Path $logDirectory 'tests.stderr.log')
if ($LASTEXITCODE -ne 0) {
    throw "Les tests finaux ont échoué; consulter tests.stderr.log"
}

Set-Content -LiteralPath (Join-Path $logDirectory 'completed.txt') `
    -Value "$(Get-Date -Format o) robustness study complete" -Encoding utf8
