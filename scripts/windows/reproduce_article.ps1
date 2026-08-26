param(
    [Parameter(Mandatory = $true)]
    [string] $Output,
    [int] $Workers = 6,
    [switch] $AllowDirty,
    [switch] $DryRun
)

$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$arguments = @(
    '-u', '-m', 'scripts.reproduce_article', 'resume',
    '--output', [System.IO.Path]::GetFullPath($Output),
    '--workers', $Workers
)
if ($AllowDirty) { $arguments += '--allow-dirty' }
if ($DryRun) { $arguments += '--dry-run' }
Push-Location $repository
try {
    & python @arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
