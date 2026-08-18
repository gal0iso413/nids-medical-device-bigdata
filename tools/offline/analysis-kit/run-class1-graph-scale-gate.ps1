#Requires -Version 5.1
param([Parameter(Mandatory=$true)][string]$Config,[Parameter(Mandatory=$true)][string]$Report,[string]$InstallDirectory="")
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
if(!$InstallDirectory){$InstallDirectory=Join-Path (Split-Path -Parent $PSScriptRoot) 'nids-analysis-runtime'};$py=Join-Path ([IO.Path]::GetFullPath($InstallDirectory)) '.venv\Scripts\python.exe';$source=Join-Path ([IO.Path]::GetFullPath($InstallDirectory)) 'source';if(!(Test-Path $py)){throw 'runtime is missing'};Push-Location $source;try{&$py -s -m data_pipeline.observability.class1_graph_scale_gate --config $Config --report $Report;if($LASTEXITCODE -ne 0){throw 'Class 1 graph-scale gate failed'}}finally{Pop-Location}
