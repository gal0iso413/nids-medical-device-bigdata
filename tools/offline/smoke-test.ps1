#Requires -Version 5.1
[CmdletBinding()]
param(
    [string] $KitDirectory = "",
    [string] $InstallDirectory = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$scriptDirectory = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($KitDirectory)) {
    $KitDirectory = $scriptDirectory
}
. (Join-Path $scriptDirectory "field-kit-common.ps1")

$kit = Get-FieldKitFullPath $KitDirectory
if ([string]::IsNullOrWhiteSpace($InstallDirectory)) {
    $InstallDirectory = Join-Path (Split-Path -Parent $kit) "nids-field-runtime"
}
$install = Get-FieldKitFullPath $InstallDirectory
$manifest = Test-FieldKit -KitDirectory $kit
$python = Join-Path $install ".venv\Scripts\python.exe"
$source = Join-Path $install "source"
if (-not (Test-Path -LiteralPath $python -PathType Leaf) -or -not (Test-Path -LiteralPath $source -PathType Container)) {
    throw "Installed field environment is incomplete."
}
if ((Get-Content -LiteralPath (Join-Path $install "source-commit.txt") -Raw).Trim() -ne $manifest.source_commit) {
    throw "Installed source commit does not match the field kit."
}

$previousNoIndex = $env:PIP_NO_INDEX
$previousDisableCheck = $env:PIP_DISABLE_PIP_VERSION_CHECK
try {
    $env:PIP_NO_INDEX = "1"
    $env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
    & $python -I -c "import numpy,pandas,pyarrow,openpyxl; print('required_imports=ok')"
    if ($LASTEXITCODE -ne 0) { throw "Required package import smoke test failed." }
    Push-Location $source
    try {
        & $python -s -m data_pipeline.cli --help | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "CLI help smoke test failed." }
        & $python -I -c "import pathlib,tomllib; tomllib.loads(pathlib.Path('config/field-run.example.toml').read_text(encoding='utf-8')); print('example_config=ok')"
        if ($LASTEXITCODE -ne 0) { throw "Example config parse smoke test failed." }
        & $python -s -m unittest tests.cli.test_field_runner -v
        if ($LASTEXITCODE -ne 0) { throw "Synthetic CLI smoke tests failed." }
    }
    finally {
        Pop-Location
    }
    [ordered]@{
        status = "passed"
        source_commit = $manifest.source_commit
        actual_data_read = $false
        network_access = "not_attempted"
    } | ConvertTo-Json -Compress
}
finally {
    $env:PIP_NO_INDEX = $previousNoIndex
    $env:PIP_DISABLE_PIP_VERSION_CHECK = $previousDisableCheck
}
