#Requires -Version 5.1
param([Parameter(Mandatory=$true)][string]$FieldRunConfig,[Parameter(Mandatory=$true)][string]$FactRoot,[Parameter(Mandatory=$true)][string]$OutputRoot,[string]$PeriodStart="",[string]$PeriodEnd="",[string]$InstallDirectory="")
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
if(!$InstallDirectory){$InstallDirectory=Join-Path (Split-Path -Parent $PSScriptRoot) 'nids-analysis-runtime'};$py=Join-Path ([IO.Path]::GetFullPath($InstallDirectory)) '.venv\Scripts\python.exe';$source=Join-Path ([IO.Path]::GetFullPath($InstallDirectory)) 'source';if(!(Test-Path $py)){throw 'runtime is missing'}
if([string]::IsNullOrWhiteSpace($PeriodStart) -ne [string]::IsNullOrWhiteSpace($PeriodEnd)){throw 'PeriodStart and PeriodEnd must both be set or both omitted'}
$cli=@('--fact-root',$FactRoot,'--output-root',$OutputRoot);if($PeriodStart -and $PeriodEnd){$cli+=@('--period-start',$PeriodStart,'--period-end',$PeriodEnd)}
Push-Location $source;try{&$py -s -m data_pipeline.analysis.class2_serving_mart @cli;if($LASTEXITCODE -ne 0){throw 'Class 2 serving-mart build failed'}}finally{Pop-Location}
