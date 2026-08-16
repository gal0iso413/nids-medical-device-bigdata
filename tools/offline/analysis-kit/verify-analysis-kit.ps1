#Requires -Version 5.1
param([string]$KitDirectory="")
$ErrorActionPreference="Stop"; Set-StrictMode -Version Latest
if (!$KitDirectory) {$KitDirectory=$PSScriptRoot}; . (Join-Path $PSScriptRoot "analysis-kit-common.ps1")
try {$m=Test-AnalysisKit $KitDirectory; @{status="verified";source_commit=$m.source_commit;file_count=@($m.files).Count}|ConvertTo-Json -Compress; exit 0} catch {[Console]::Error.WriteLine($_.Exception.Message);exit 1}
