# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

param(
    [Parameter(Mandatory = $true)]
    [string] $Output,
    [int] $Workers = 6,
    [string] $ExpectedTag = '1.0',
    [switch] $AllowDirty,
    [switch] $AllowUntagged,
    [switch] $DryRun
)

$ErrorActionPreference = 'Stop'
$previousNoUserSite = $env:PYTHONNOUSERSITE
$env:PYTHONNOUSERSITE = '1'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$arguments = @(
    '-u', '-m', 'scripts.reproduce_article', 'resume',
    '--output', [System.IO.Path]::GetFullPath($Output),
    '--workers', $Workers,
    '--expected-tag', $ExpectedTag
)
if ($AllowDirty) { $arguments += '--allow-dirty' }
if ($AllowUntagged) { $arguments += '--allow-untagged' }
if ($DryRun) { $arguments += '--dry-run' }
Push-Location $repository
try {
    & python @arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    if ($null -eq $previousNoUserSite) {
        Remove-Item Env:PYTHONNOUSERSITE -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONNOUSERSITE = $previousNoUserSite
    }
}
