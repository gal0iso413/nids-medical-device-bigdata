#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string] $File,
    [string[]] $ArgumentList = @(),
    [string] $LogPath = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$target = [System.IO.Path]::GetFullPath($File)
if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
    throw "keep-session target file is missing."
}

if ([string]::IsNullOrWhiteSpace($LogPath)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $LogPath = Join-Path $env:TEMP ("nids-keep-session-" + $stamp + ".log")
}
$logFull = [System.IO.Path]::GetFullPath($LogPath)
$logParent = Split-Path -Parent $logFull
if (-not [string]::IsNullOrWhiteSpace($logParent) -and -not (Test-Path -LiteralPath $logParent -PathType Container)) {
    $null = New-Item -ItemType Directory -Path $logParent -Force
}

if (-not ("NidsKeepAwake" -as [type])) {
    Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
public static class NidsKeepAwake {
    public const uint ES_SYSTEM_REQUIRED = 0x00000001;
    public const uint ES_CONTINUOUS = 0x80000000;
    [DllImport("kernel32.dll")]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
"@
}

$transcriptStarted = $false
try {
    [void][NidsKeepAwake]::SetThreadExecutionState(
        [NidsKeepAwake]::ES_CONTINUOUS -bor [NidsKeepAwake]::ES_SYSTEM_REQUIRED
    )
    Start-Transcript -LiteralPath $logFull | Out-Null
    $transcriptStarted = $true
    Write-Host ("keep-session log=" + $logFull)
    Write-Host "keep-session system sleep is blocked; the display may still turn off."
        & $target @ArgumentList
        $exitCode = 0
        if (Test-Path variable:LASTEXITCODE) { $exitCode = [int]$LASTEXITCODE }
        if ($exitCode -ne 0) {
            throw "keep-session wrapped command failed with exit code $exitCode"
        }
}
finally {
    if ($transcriptStarted) {
        Stop-Transcript | Out-Null
    }
    if ("NidsKeepAwake" -as [type]) {
        [void][NidsKeepAwake]::SetThreadExecutionState([NidsKeepAwake]::ES_CONTINUOUS)
    }
}
