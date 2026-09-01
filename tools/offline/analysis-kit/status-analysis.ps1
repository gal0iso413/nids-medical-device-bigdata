#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string] $Config,
    [string] $MartRoot = "",
    [string] $InstallDirectory = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-StatusFullPath {
    param([string] $Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Read-QuotedTomlValue {
    param([string] $TomlPath, [string] $Section, [string] $Key)
    $inSection = $false
    foreach ($line in @(Get-Content -LiteralPath $TomlPath -Encoding UTF8)) {
        if ($line -match '^\s*\[([^\]]+)\]\s*$') {
            $inSection = ($Matches[1] -eq $Section)
            continue
        }
        if (-not $inSection) { continue }
        $pattern = '^\s*' + [regex]::Escape($Key) + '\s*=\s*"([^"]*)"\s*(#.*)?$'
        if ($line -match $pattern) { return [string]$Matches[1] }
    }
    return ""
}

function Read-JsonObject {
    param([string] $Path)
    try {
        return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
    }
    catch {
        return $null
    }
}

$configPath = Get-StatusFullPath $Config
if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw "field-run config is missing."
}

$checkpointRoot = Read-QuotedTomlValue $configPath "paths" "checkpoint_root"
$outputRoot = Read-QuotedTomlValue $configPath "paths" "output_root"
$class1Config = Read-QuotedTomlValue $configPath "class1" "config"

$checkpoint = [ordered]@{
    root_present = $false
    runs = 0
    sealed = 0
    complete = 0
    complete_months = @()
    unsealed_run_ids = @()
}
if (-not [string]::IsNullOrWhiteSpace($checkpointRoot) -and (Test-Path -LiteralPath $checkpointRoot -PathType Container)) {
    $checkpoint.root_present = $true
    $runRoot = Join-Path $checkpointRoot "supply_monthly_orchestration\checkpoint_version=1.0.0"
    if (Test-Path -LiteralPath $runRoot -PathType Container) {
        $completeMonths = New-Object System.Collections.Generic.List[string]
        $unsealed = New-Object System.Collections.Generic.List[string]
        foreach ($runDir in @(Get-ChildItem -LiteralPath $runRoot -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "run_id=*" })) {
            $checkpoint.runs++
            $sealedPath = Join-Path $runDir.FullName "_sealed_manifest.json"
            $completePath = Join-Path $runDir.FullName "_complete_manifest.json"
            $sealed = Test-Path -LiteralPath $sealedPath -PathType Leaf
            $complete = Test-Path -LiteralPath $completePath -PathType Leaf
            if ($sealed) { $checkpoint.sealed++ }
            if ($complete) {
                $checkpoint.complete++
                $manifest = Read-JsonObject $completePath
                if ($null -ne $manifest -and $manifest.PSObject.Properties.Name -contains "published_months") {
                    foreach ($entry in @($manifest.published_months)) {
                        $month = [string]$entry.month
                        if ($month -and -not $completeMonths.Contains($month)) { $completeMonths.Add($month) }
                    }
                }
            }
            elseif (-not $sealed) {
                $unsealed.Add($runDir.Name.Substring(7))
            }
        }
        $checkpoint.complete_months = @($completeMonths | Sort-Object)
        $checkpoint.unsealed_run_ids = @($unsealed)
    }
}

$facts = [ordered]@{
    root_present = $false
    months = @()
}
if (-not [string]::IsNullOrWhiteSpace($outputRoot) -and (Test-Path -LiteralPath $outputRoot -PathType Container)) {
    $facts.root_present = $true
    $monthRoot = Join-Path $outputRoot "fact_company_counterparty_product_month\schema_version=1.0.0"
    $months = New-Object System.Collections.Generic.List[string]
    if (Test-Path -LiteralPath $monthRoot -PathType Container) {
        foreach ($monthDir in @(Get-ChildItem -LiteralPath $monthRoot -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "month=*" })) {
            $manifestPath = Join-Path $monthDir.FullName "_manifest.json"
            if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { continue }
            $manifest = Read-JsonObject $manifestPath
            $month = $monthDir.Name.Substring(6)
            if ($null -ne $manifest -and [string]$manifest.partition_value) {
                $month = [string]$manifest.partition_value
            }
            if ($month -and -not $months.Contains($month)) { $months.Add($month) }
        }
    }
    $facts.months = @($months | Sort-Object)
}

$class1 = [ordered]@{
    config_present = $false
    anchors = @()
}
if (-not [string]::IsNullOrWhiteSpace($class1Config) -and (Test-Path -LiteralPath $class1Config -PathType Leaf)) {
    $class1.config_present = $true
    $class1Json = Read-JsonObject $class1Config
    if ($null -ne $class1Json -and [string]$class1Json.output_root) {
        $anchorRoot = [string]$class1Json.output_root
        $anchors = New-Object System.Collections.Generic.List[object]
        if (Test-Path -LiteralPath $anchorRoot -PathType Container) {
            foreach ($anchorDir in @(Get-ChildItem -LiteralPath $anchorRoot -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "anchor_month=*" })) {
                $manifestPath = Join-Path $anchorDir.FullName "run-manifest.json"
                $status = "missing_manifest"
                $month = $anchorDir.Name.Substring(13)
                if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
                    $manifest = Read-JsonObject $manifestPath
                    if ($null -eq $manifest) { $status = "unreadable_manifest" }
                    else {
                        if ([string]$manifest.anchor_month) { $month = [string]$manifest.anchor_month }
                        if ([string]$manifest.run_status) { $status = [string]$manifest.run_status }
                        else { $status = "unknown" }
                    }
                }
                $anchors.Add([ordered]@{ month = $month; run_status = $status })
            }
        }
        $class1.anchors = @($anchors | Sort-Object { $_.month })
    }
}

$class2 = [ordered]@{
    present = $false
}
if (-not [string]::IsNullOrWhiteSpace($MartRoot)) {
    $martManifest = Join-Path (Get-StatusFullPath $MartRoot) "class2_serving_mart\schema_version=1.1.0\_manifest.json"
    if (Test-Path -LiteralPath $martManifest -PathType Leaf) {
        $manifest = Read-JsonObject $martManifest
        if ($null -eq $manifest) {
            $class2 = [ordered]@{ present = $true; readable = $false }
        }
        else {
            $class2 = [ordered]@{
                present = $true
                readable = $true
                period_start = [string]$manifest.period_start
                period_end = [string]$manifest.period_end
                created_fingerprint = [string]$manifest.created_fingerprint
            }
        }
    }
}

$status = [ordered]@{
    config = $configPath
    checkpoint = $checkpoint
    verified_fact_months = $facts
    class1 = $class1
    class2_mart = $class2
}
$status | ConvertTo-Json -Depth 6 -Compress
