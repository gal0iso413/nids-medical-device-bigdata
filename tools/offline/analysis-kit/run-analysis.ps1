#Requires -Version 5.1
param(
    [Parameter(Mandatory = $true)][ValidateSet("preflight", "pipeline", "class2-export", "class1-run", "verify")][string] $Command,
    [Parameter(Mandatory = $true)][string] $Config,
    [string] $InstallDirectory = "",
    [string] $LogPath = ""
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if (!$InstallDirectory) { $InstallDirectory = Join-Path (Split-Path -Parent $PSScriptRoot) "nids-analysis-runtime" }
$runtime = [IO.Path]::GetFullPath($InstallDirectory)
$py = Join-Path $runtime ".venv\Scripts\python.exe"
$source = Join-Path $runtime "source"
if (!(Test-Path $py) -or !(Test-Path $source)) { throw "installed analysis environment is incomplete" }
$common = Join-Path $source "tools\offline\analysis-kit\analysis-kit-common.ps1"
. $common
$env:PIP_NO_INDEX = "1"

$transcriptStarted = $false
if (-not [string]::IsNullOrWhiteSpace($LogPath)) {
    $logFull = [IO.Path]::GetFullPath($LogPath)
    $logParent = Split-Path -Parent $logFull
    if (-not [string]::IsNullOrWhiteSpace($logParent) -and -not (Test-Path -LiteralPath $logParent -PathType Container)) {
        $null = New-Item -ItemType Directory -Path $logParent -Force
    }
    Start-Transcript -LiteralPath $logFull | Out-Null
    $transcriptStarted = $true
}

Push-Location $source
try {
    if ($Command -eq "preflight") { & $py -s -m data_pipeline.cli preflight --config $Config }
    elseif ($Command -eq "pipeline") { & $py -s -m data_pipeline.cli run --config $Config }
    elseif ($Command -eq "class2-export") {
        $cfg = Get-AnalysisConfigValue $py $Config "class2_export" "config"
        & $py -s -m data_pipeline.offline.class2_analysis_export --config $cfg
    }
    elseif ($Command -eq "class1-run") {
        $cfg = Get-AnalysisConfigValue $py $Config "class1" "config"
        & $py -s -m class_1_anomaly_detection.src.offline_anchor_runner --config $cfg
    }
    else {
        & $py -s -m data_pipeline.cli verify --config $Config
        $cfg = Get-AnalysisConfigValue $py $Config "class1" "config"
        $class1 = Get-Content $cfg -Raw -Encoding UTF8 | ConvertFrom-Json
        & $py -s -m data_pipeline.offline.local_analysis_tools verify-class1 --output-root $class1.output_root --anchor-month $class1.anchor_month
    }
    if ($LASTEXITCODE -ne 0) { throw "existing analysis command failed: $Command" }
}
finally {
    Pop-Location
    if ($transcriptStarted) { Stop-Transcript | Out-Null }
}
