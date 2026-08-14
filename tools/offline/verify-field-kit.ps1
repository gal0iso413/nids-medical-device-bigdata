#Requires -Version 5.1
[CmdletBinding()]
param(
    [string] $KitDirectory = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$scriptDirectory = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($KitDirectory)) {
    $KitDirectory = $scriptDirectory
}
. (Join-Path $scriptDirectory "field-kit-common.ps1")

try {
    $manifest = Test-FieldKit -KitDirectory $KitDirectory
    [ordered]@{
        status = "verified"
        contract_version = $manifest.contract_version
        source_commit = $manifest.source_commit
        file_count = @($manifest.files).Count
    } | ConvertTo-Json -Compress
    exit 0
}
catch {
    [Console]::Error.WriteLine("field-kit verification failed: $($_.Exception.Message)")
    exit 1
}
